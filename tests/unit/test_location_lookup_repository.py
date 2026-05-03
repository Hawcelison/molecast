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


def _write_county_reference(path: Path, rows: list[tuple[str, str, str]]) -> None:
    path.write_text(
        "\n".join(
            ["USPS|GEOID|GEOIDFQ|ANSICODE|NAME"]
            + [f"{state}|{geoid}|0500000US{geoid}|00000000|{name}" for state, geoid, name in rows]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_hud_zip_county(path: Path, rows: list[tuple[str, str, float, float, float, float, str, str]]) -> None:
    path.write_text(
        "\n".join(
            ["ZIP,COUNTY,RES_RATIO,BUS_RATIO,OTH_RATIO,TOT_RATIO,USPS_ZIP_PREF_CITY,USPS_ZIP_PREF_STATE"]
            + [
                f"{zip_code},{county},{res_ratio},{bus_ratio},{oth_ratio},{tot_ratio},{city},{state}"
                for zip_code, county, res_ratio, bus_ratio, oth_ratio, tot_ratio, city, state in rows
            ]
        )
        + "\n",
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


def test_importer_enriches_zcta_rows_with_hud_zip_county_metadata(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    zcta_source = tmp_path / "gaz_zcta.txt"
    hud_source = tmp_path / "ZIP_COUNTY_2025_Q4.csv"
    county_reference = tmp_path / "gaz_counties.txt"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    _write_seed_json(source_json)
    zcta_source.write_text(
        "\n".join(
            [
                "GEOID|GEOIDFQ|ALAND|AWATER|ALAND_SQMI|AWATER_SQMI|INTPTLAT|INTPTLONG",
                "10001|860Z200US10001|1|0|0.001|0|40.750649|-73.997298",
                "49002|860Z200US49002|1|0|0.001|0|42.197202|-85.555543",
                "90210|860Z200US90210|1|0|0.001|0|34.100517|-118.41463",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_hud_zip_county(
        hud_source,
        [
            ("10001", "36061", 0.98, 0.99, 1.0, 0.98, "NEW YORK", "NY"),
            ("49002", "26077", 0.99, 0.99, 1.0, 0.99, "PORTAGE", "MI"),
            ("49005", "26077", 0.99, 0.99, 1.0, 0.99, "KALAMAZOO", "MI"),
            ("90210", "06037", 0.95, 0.97, 1.0, 0.96, "BEVERLY HILLS", "CA"),
        ],
    )
    _write_county_reference(
        county_reference,
        [
            ("CA", "06037", "Los Angeles County"),
            ("MI", "26077", "Kalamazoo County"),
            ("NY", "36061", "New York County"),
        ],
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
        hud_zip_county_path=hud_source,
        hud_source_year="2025",
        hud_source_quarter="Q4",
        hud_source_version="HUD_USPS_2025_Q4",
        hud_dataset_version="HUD_USPS_ZIP_COUNTY_2025_Q4",
        county_reference_path=county_reference,
        sentinel_zip_codes=["49002", "49005", "10001", "90210"],
    )
    repository = LocationLookupRepository(output_db)
    portage = repository.lookup_zip("49002")
    kalamazoo = repository.lookup_zip("49005")
    new_york = repository.lookup_zip("10001")
    beverly_hills = repository.lookup_zip("90210")

    assert portage is not None
    assert portage.primary_city == "Portage"
    assert portage.state == "MI"
    assert portage.county == "Kalamazoo"
    assert portage.county_fips == "26077"
    assert portage.latitude == 42.197202
    assert kalamazoo is not None
    assert kalamazoo.primary_city == "Kalamazoo"
    assert kalamazoo.state == "MI"
    assert kalamazoo.county == "Kalamazoo"
    assert kalamazoo.county_fips == "26077"
    assert new_york is not None
    assert new_york.primary_city is None
    assert new_york.state == "NY"
    assert new_york.county == "New York"
    assert new_york.county_fips == "36061"
    assert beverly_hills is not None
    assert beverly_hills.primary_city is None
    assert beverly_hills.state == "CA"
    assert beverly_hills.county == "Los Angeles"
    assert beverly_hills.county_fips == "06037"
    assert manifest["hud_usps_zip_county_source"]["rows_processed"] == 4
    assert manifest["hud_usps_zip_county_source"]["distinct_zips_processed"] == 4
    assert manifest["hud_usps_zip_county_source"]["matched_zips"] == 4
    assert manifest["hud_usps_zip_county_source"]["enriched_zips"] == 4
    assert manifest["hud_usps_zip_county_source"]["multi_county_zip_count"] == 0
    assert manifest["hud_usps_zip_county_source"]["seed_preserved_count"] == 2
    assert manifest["hud_usps_zip_county_source"]["conflict_count"] == 0
    assert manifest["hud_usps_zip_county_source"]["checksum_sha256"]
    assert manifest["county_reference_source"]["rows_processed"] == 3
    assert manifest["county_reference_source"]["checksum_sha256"]


def test_importer_ranks_multi_county_hud_rows_deterministically(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    zcta_source = tmp_path / "gaz_zcta.txt"
    hud_source = tmp_path / "ZIP_COUNTY_2025_Q4.csv"
    county_reference = tmp_path / "gaz_counties.txt"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    source_json.write_text("[]", encoding="utf-8")
    zcta_source.write_text(
        "\n".join(
            [
                "GEOID|GEOIDFQ|ALAND|AWATER|ALAND_SQMI|AWATER_SQMI|INTPTLAT|INTPTLONG",
                "77777|860Z200US77777|1|0|0.001|0|40.0|-90.0",
                "88888|860Z200US88888|1|0|0.001|0|41.0|-91.0",
                "88889|860Z200US88889|1|0|0.001|0|42.0|-92.0",
                "88890|860Z200US88890|1|0|0.001|0|43.0|-93.0",
                "88891|860Z200US88891|1|0|0.001|0|44.0|-94.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_hud_zip_county(
        hud_source,
        [
            ("77777", "01001", 0.4, 1.0, 1.0, 1.0, "IGNORED", "AL"),
            ("77777", "01003", 0.8, 0.0, 0.0, 0.0, "IGNORED", "AL"),
            ("88888", "01001", 0.5, 0.0, 0.0, 0.4, "IGNORED", "AL"),
            ("88888", "01005", 0.5, 0.0, 0.0, 0.7, "IGNORED", "AL"),
            ("88889", "01001", 0.5, 0.4, 0.0, 0.7, "IGNORED", "AL"),
            ("88889", "01007", 0.5, 0.8, 0.0, 0.7, "IGNORED", "AL"),
            ("88890", "01001", 0.5, 0.8, 0.1, 0.7, "IGNORED", "AL"),
            ("88890", "01009", 0.5, 0.8, 0.6, 0.7, "IGNORED", "AL"),
            ("88891", "01011", 0.5, 0.8, 0.6, 0.7, "IGNORED", "AL"),
            ("88891", "01001", 0.5, 0.8, 0.6, 0.7, "IGNORED", "AL"),
        ],
    )
    _write_county_reference(
        county_reference,
        [
            ("AL", "01001", "Autauga County"),
            ("AL", "01003", "Baldwin County"),
            ("AL", "01005", "Barbour County"),
            ("AL", "01007", "Bibb County"),
            ("AL", "01009", "Blount County"),
            ("AL", "01011", "Bullock County"),
        ],
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
        hud_zip_county_path=hud_source,
        hud_source_year="2025",
        hud_source_quarter="Q4",
        hud_source_version="HUD_USPS_2025_Q4",
        county_reference_path=county_reference,
        sentinel_zip_codes=["77777", "88888", "88889", "88890", "88891"],
    )
    repository = LocationLookupRepository(output_db)

    assert repository.lookup_zip("77777").county_fips == "01003"
    assert repository.lookup_zip("88888").county_fips == "01005"
    assert repository.lookup_zip("88889").county_fips == "01007"
    assert repository.lookup_zip("88890").county_fips == "01009"
    assert repository.lookup_zip("88891").county_fips == "01001"
    assert manifest["hud_usps_zip_county_source"]["multi_county_zip_count"] == 5


def test_importer_ignores_hud_city_and_handles_missing_county_mapping(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    zcta_source = tmp_path / "gaz_zcta.txt"
    hud_source = tmp_path / "ZIP_COUNTY_2025_Q4.csv"
    county_reference = tmp_path / "gaz_counties.txt"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    source_json.write_text("[]", encoding="utf-8")
    zcta_source.write_text(
        "\n".join(
            [
                "GEOID|GEOIDFQ|ALAND|AWATER|ALAND_SQMI|AWATER_SQMI|INTPTLAT|INTPTLONG",
                "30303|860Z200US30303|1|0|0.001|0|33.7529|-84.3903",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_hud_zip_county(
        hud_source,
        [("30303", "13121", 0.9, 0.9, 0.9, 0.9, "ATLANTA", "GA")],
    )
    _write_county_reference(county_reference, [("GA", "13089", "DeKalb County")])

    import_location_lookup(
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
        hud_zip_county_path=hud_source,
        hud_source_year="2025",
        hud_source_quarter="Q4",
        hud_source_version="HUD_USPS_2025_Q4",
        county_reference_path=county_reference,
        sentinel_zip_codes=["30303"],
    )
    record = LocationLookupRepository(output_db).lookup_zip("30303")

    assert record is not None
    assert record.primary_city is None
    assert record.state == "GA"
    assert record.county is None
    assert record.county_fips == "13121"


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
        "county_fips": None,
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
