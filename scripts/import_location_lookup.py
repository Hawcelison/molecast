#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ZIP_LOOKUP_SCHEMA = """
CREATE TABLE zip_locations (
    zip_code TEXT PRIMARY KEY,
    primary_city TEXT NOT NULL,
    state TEXT NOT NULL,
    county TEXT,
    county_fips TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    timezone TEXT,
    default_zoom INTEGER NOT NULL DEFAULT 9,
    source TEXT,
    source_year TEXT,
    source_version TEXT,
    dataset_version TEXT,
    imported_at TEXT,
    location_type TEXT,
    is_zcta INTEGER NOT NULL DEFAULT 0,
    confidence TEXT
);

CREATE INDEX idx_zip_locations_zip_code ON zip_locations(zip_code);
CREATE INDEX idx_zip_locations_city_state ON zip_locations(primary_city, state);
CREATE INDEX idx_zip_locations_state_city ON zip_locations(state, primary_city);

CREATE TABLE city_locations (
    id INTEGER PRIMARY KEY,
    primary_city TEXT NOT NULL,
    state TEXT NOT NULL,
    county TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    default_zoom INTEGER NOT NULL DEFAULT 9,
    source TEXT,
    source_version TEXT,
    dataset_version TEXT,
    imported_at TEXT,
    confidence TEXT,
    UNIQUE (primary_city, state, county)
);

CREATE INDEX idx_city_locations_city_state ON city_locations(primary_city, state);
CREATE INDEX idx_city_locations_state_city ON city_locations(state, primary_city);
"""


def import_location_lookup(
    source_json: Path,
    output_db: Path,
    manifest_path: Path,
    source_name: str,
    source_year: str | None,
    source_version: str | None,
    source_format: str = "auto",
    dataset_version: str | None = None,
    sentinel_zip_codes: list[str] | None = None,
) -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat()
    effective_dataset_version = dataset_version or source_version
    records = _load_records(
        source_json,
        source_name,
        source_year,
        source_version,
        effective_dataset_version,
        generated_at,
        source_format,
    )
    output_db.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    temp_db_path = _temporary_path(output_db.parent, ".sqlite3.tmp")
    try:
        _write_database(temp_db_path, records)
        _validate_database(temp_db_path, len(records), sentinel_zip_codes)
        temp_db_path.replace(output_db)
    finally:
        temp_db_path.unlink(missing_ok=True)

    checksum = _sha256_file(output_db)
    manifest = {
        "source_name": source_name,
        "source_year": source_year,
        "source_version": source_version,
        "dataset_version": effective_dataset_version,
        "future_source_license": None,
        "generated_at": generated_at,
        "imported_at": generated_at,
        "row_counts": {
            "zip_locations": len(records),
            "city_locations": _city_location_count(output_db),
        },
        "checksum_sha256": checksum,
        "notes": [
            "Phase 1 lookup database is seeded from backend/app/data/zip_codes.json for current development parity.",
            "Future imports should replace this seed with licensed nationwide ZIP/city source data.",
        ],
    }
    _write_manifest(manifest_path, manifest)
    return manifest


def _load_records(
    source_path: Path,
    source_name: str,
    source_year: str | None,
    source_version: str | None,
    dataset_version: str | None,
    imported_at: str,
    source_format: str,
) -> list[dict[str, Any]]:
    raw_records = _load_raw_records(source_path, source_format)
    if not isinstance(raw_records, list):
        raise ValueError("ZIP source must contain a list of records.")

    records: list[dict[str, Any]] = []
    seen_zip_codes: set[str] = set()
    for index, raw_record in enumerate(raw_records, start=1):
        if not isinstance(raw_record, dict):
            raise ValueError(f"ZIP source record {index} must be an object.")

        record = _normalize_record(
            raw_record,
            source_name,
            source_year,
            source_version,
            dataset_version,
            imported_at,
            index,
        )
        if record["zip_code"] in seen_zip_codes:
            raise ValueError(f"Duplicate ZIP code: {record['zip_code']}")
        seen_zip_codes.add(record["zip_code"])
        records.append(record)
    return records


def _load_raw_records(source_path: Path, source_format: str) -> list[dict[str, Any]]:
    resolved_format = source_format.lower()
    if resolved_format == "auto":
        suffix = source_path.suffix.lower()
        if suffix == ".csv":
            resolved_format = "csv"
        elif suffix == ".json":
            resolved_format = "json"
        else:
            raise ValueError(f"Cannot infer source format from extension: {source_path}")

    if resolved_format == "json":
        return json.loads(source_path.read_text(encoding="utf-8"))
    if resolved_format == "csv":
        with source_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            if not reader.fieldnames:
                raise ValueError("ZIP source CSV must include a header row.")
            return [dict(row) for row in reader]

    raise ValueError(f"Unsupported source format: {source_format}")


def _normalize_record(
    raw_record: dict[str, Any],
    source_name: str,
    source_year: str | None,
    source_version: str | None,
    dataset_version: str | None,
    imported_at: str,
    index: int,
) -> dict[str, Any]:
    zip_code = _normalize_zip(raw_record.get("zip_code") or raw_record.get("zip"), index)
    primary_city = _required_text(raw_record.get("primary_city") or raw_record.get("city"), "city", index)
    state = _required_text(raw_record.get("state"), "state", index).upper()
    if len(state) != 2 or not state.isalpha():
        raise ValueError(f"Record {index} has invalid state: {state!r}")

    latitude = _coordinate(raw_record.get("latitude"), "latitude", -90, 90, index)
    longitude = _coordinate(raw_record.get("longitude"), "longitude", -180, 180, index)
    default_zoom = _default_zoom(raw_record.get("default_zoom"), index)

    return {
        "zip_code": zip_code,
        "primary_city": primary_city,
        "state": state,
        "county": _optional_text(raw_record.get("county")),
        "county_fips": _optional_text(raw_record.get("county_fips")),
        "latitude": latitude,
        "longitude": longitude,
        "timezone": _optional_text(raw_record.get("timezone")),
        "default_zoom": default_zoom,
        "source": _optional_text(raw_record.get("source")) or source_name,
        "source_year": _optional_text(raw_record.get("source_year")) or source_year,
        "source_version": _optional_text(raw_record.get("source_version")) or source_version,
        "dataset_version": _optional_text(raw_record.get("dataset_version")) or dataset_version,
        "imported_at": _optional_text(raw_record.get("imported_at")) or imported_at,
        "location_type": _optional_text(raw_record.get("location_type")) or "zip",
        "is_zcta": 1 if _truthy(raw_record.get("is_zcta")) else 0,
        "confidence": _optional_text(raw_record.get("confidence")) or "seed",
    }


def _normalize_zip(value: Any, index: int) -> str:
    zip_code = _required_text(value, "zip_code", index)
    if zip_code.isdigit():
        zip_code = zip_code.zfill(5)
    if len(zip_code) != 5 or not zip_code.isdigit():
        raise ValueError(f"Record {index} has invalid ZIP code: {zip_code!r}")
    return zip_code


def _required_text(value: Any, field_name: str, index: int) -> str:
    text = _optional_text(value)
    if not text:
        raise ValueError(f"Record {index} is missing required field: {field_name}")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = _optional_text(value)
    if not text:
        return False
    return text.lower() in {"1", "true", "t", "yes", "y"}


def _coordinate(value: Any, field_name: str, minimum: float, maximum: float, index: int) -> float:
    try:
        coordinate = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Record {index} has invalid {field_name}: {value!r}") from exc

    if not math.isfinite(coordinate) or coordinate < minimum or coordinate > maximum:
        raise ValueError(f"Record {index} has out-of-range {field_name}: {value!r}")
    return coordinate


def _default_zoom(value: Any, index: int) -> int:
    if value is None or value == "":
        return 9
    try:
        default_zoom = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Record {index} has invalid default_zoom: {value!r}") from exc
    if default_zoom < 0 or default_zoom > 22:
        raise ValueError(f"Record {index} has out-of-range default_zoom: {value!r}")
    return default_zoom


def _write_database(db_path: Path, records: list[dict[str, Any]]) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.executescript(ZIP_LOOKUP_SCHEMA)
        connection.executemany(
            """
            INSERT INTO zip_locations (
                zip_code,
                primary_city,
                state,
                county,
                county_fips,
                latitude,
                longitude,
                timezone,
                default_zoom,
                source,
                source_year,
                source_version,
                dataset_version,
                imported_at,
                location_type,
                is_zcta,
                confidence
            ) VALUES (
                :zip_code,
                :primary_city,
                :state,
                :county,
                :county_fips,
                :latitude,
                :longitude,
                :timezone,
                :default_zoom,
                :source,
                :source_year,
                :source_version,
                :dataset_version,
                :imported_at,
                :location_type,
                :is_zcta,
                :confidence
            )
            """,
            records,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO city_locations (
                primary_city,
                state,
                county,
                latitude,
                longitude,
                default_zoom,
                source,
                source_version,
                dataset_version,
                imported_at,
                confidence
            ) VALUES (
                :primary_city,
                :state,
                :county,
                :latitude,
                :longitude,
                :default_zoom,
                :source,
                :source_version,
                :dataset_version,
                :imported_at,
                :confidence
            )
            """,
            records,
        )


def _validate_database(
    db_path: Path,
    expected_zip_count: int,
    sentinel_zip_codes: list[str] | None,
) -> None:
    with sqlite3.connect(db_path) as connection:
        zip_count = connection.execute("SELECT COUNT(*) FROM zip_locations").fetchone()[0]
        if zip_count != expected_zip_count:
            raise ValueError(f"Expected {expected_zip_count} ZIP rows, imported {zip_count}.")
        for zip_code in sentinel_zip_codes or []:
            normalized_zip_code = _normalize_zip(zip_code, 0)
            exists = connection.execute(
                "SELECT 1 FROM zip_locations WHERE zip_code = ?",
                (normalized_zip_code,),
            ).fetchone()
            if exists is None:
                raise ValueError(f"Sentinel ZIP code missing after import: {normalized_zip_code}")


def _city_location_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        return connection.execute("SELECT COUNT(*) FROM city_locations").fetchone()[0]


def _write_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    temp_manifest_path = _temporary_path(manifest_path.parent, ".json.tmp")
    try:
        temp_manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_manifest_path.replace(manifest_path)
    finally:
        temp_manifest_path.unlink(missing_ok=True)


def _temporary_path(directory: Path, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(delete=False, dir=directory, suffix=suffix) as temp_file:
        return Path(temp_file.name)


def _sha256_file(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def _parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_data_dir = repo_root / "backend" / "app" / "data"
    parser = argparse.ArgumentParser(description="Build the bundled Molecast location lookup SQLite database.")
    parser.add_argument("--input", type=Path, default=default_data_dir / "zip_codes.json")
    parser.add_argument("--output", type=Path, default=default_data_dir / "location_lookup.sqlite3")
    parser.add_argument("--manifest", type=Path, default=default_data_dir / "location_lookup_manifest.json")
    parser.add_argument("--source-name", default="molecast-seed-zip-codes-json")
    parser.add_argument("--source-year", default=None)
    parser.add_argument("--source-version", default="phase-1-seed")
    parser.add_argument("--source-format", choices=("auto", "json", "csv"), default="auto")
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument(
        "--sentinel-zip",
        dest="sentinel_zip_codes",
        action="append",
        default=["49002", "49005"],
        help="ZIP code that must exist after import. Repeat for multiple sentinels.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = import_location_lookup(
        source_json=args.input,
        output_db=args.output,
        manifest_path=args.manifest,
        source_name=args.source_name,
        source_year=args.source_year,
        source_version=args.source_version,
        source_format=args.source_format,
        dataset_version=args.dataset_version,
        sentinel_zip_codes=args.sentinel_zip_codes,
    )
    print(
        "Imported "
        f"{manifest['row_counts']['zip_locations']} ZIP rows and "
        f"{manifest['row_counts']['city_locations']} city rows to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
