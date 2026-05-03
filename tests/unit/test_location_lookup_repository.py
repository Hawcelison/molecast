from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.repositories.location_lookup_repository import LocationLookupRepository
from app.services.zip_lookup_service import SQLiteZipCodeProvider, ZipLookupService
from scripts.import_location_lookup import import_location_lookup


def _write_seed_json(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "zip_code": "49002",
                    "city": "Portage",
                    "state": "mi",
                    "county": "Kalamazoo",
                    "latitude": 42.2012,
                    "longitude": -85.58,
                    "default_zoom": 9,
                },
                {
                    "zip_code": "49005",
                    "city": "Kalamazoo",
                    "state": "MI",
                    "county": "Kalamazoo",
                    "latitude": 42.2918,
                    "longitude": -85.5874,
                    "default_zoom": 9,
                },
            ]
        ),
        encoding="utf-8",
    )


def test_importer_creates_lookup_database_from_zip_json(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    _write_seed_json(source_json)

    manifest = import_location_lookup(
        source_json=source_json,
        output_db=output_db,
        manifest_path=manifest_path,
        source_name="test-seed",
        source_year="2026",
        source_version="test",
    )

    assert output_db.exists()
    assert manifest_path.exists()
    assert manifest["row_counts"]["zip_locations"] == 2
    assert manifest["row_counts"]["city_locations"] == 2
    assert manifest["checksum_sha256"]

    with sqlite3.connect(output_db) as connection:
        row = connection.execute(
            """
            SELECT zip_code, primary_city, state, county, default_zoom, source, source_year
            FROM zip_locations
            WHERE zip_code = '49002'
            """
        ).fetchone()

    assert row == ("49002", "Portage", "MI", "Kalamazoo", 9, "test-seed", "2026")


def test_repository_returns_exact_zip_record(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    _write_seed_json(source_json)
    import_location_lookup(source_json, output_db, manifest_path, "test-seed", None, "test")

    record = LocationLookupRepository(output_db).lookup_zip("49005")

    assert record is not None
    assert record.zip_code == "49005"
    assert record.primary_city == "Kalamazoo"
    assert record.state == "MI"
    assert record.county == "Kalamazoo"
    assert record.latitude == 42.2918
    assert record.longitude == -85.5874


def test_repository_returns_nearest_zip_within_preview_range(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    _write_seed_json(source_json)
    import_location_lookup(source_json, output_db, manifest_path, "test-seed", None, "test")

    record = LocationLookupRepository(output_db).find_nearest_zip(42.205, -85.575)

    assert record is not None
    assert record.zip_code == "49002"
    assert record.primary_city == "Portage"


def test_repository_returns_none_when_nearest_zip_is_out_of_preview_range(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    _write_seed_json(source_json)
    import_location_lookup(source_json, output_db, manifest_path, "test-seed", None, "test")

    assert LocationLookupRepository(output_db).find_nearest_zip(41.0, -86.5, max_distance_miles=5) is None


def test_repository_returns_none_for_missing_database(tmp_path: Path) -> None:
    assert LocationLookupRepository(tmp_path / "missing.sqlite3").lookup_zip("49002") is None


def test_repository_returns_none_for_missing_zip(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    _write_seed_json(source_json)
    import_location_lookup(source_json, output_db, manifest_path, "test-seed", None, "test")

    assert LocationLookupRepository(output_db).lookup_zip("99999") is None


def test_zip_lookup_service_keeps_frontend_response_contract(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    _write_seed_json(source_json)
    import_location_lookup(source_json, output_db, manifest_path, "test-seed", None, "test")
    service = ZipLookupService(SQLiteZipCodeProvider(output_db))

    lookup = service.lookup(" 49002 ")

    assert lookup is not None
    assert lookup.model_dump() == {
        "zip_code": "49002",
        "city": "Portage",
        "state": "MI",
        "county": "Kalamazoo",
        "latitude": 42.2012,
        "longitude": -85.58,
        "default_zoom": 9,
    }
