from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes import locations as locations_route
from app.geocoders.base import (
    AddressGeocodeCandidate,
    AddressGeocodeRequest,
    AddressGeocodeResponse,
    AddressGeocoderUnavailable,
)
from app.repositories.location_lookup_repository import LocationLookupRepository
from app.services.location_resolver_service import LocationResolverService
from scripts.import_location_lookup import import_location_lookup


class FakeAddressLookupService:
    def __init__(self, should_fail: bool = False) -> None:
        self.calls: list[AddressGeocodeRequest] = []
        self.should_fail = should_fail

    def lookup(self, request: AddressGeocodeRequest) -> AddressGeocodeResponse:
        self.calls.append(request)
        if self.should_fail:
            raise AddressGeocoderUnavailable("Address provider unavailable.")
        return AddressGeocodeResponse(
            query=request.address or "",
            provider="fake",
            count=1,
            candidates=[
                AddressGeocodeCandidate(
                    ref="census:123:left:0",
                    matched_address="4222 FIRESIDE AVE, PORTAGE, MI, 49002",
                    display_label="Portage, MI 49002",
                    latitude=42.1976,
                    longitude=-85.5386,
                    city="Portage",
                    state="MI",
                    zip_code="49002",
                    source="census",
                    accuracy="address_range_interpolated",
                    match_quality="matched",
                )
            ],
            attribution="Fake",
        )


def test_search_endpoint_returns_zip_prefix_results() -> None:
    response = locations_route.search_locations(q="490", limit=8, search_type=None)

    assert response.query == "490"
    assert response.count >= 2
    assert {"zip:49002", "zip:49005"}.issubset({result.ref for result in response.results})
    assert all(result.kind == "zip" for result in response.results)


def test_search_endpoint_returns_exact_zip_first() -> None:
    response = locations_route.search_locations(q="49002", limit=8, search_type=None)

    assert response.count >= 1
    assert response.results[0].ref == "zip:49002"
    assert response.results[0].zip == "49002"
    assert response.results[0].city == "Portage"


def test_search_endpoint_returns_city_prefix_results() -> None:
    response = locations_route.search_locations(q="Port", limit=8, search_type=None)

    assert response.count >= 1
    assert response.results[0].kind == "city"
    assert response.results[0].city == "Portage"
    assert response.results[0].state == "MI"
    assert response.results[0].county == "Kalamazoo County"


def test_search_endpoint_returns_kalamazoo_city_result() -> None:
    response = locations_route.search_locations(q="Kalam", limit=8, search_type=None)

    assert response.count >= 1
    assert response.results[0].kind == "city"
    assert response.results[0].city == "Kalamazoo"


def test_search_endpoint_supports_city_state_query() -> None:
    response = locations_route.search_locations(q=" Portage  MI ", limit=8, search_type=None)

    assert response.query == "Portage MI"
    assert response.count >= 1
    assert response.results[0].kind == "city"
    assert response.results[0].city == "Portage"
    assert response.results[0].state == "MI"


def test_search_endpoint_type_zip_only_filters_results() -> None:
    response = locations_route.search_locations(q="490", limit=8, search_type="zip")

    assert response.count >= 2
    assert {result.kind for result in response.results} == {"zip"}


def test_search_endpoint_type_city_only_filters_results() -> None:
    response = locations_route.search_locations(q="Port", limit=8, search_type="city")

    assert response.count >= 1
    assert {result.kind for result in response.results} == {"city"}


def test_search_service_returns_address_results_for_address_like_query() -> None:
    address_service = FakeAddressLookupService()
    service = LocationResolverService(
        LocationLookupRepository(Path("backend/app/data/location_lookup.sqlite3")),
        address_service=address_service,
    )

    response = service.search("4222 Fireside Ave Portage MI", limit=8, types="address")

    assert response.count == 1
    assert response.results[0].kind == "address"
    assert response.results[0].label == "4222 FIRESIDE AVE, PORTAGE, MI, 49002"
    assert response.results[0].city == "Portage"
    assert response.results[0].state == "MI"
    assert response.results[0].zip == "49002"
    assert response.results[0].default_zoom == 14
    assert address_service.calls[0].address == "4222 Fireside Ave Portage MI"


def test_search_service_skips_address_provider_for_city_like_query() -> None:
    address_service = FakeAddressLookupService()
    service = LocationResolverService(
        LocationLookupRepository(Path("backend/app/data/location_lookup.sqlite3")),
        address_service=address_service,
    )

    response = service.search("Portage MI", limit=8, types="address")

    assert response.count == 0
    assert address_service.calls == []


@pytest.mark.parametrize("query", ["4222", "42222"])
def test_search_service_does_not_use_address_provider_for_short_numeric_queries(query: str) -> None:
    address_service = FakeAddressLookupService()
    service = LocationResolverService(
        LocationLookupRepository(Path("backend/app/data/location_lookup.sqlite3")),
        address_service=address_service,
    )

    response = service.search(query, limit=8, types="zip,city,address")

    assert response.warnings == []
    assert address_service.calls == []


def test_search_service_reports_address_provider_warning_without_breaking_local_results() -> None:
    address_service = FakeAddressLookupService(should_fail=True)
    service = LocationResolverService(
        LocationLookupRepository(Path("backend/app/data/location_lookup.sqlite3")),
        address_service=address_service,
    )

    response = service.search("49002 4222 Fireside", limit=8, types="zip,address")

    assert response.count >= 1
    assert response.results[0].kind == "zip"
    assert response.warnings == ["address_search_unavailable"]
    assert address_service.calls[0].address == "49002 4222 Fireside"


def test_search_endpoint_limit_is_applied() -> None:
    response = locations_route.search_locations(q="49002", limit=1, search_type=None)

    assert response.count == 1
    assert response.results[0].ref == "zip:49002"


def test_search_service_caps_large_limit(tmp_path: Path) -> None:
    source_json = tmp_path / "zip_codes.json"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    source_json.write_text(
        json.dumps(
            [
                {
                    "zip_code": str(10000 + index),
                    "city": f"City {index:02d}",
                    "state": "MI",
                    "county": "Kalamazoo",
                    "latitude": 42.0 + (index / 1000),
                    "longitude": -85.0 - (index / 1000),
                    "default_zoom": 9,
                }
                for index in range(25)
            ]
        ),
        encoding="utf-8",
    )
    import_location_lookup(source_json, output_db, manifest_path, "test-seed", None, "test")
    service = LocationResolverService(LocationLookupRepository(output_db))

    response = service.search("10", limit=999, types="zip")

    assert response.count == 20
    assert response.results[0].ref == "zip:10000"
    assert response.results[-1].ref == "zip:10019"


def test_city_search_uses_imported_csv_city_rows(tmp_path: Path) -> None:
    source_csv = tmp_path / "zip_codes.csv"
    output_db = tmp_path / "location_lookup.sqlite3"
    manifest_path = tmp_path / "location_lookup_manifest.json"
    source_csv.write_text(
        "\n".join(
            [
                "zip_code,primary_city,state,county,latitude,longitude,source,source_version,dataset_version",
                "10001,New York,NY,New York,40.7506,-73.9972,test-csv,2026q1,2026q1",
                "90210,Beverly Hills,CA,Los Angeles,34.0901,-118.4065,test-csv,2026q1,2026q1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    import_location_lookup(
        source_csv,
        output_db,
        manifest_path,
        "test-csv",
        "2026",
        "2026q1",
        source_format="csv",
        sentinel_zip_codes=["10001", "90210"],
    )
    service = LocationResolverService(LocationLookupRepository(output_db))

    response = service.search("Beverly", limit=8, types="city")

    assert response.count == 1
    assert response.results[0].kind == "city"
    assert response.results[0].city == "Beverly Hills"
    assert response.results[0].state == "CA"
    assert response.results[0].county == "Los Angeles County"


def test_search_endpoint_unknown_query_returns_empty_results() -> None:
    response = locations_route.search_locations(q="zzzzzz", limit=8, search_type=None)

    assert response.query == "zzzzzz"
    assert response.count == 0
    assert response.results == []


@pytest.mark.parametrize("query", ["", " ", "4", "P"])
def test_search_endpoint_short_query_returns_empty_results(query: str) -> None:
    response = locations_route.search_locations(q=query, limit=8, search_type=None)

    assert response.count == 0
    assert response.results == []


def test_search_endpoint_rejects_invalid_type_filter() -> None:
    with pytest.raises(HTTPException) as exc_info:
        locations_route.search_locations(q="490", limit=8, search_type="place")

    assert exc_info.value.status_code == 422


def test_existing_zip_lookup_routes_remain_compatible() -> None:
    assert locations_route.lookup_zip_code("49002").city == "Portage"
    assert locations_route.lookup_zip_code("49005").city == "Kalamazoo"


def test_zip_lookup_returns_imported_zcta_with_hud_county_metadata() -> None:
    response = locations_route.lookup_zip_code("10001")

    assert response.zip_code == "10001"
    assert response.city is None
    assert response.state == "NY"
    assert response.county == "New York"
    assert response.county_fips == "36061"
    assert response.latitude == 40.750649
    assert response.longitude == -73.997298
    assert response.source == "census_gazetteer_zcta+hud_usps_zip_county"
    assert response.source_year == "2025"
    assert response.location_type == "zcta"
    assert response.is_zcta is True
    assert response.confidence == "approximate+hud_primary_county"


def test_search_endpoint_returns_zcta_only_zip_without_metadata_crash() -> None:
    response = locations_route.search_locations(q="10001", limit=8, search_type="zip")

    assert response.count >= 1
    result = response.results[0]
    assert result.ref == "zip:10001"
    assert result.label == "10001 - NY - New York County"
    assert result.city is None
    assert result.state == "NY"
    assert result.county == "New York County"
    assert result.latitude == 40.750649
    assert result.longitude == -73.997298


def test_zip_lookup_route_response_includes_dataset_metadata() -> None:
    response = locations_route.lookup_zip_code("49002")

    assert response.source == "molecast-seed-zip-codes-json+census_gazetteer_zcta+hud_usps_zip_county"
    assert response.dataset_version == "phase-1-seed+2025_Gazetteer_ZCTA+HUD_USPS_ZIP_COUNTY_2025_Q4"
    assert response.imported_at
