#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ZIP_LOOKUP_SCHEMA = """
CREATE TABLE zip_locations (
    zip_code TEXT PRIMARY KEY,
    primary_city TEXT,
    state TEXT,
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
    zcta_source_path: Path | None = None,
    zcta_source_year: str | None = None,
    zcta_source_version: str | None = None,
    zcta_dataset_version: str | None = None,
    hud_zip_county_path: Path | None = None,
    hud_source_year: str | None = None,
    hud_source_quarter: str | None = None,
    hud_source_version: str | None = None,
    hud_dataset_version: str | None = None,
    county_reference_path: Path | None = None,
) -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat()
    effective_dataset_version = dataset_version or source_version
    hud_enrichment_stats: dict[str, Any] | None = None
    county_reference_metadata: dict[str, Any] | None = None
    records = _load_records(
        source_json,
        source_name,
        source_year,
        source_version,
        effective_dataset_version,
        generated_at,
        source_format,
    )
    if zcta_source_path is not None:
        effective_zcta_dataset_version = zcta_dataset_version or zcta_source_version
        zcta_records = _load_records(
            zcta_source_path,
            "census_gazetteer_zcta",
            zcta_source_year,
            zcta_source_version,
            effective_zcta_dataset_version,
            generated_at,
            "census-zcta-gazetteer",
        )
        records = _merge_seed_and_zcta_records(records, zcta_records)
    if hud_zip_county_path is not None:
        county_reference = {}
        county_reference_rows = 0
        if county_reference_path is not None:
            county_reference, county_reference_rows = _load_census_county_reference(county_reference_path)
            county_reference_metadata = {
                "path": county_reference_path.as_posix(),
                "source_name": "census_gazetteer_counties",
                "checksum_sha256": _sha256_file(county_reference_path),
                "rows_processed": county_reference_rows,
            }
        hud_candidates = _load_hud_zip_county_records(hud_zip_county_path)
        effective_hud_dataset_version = hud_dataset_version or hud_source_version
        records, hud_enrichment_stats = _enrich_records_with_hud_zip_counties(
            records,
            hud_candidates,
            county_reference,
            hud_source_year,
            hud_source_version,
            effective_hud_dataset_version,
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
        "zcta_source": _zcta_manifest_source(
            zcta_source_path,
            zcta_source_year,
            zcta_source_version,
            zcta_dataset_version or zcta_source_version,
        ),
        "hud_usps_zip_county_source": _hud_zip_county_manifest_source(
            hud_zip_county_path,
            hud_source_year,
            hud_source_quarter,
            hud_source_version,
            hud_dataset_version or hud_source_version,
            hud_enrichment_stats,
        ),
        "county_reference_source": county_reference_metadata,
        "future_source_license": None,
        "generated_at": generated_at,
        "imported_at": generated_at,
        "row_counts": {
            "zip_locations": len(records),
            "city_locations": _city_location_count(output_db),
        },
        "checksum_sha256": checksum,
        "notes": [
            "Seed JSON rows preserve curated city/state/county metadata for current development ZIPs.",
            "Census Gazetteer ZCTA rows provide broad offline ZIP-style coordinate coverage.",
            "ZCTAs are approximate Census geographies, not USPS ZIP Code validation data.",
            "Not every valid USPS ZIP Code is represented by a Census ZCTA.",
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
        elif suffix == ".zip":
            resolved_format = "census-zcta-gazetteer"
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
    if resolved_format == "census-zcta-gazetteer":
        return _load_census_zcta_gazetteer_records(source_path)

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
    primary_city = _optional_text(raw_record.get("primary_city") or raw_record.get("city"))
    state = _optional_text(raw_record.get("state"))
    if state:
        state = state.upper()
    if state and (len(state) != 2 or not state.isalpha()):
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


def _load_census_zcta_gazetteer_records(source_path: Path) -> list[dict[str, Any]]:
    if source_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(source_path) as archive:
            text_members = [name for name in archive.namelist() if name.lower().endswith(".txt")]
            if len(text_members) != 1:
                raise ValueError("Census ZCTA Gazetteer ZIP must contain exactly one TXT file.")
            with archive.open(text_members[0]) as raw_file:
                text = raw_file.read().decode("utf-8-sig").splitlines()
    else:
        text = source_path.read_text(encoding="utf-8-sig").splitlines()

    reader = csv.DictReader(text, delimiter="|")
    required_fields = {"GEOID", "INTPTLAT", "INTPTLONG"}
    if not reader.fieldnames or not required_fields.issubset(set(reader.fieldnames)):
        raise ValueError("Census ZCTA Gazetteer source must include GEOID, INTPTLAT, and INTPTLONG columns.")

    records: list[dict[str, Any]] = []
    for row in reader:
        records.append(
            {
                "zip_code": row.get("GEOID"),
                "latitude": row.get("INTPTLAT"),
                "longitude": row.get("INTPTLONG"),
                "default_zoom": 9,
                "location_type": "zcta",
                "is_zcta": True,
                "confidence": "approximate",
            }
        )
    return records


def _load_hud_zip_county_records(source_path: Path) -> list[dict[str, Any]]:
    rows = _load_delimited_rows(source_path, ",")
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        zip_code = _normalize_zip(_field(row, "ZIP", "zip"), index)
        county_geoid = _normalize_county_geoid(_field(row, "COUNTY", "county"), index)
        records.append(
            {
                "zip_code": zip_code,
                "county_geoid": county_geoid,
                "res_ratio": _optional_ratio(_field(row, "RES_RATIO", "res_ratio"), "RES_RATIO", index),
                "tot_ratio": _optional_ratio(
                    _field(row, "TOT_RATIO", "TOTAL_RATIO", "tot_ratio", "total_ratio"),
                    "TOT_RATIO",
                    index,
                ),
                "bus_ratio": _optional_ratio(_field(row, "BUS_RATIO", "bus_ratio"), "BUS_RATIO", index),
                "oth_ratio": _optional_ratio(_field(row, "OTH_RATIO", "oth_ratio"), "OTH_RATIO", index),
                "state": _normalize_state(_field(row, "USPS_ZIP_PREF_STATE", "STATE", "state"), index),
            }
        )
    return records


def _load_census_county_reference(source_path: Path) -> tuple[dict[str, dict[str, str | None]], int]:
    rows = _load_delimited_rows(source_path, "|")
    counties: dict[str, dict[str, str | None]] = {}
    rows_processed = 0
    for index, row in enumerate(rows, start=1):
        geoid = _optional_text(_field(row, "GEOID", "county_fips", "COUNTY"))
        if not geoid:
            continue
        county_geoid = _normalize_county_geoid(geoid, index)
        state = _normalize_state(_field(row, "USPS", "state"), index)
        county_name = _county_name(_field(row, "NAME", "county"))
        counties[county_geoid] = {
            "state": state,
            "county": county_name,
        }
        rows_processed += 1
    return counties, rows_processed


def _load_delimited_rows(source_path: Path, default_delimiter: str) -> list[dict[str, Any]]:
    text_lines: list[str] = []
    if source_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(source_path) as archive:
            text_members = [
                name
                for name in archive.namelist()
                if name.lower().endswith((".csv", ".txt"))
            ]
            if not text_members:
                raise ValueError(f"Reference ZIP contains no CSV or TXT files: {source_path}")
            for member in sorted(text_members):
                with archive.open(member) as raw_file:
                    text_lines.extend(raw_file.read().decode("utf-8-sig").splitlines())
    else:
        text_lines = source_path.read_text(encoding="utf-8-sig").splitlines()

    if not text_lines:
        return []

    delimiter = "|" if "|" in text_lines[0] else default_delimiter
    reader = csv.DictReader(text_lines, delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError(f"Reference source must include a header row: {source_path}")
    return [dict(row) for row in reader]


def _field(row: dict[str, Any], *names: str) -> Any:
    fields_by_normalized_name = {str(key).strip().upper(): value for key, value in row.items()}
    for name in names:
        value = fields_by_normalized_name.get(name.strip().upper())
        if value is not None:
            return value
    return None


def _normalize_county_geoid(value: Any, index: int) -> str:
    county_geoid = _required_text(value, "county", index)
    if county_geoid.isdigit():
        county_geoid = county_geoid.zfill(5)
    if len(county_geoid) != 5 or not county_geoid.isdigit():
        raise ValueError(f"Record {index} has invalid county GEOID: {county_geoid!r}")
    return county_geoid


def _normalize_state(value: Any, index: int) -> str | None:
    state = _optional_text(value)
    if not state:
        return None
    state = state.upper()
    if len(state) != 2 or not state.isalpha():
        raise ValueError(f"Record {index} has invalid state: {state!r}")
    return state


def _optional_ratio(value: Any, field_name: str, index: int) -> float | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        ratio = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Record {index} has invalid {field_name}: {value!r}") from exc
    if not math.isfinite(ratio):
        raise ValueError(f"Record {index} has invalid {field_name}: {value!r}")
    return ratio


def _county_name(value: Any) -> str | None:
    county = _optional_text(value)
    if not county:
        return None
    if county.lower().endswith(" county"):
        return county[:-7].strip() or county
    return county


def _merge_seed_and_zcta_records(
    seed_records: list[dict[str, Any]],
    zcta_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records_by_zip = {record["zip_code"]: dict(record) for record in seed_records}
    for zcta_record in zcta_records:
        existing = records_by_zip.get(zcta_record["zip_code"])
        if existing is None:
            records_by_zip[zcta_record["zip_code"]] = dict(zcta_record)
            continue

        records_by_zip[zcta_record["zip_code"]] = _merge_seed_record_with_zcta(existing, zcta_record)

    return [records_by_zip[zip_code] for zip_code in sorted(records_by_zip)]


def _enrich_records_with_hud_zip_counties(
    records: list[dict[str, Any]],
    hud_candidates: list[dict[str, Any]],
    county_reference: dict[str, dict[str, str | None]],
    hud_source_year: str | None,
    hud_source_version: str | None,
    hud_dataset_version: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates_by_zip: dict[str, list[dict[str, Any]]] = {}
    for candidate in hud_candidates:
        candidates_by_zip.setdefault(candidate["zip_code"], []).append(candidate)

    records_by_zip = {record["zip_code"]: dict(record) for record in records}
    matched_zip_count = 0
    enriched_zip_count = 0
    seed_preserved_count = 0
    conflict_count = 0

    for zip_code, candidates in candidates_by_zip.items():
        record = records_by_zip.get(zip_code)
        if record is None:
            continue
        matched_zip_count += 1
        original_record = dict(record)
        primary_candidate = _primary_hud_county_candidate(candidates)
        county_ref = county_reference.get(primary_candidate["county_geoid"], {})
        hud_state = county_ref.get("state") or primary_candidate.get("state")
        hud_county = county_ref.get("county")
        county_geoid = primary_candidate["county_geoid"]

        if record.get("state") and hud_state and record["state"] != hud_state:
            conflict_count += 1
        elif record.get("county") and hud_county and _county_name(record["county"]) != _county_name(hud_county):
            conflict_count += 1

        if not record.get("county_fips"):
            record["county_fips"] = county_geoid
        if not record.get("state") and hud_state:
            record["state"] = hud_state
        if not record.get("county") and hud_county:
            record["county"] = hud_county

        if record != original_record:
            enriched_zip_count += 1
            record["source"] = _combine_labels(record.get("source"), "hud_usps_zip_county")
            record["source_year"] = _combine_labels(record.get("source_year"), hud_source_year)
            record["source_version"] = _combine_labels(record.get("source_version"), hud_source_version)
            record["dataset_version"] = _combine_labels(record.get("dataset_version"), hud_dataset_version)
            record["confidence"] = _combine_labels(record.get("confidence"), "hud_primary_county")
        if original_record.get("primary_city") or original_record.get("state") or original_record.get("county"):
            seed_preserved_count += 1

        records_by_zip[zip_code] = record

    return [records_by_zip[zip_code] for zip_code in sorted(records_by_zip)], {
        "rows_processed": len(hud_candidates),
        "distinct_zips_processed": len(candidates_by_zip),
        "matched_zips": matched_zip_count,
        "enriched_zips": enriched_zip_count,
        "multi_county_zip_count": sum(
            1
            for candidates in candidates_by_zip.values()
            if len({candidate["county_geoid"] for candidate in candidates}) > 1
        ),
        "seed_preserved_count": seed_preserved_count,
        "conflict_count": conflict_count,
        "limitations": [
            "HUD-USPS ZIP-County rows relate USPS ZIP Codes to counties using address ratios.",
            "HUD-USPS ZIP-County data is not authoritative postal city-name data; city fields are ignored.",
            "ZIP Codes can span multiple counties; Molecast stores one deterministic primary county.",
            "HUD-USPS crosswalk files may omit some USPS ZIP Codes.",
            "This import enriches only existing Molecast lookup rows with coordinates.",
        ],
    }


def _primary_hud_county_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        candidates,
        key=lambda candidate: (
            -_ratio_sort_value(candidate.get("res_ratio")),
            -_ratio_sort_value(candidate.get("tot_ratio")),
            -_ratio_sort_value(candidate.get("bus_ratio")),
            -_ratio_sort_value(candidate.get("oth_ratio")),
            candidate["county_geoid"],
        ),
    )[0]


def _ratio_sort_value(value: Any) -> float:
    if value is None:
        return -1.0
    return float(value)


def _merge_seed_record_with_zcta(seed_record: dict[str, Any], zcta_record: dict[str, Any]) -> dict[str, Any]:
    merged = dict(seed_record)
    merged["latitude"] = zcta_record["latitude"]
    merged["longitude"] = zcta_record["longitude"]
    merged["source"] = _combine_labels(seed_record.get("source"), zcta_record.get("source"))
    merged["source_year"] = zcta_record.get("source_year") or seed_record.get("source_year")
    merged["source_version"] = _combine_labels(seed_record.get("source_version"), zcta_record.get("source_version"))
    merged["dataset_version"] = _combine_labels(seed_record.get("dataset_version"), zcta_record.get("dataset_version"))
    merged["imported_at"] = zcta_record.get("imported_at") or seed_record.get("imported_at")
    merged["location_type"] = "zip_zcta"
    merged["is_zcta"] = 1
    merged["confidence"] = "seed_metadata+approximate_zcta"
    return merged


def _combine_labels(left: Any, right: Any) -> str | None:
    left_text = _optional_text(left)
    right_text = _optional_text(right)
    if left_text and right_text and left_text != right_text:
        return f"{left_text}+{right_text}"
    return left_text or right_text


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
    city_records = [record for record in records if record.get("primary_city") and record.get("state")]
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
            city_records,
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


def _zcta_manifest_source(
    zcta_source_path: Path | None,
    source_year: str | None,
    source_version: str | None,
    dataset_version: str | None,
) -> dict[str, Any] | None:
    if zcta_source_path is None:
        return None
    return {
        "path": zcta_source_path.as_posix(),
        "source_name": "census_gazetteer_zcta",
        "source_year": source_year,
        "source_version": source_version,
        "dataset_version": dataset_version,
        "checksum_sha256": _sha256_file(zcta_source_path),
        "download_url": (
            "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
            "2025_Gazetteer/2025_Gaz_zcta_national.zip"
        )
        if source_version == "2025_Gaz_zcta_national"
        else None,
    }


def _hud_zip_county_manifest_source(
    hud_zip_county_path: Path | None,
    source_year: str | None,
    source_quarter: str | None,
    source_version: str | None,
    dataset_version: str | None,
    enrichment_stats: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if hud_zip_county_path is None:
        return None
    return {
        "path": hud_zip_county_path.as_posix(),
        "source_name": "hud_usps_zip_county",
        "source_year": source_year,
        "source_quarter": source_quarter,
        "source_version": source_version,
        "dataset_version": dataset_version,
        "checksum_sha256": _sha256_file(hud_zip_county_path),
        "download_url": "https://www.huduser.gov/portal/datasets/usps_crosswalk.html",
        **(enrichment_stats or {}),
    }


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
    parser.add_argument("--source-format", choices=("auto", "json", "csv", "census-zcta-gazetteer"), default="auto")
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--zcta-input", type=Path, default=None)
    parser.add_argument("--zcta-source-year", default=None)
    parser.add_argument("--zcta-source-version", default=None)
    parser.add_argument("--zcta-dataset-version", default=None)
    parser.add_argument("--hud-zip-county-input", type=Path, default=None)
    parser.add_argument("--hud-source-year", default=None)
    parser.add_argument("--hud-source-quarter", default=None)
    parser.add_argument("--hud-source-version", default=None)
    parser.add_argument("--hud-dataset-version", default=None)
    parser.add_argument("--county-reference-input", type=Path, default=None)
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
        zcta_source_path=args.zcta_input,
        zcta_source_year=args.zcta_source_year,
        zcta_source_version=args.zcta_source_version,
        zcta_dataset_version=args.zcta_dataset_version,
        hud_zip_county_path=args.hud_zip_county_input,
        hud_source_year=args.hud_source_year,
        hud_source_quarter=args.hud_source_quarter,
        hud_source_version=args.hud_source_version,
        hud_dataset_version=args.hud_dataset_version,
        county_reference_path=args.county_reference_input,
    )
    print(
        "Imported "
        f"{manifest['row_counts']['zip_locations']} ZIP rows and "
        f"{manifest['row_counts']['city_locations']} city rows to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
