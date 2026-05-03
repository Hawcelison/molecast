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
            SELECT
                zip_code,
                primary_city,
                state,
                county,
                default_zoom,
                source,
                source_year,
                source_version,
                dataset_version,
                imported_at
            FROM zip_locations
            WHERE zip_code = '49002'
            """
        ).fetchone()

    assert row[:9] == ("49002", "Portage", "MI", "Kalamazoo", 9, "test-seed", "2026", "test", "test")
    assert row[9]


def test_importer_supports_csv_source_and_sentinel_validation(tmp_path: Path) -> None:
    source_csv = tmp_path / "zip_codes.csv"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    source_csv.write_text(
        "\n".join(
            [
                "zip_code,primary_city,state,county,latitude,longitude,timezone,source,source_version,dataset_version,is_zcta,confidence",
                "10001,New York,NY,New York,40.7506,-73.9972,America/New_York,test-csv,2026q1,2026q1,1,zcta",
                "49002,Portage,MI,Kalamazoo,42.2012,-85.58,America/Detroit,test-csv,2026q1,2026q1,0,usps",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = import_location_lookup(
        source_json=source_csv,
        output_db=output_db,
        manifest_path=manifest_path,
        source_name="test-csv",
        source_year="2026",
        source_version="2026q1",
        source_format="csv",
        sentinel_zip_codes=["49002", "10001"],
    )
    record = LocationLookupRepository(output_db).lookup_zip("10001")

    assert manifest["row_counts"]["zip_locations"] == 2
    assert manifest["dataset_version"] == "2026q1"
    assert record is not None
    assert record.zip_code == "10001"
    assert record.primary_city == "New York"
    assert record.state == "NY"
    assert record.source == "test-csv"
    assert record.source_version == "2026q1"
    assert record.dataset_version == "2026q1"
    assert record.imported_at
    assert record.is_zcta is True
    assert record.confidence == "zcta"


def test_importer_merges_seed_json_with_census_zcta_gazetteer(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    zcta_source = tmp_path / "gaz_zcta.txt"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    _write_seed_json(source_json)
    zcta_source.write_text(
        "\n".join(
            [
                "GEOID|GEOIDFQ|ALAND|AWATER|ALAND_SQMI|AWATER_SQMI|INTPTLAT|INTPTLONG",
                "10001|860Z200US10001|1|0|0.001|0|40.750649|-73.997298",
                "49002|860Z200US49002|1|0|0.001|0|42.197202|-85.555543",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = import_location_lookup(
        source_json=source_json,
        output_db=output_db,
        manifest_path=manifest_path,
        source_name="test-seed",
        source_year=None,
        source_version="seed-v1",
        zcta_source_path=zcta_source,
        zcta_source_year="2025",
        zcta_source_version="2025_Gaz_zcta_national",
        zcta_dataset_version="2025_Gazetteer_ZCTA",
        sentinel_zip_codes=["49002", "49005", "10001"],
    )
    repository = LocationLookupRepository(output_db)
    seed_overlap = repository.lookup_zip("49002")
    zcta_only = repository.lookup_zip("10001")

    assert manifest["row_counts"]["zip_locations"] == 3
    assert manifest["row_counts"]["city_locations"] == 2
    assert seed_overlap is not None
    assert seed_overlap.primary_city == "Portage"
    assert seed_overlap.state == "MI"
    assert seed_overlap.county == "Kalamazoo"
    assert seed_overlap.latitude == 42.197202
    assert seed_overlap.longitude == -85.555543
    assert seed_overlap.source == "test-seed+census_gazetteer_zcta"
    assert seed_overlap.location_type == "zip_zcta"
    assert seed_overlap.is_zcta is True
    assert seed_overlap.confidence == "seed_metadata+approximate_zcta"
    assert zcta_only is not None
    assert zcta_only.primary_city is None
    assert zcta_only.state is None
    assert zcta_only.county is None
    assert zcta_only.source == "census_gazetteer_zcta"
    assert zcta_only.source_year == "2025"
    assert zcta_only.location_type == "zcta"
    assert zcta_only.is_zcta is True
    assert zcta_only.confidence == "approximate"


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
    assert record.source == "test-seed"
    assert record.dataset_version == "test"
    assert record.imported_at


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
    lookup_payload = lookup.model_dump()
    assert lookup_payload == {
        "zip_code": "49002",
        "city": "Portage",
        "state": "MI",
        "county": "Kalamazoo",
        "latitude": 42.2012,
        "longitude": -85.58,
        "default_zoom": 9,
        "source": "test-seed",
        "source_year": None,
        "source_version": "test",
        "dataset_version": "test",
        "imported_at": lookup_payload["imported_at"],
        "location_type": "zip",
        "is_zcta": False,
        "confidence": "seed",
    }
    assert lookup_payload["imported_at"]
