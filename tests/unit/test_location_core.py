import hashlib
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import locations as locations_route
from app.database import Base
from app.db_init import ensure_location_schema
from app.models.location import Location
from app.schemas.location import ActiveLocationDirectUpdate, LocationCreate
from app.schemas.location_resolver import NwsPointPreviewRequest
from app.services import location_service
from app.services.location_resolver_service import LocationResolverService, office_name_for
from app.services.nws_points_service import (
    NwsPointsFetchError,
    NwsPointsMetadata,
    parse_points_metadata,
)
from app.services.zip_lookup_service import InvalidZipCodeError


def _settings():
    return SimpleNamespace(
        default_location_data={
            "label": "Portage, MI 49002",
            "name": "Portage, MI 49002",
            "city": "Portage",
            "state": "MI",
            "county": "Kalamazoo",
            "zip_code": "49002",
            "latitude": 42.2012,
            "longitude": -85.58,
            "default_zoom": 9,
            "is_primary": True,
        },
        default_location_postal_code="49002",
        default_location_latitude=42.2012,
        default_location_longitude=-85.58,
        default_location_zoom=9,
    )


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestingSessionLocal() as session:
        yield session
    Base.metadata.drop_all(bind=engine)


class SuccessfulPointsService:
    def fetch_points_metadata(self, latitude: float, longitude: float) -> NwsPointsMetadata:
        return NwsPointsMetadata(
            nws_office="GRR",
            nws_grid_x=55,
            nws_grid_y=44,
            forecast_zone="MIZ072",
            county_zone="MIC077",
            fire_weather_zone="MIZ072",
            timezone="America/Detroit",
        )


class FailingPointsService:
    def fetch_points_metadata(self, latitude: float, longitude: float) -> NwsPointsMetadata:
        raise NwsPointsFetchError("points failed")


class RecordingPointsService:
    def __init__(self) -> None:
        self.calls = []

    def fetch_points_metadata(self, latitude: float, longitude: float) -> NwsPointsMetadata:
        self.calls.append((latitude, longitude))
        return NwsPointsMetadata(
            nws_office="GRR",
            nws_grid_x=55,
            nws_grid_y=44,
            forecast_zone="MIZ072",
            county_zone="MIC077",
            fire_weather_zone="MIZ072",
            timezone="America/Detroit",
        )


def test_default_active_location_exists_when_none_saved(db) -> None:
    location = location_service.get_active_location(db, _settings())

    assert location.label == "Portage, MI 49002"
    assert location.is_primary is True
    assert location.default_zoom == 9


def test_get_active_location_route_returns_default_payload(db, monkeypatch) -> None:
    monkeypatch.setattr(locations_route, "settings", _settings())

    payload = locations_route.get_active_location(db)

    assert payload["label"] == "Portage, MI 49002"
    assert payload["using_default"] is True
    assert payload["default_zoom"] == 9


def test_put_active_location_persists_new_primary_with_metadata(db, monkeypatch) -> None:
    monkeypatch.setattr(location_service, "nws_points_service", SuccessfulPointsService())
    settings = _settings()
    location_service.get_active_location(db, settings)

    location = location_service.set_active_location_from_payload(
        db,
        settings,
        {
            "latitude": 42.2917,
            "longitude": -85.5872,
            "label": "Kalamazoo, MI",
            "name": "Kalamazoo",
            "city": "Kalamazoo",
            "county": "Kalamazoo",
            "state": "MI",
            "zip_code": "49007",
            "default_zoom": 10,
        },
    )

    assert location.is_primary is True
    assert location.label == "Kalamazoo, MI"
    assert location.default_zoom == 10
    assert location.nws_office == "GRR"
    assert location.nws_grid_x == 55
    assert location.nws_grid_y == 44
    assert location.forecast_zone == "MIZ072"
    assert location.county_zone == "MIC077"
    assert location.fire_weather_zone == "MIZ072"
    assert location.nws_points_updated_at is not None
    assert db.query(Location).filter(Location.is_primary.is_(True)).count() == 1


def test_points_failure_still_saves_active_location(db, monkeypatch) -> None:
    monkeypatch.setattr(location_service, "nws_points_service", FailingPointsService())

    location = location_service.set_active_location_from_payload(
        db,
        _settings(),
        {"latitude": 40.0, "longitude": -86.0, "label": "Manual point"},
    )

    assert location.label == "Manual point"
    assert location.is_primary is True
    assert location.nws_points_updated_at is None


def test_invalid_active_location_payloads_rejected() -> None:
    with pytest.raises(ValidationError):
        ActiveLocationDirectUpdate(latitude=91, longitude=-85)
    with pytest.raises(ValidationError):
        ActiveLocationDirectUpdate(latitude=42, longitude=-181)
    with pytest.raises(ValidationError):
        ActiveLocationDirectUpdate(latitude=42, longitude=-85, default_zoom=23)
    with pytest.raises(ValidationError):
        ActiveLocationDirectUpdate(latitude=42, longitude=-85, zip_code="49A02")


def test_nws_point_preview_payload_rejects_invalid_coordinates() -> None:
    with pytest.raises(ValidationError):
        NwsPointPreviewRequest(latitude=91, longitude=-85)
    with pytest.raises(ValidationError):
        NwsPointPreviewRequest(latitude=42, longitude=-181)


def test_active_location_payload_trims_zip_code_whitespace() -> None:
    payload = ActiveLocationDirectUpdate(latitude=42, longitude=-85, zip_code=" 49002\t")

    assert payload.zip_code == "49002"


def test_location_create_trims_zip_code_whitespace() -> None:
    payload = LocationCreate(
        label="Portage, MI 49002",
        city="Portage",
        state="MI",
        county="Kalamazoo",
        zip_code="\n49002 ",
        latitude=42.2012,
        longitude=-85.58,
    )

    assert payload.zip_code == "49002"


def test_location_status_reports_missing_metadata(db) -> None:
    status = location_service.get_location_status(db, _settings())

    assert status["active_location"]["label"] == "Portage, MI 49002"
    assert status["using_default"] is True
    assert status["nws_metadata_status"] == "missing"
    assert "metadata is missing" in status["warning"]


def test_zip_lookup_returns_local_location_data() -> None:
    lookup = locations_route.lookup_zip_code("49002")

    assert lookup.zip == "49002"
    assert lookup.zip_code == "49002"
    assert lookup.city == "Portage"
    assert lookup.state == "MI"
    assert lookup.county == "Kalamazoo"
    assert lookup.county_fips is None
    assert lookup.default_zoom == 9


def test_zip_lookup_route_response_includes_county_fips(monkeypatch) -> None:
    monkeypatch.setattr(
        location_service,
        "lookup_zip_code",
        lambda zip_code: SimpleNamespace(
            zip_code="10001",
            city=None,
            state="NY",
            county="New York",
            county_fips="36061",
            latitude=40.750649,
            longitude=-73.997298,
            default_zoom=9,
            source="census_gazetteer_zcta+hud_usps_zip_county",
            source_year="2025",
            source_version="2025_Gaz_zcta_national+HUD_USPS_2025_Q4",
            dataset_version="2025_Gazetteer_ZCTA+HUD_USPS_ZIP_COUNTY_2025_Q4",
            imported_at="2026-05-03T00:00:00+00:00",
            location_type="zcta",
            is_zcta=True,
            confidence="approximate+hud_primary_county",
        ),
    )

    lookup = locations_route.lookup_zip_code("10001")

    assert lookup.zip_code == "10001"
    assert lookup.city is None
    assert lookup.state == "NY"
    assert lookup.county == "New York"
    assert lookup.county_fips == "36061"


def test_zip_lookup_preserves_seed_metadata_for_49005() -> None:
    lookup = locations_route.lookup_zip_code("49005")

    assert lookup.zip == "49005"
    assert lookup.zip_code == "49005"
    assert lookup.city == "Kalamazoo"
    assert lookup.state == "MI"
    assert lookup.county == "Kalamazoo"
    assert lookup.location_type == "zip"
    assert lookup.is_zcta is False


def test_zip_lookup_returns_non_michigan_zcta_with_partial_metadata() -> None:
    lookup = locations_route.lookup_zip_code("90210")

    assert lookup.zip_code == "90210"
    assert lookup.city is None
    assert lookup.state is None
    assert lookup.county is None
    assert lookup.latitude == 34.100517
    assert lookup.longitude == -118.41463
    assert lookup.source == "census_gazetteer_zcta"
    assert lookup.source_year == "2025"
    assert lookup.location_type == "zcta"
    assert lookup.is_zcta is True
    assert lookup.confidence == "approximate"


def test_legacy_zip_lookup_route_returns_local_location_data() -> None:
    lookup = locations_route.lookup_zip_code_legacy("49005")

    assert lookup.zip == "49005"
    assert lookup.zip_code == "49005"
    assert lookup.city == "Kalamazoo"


def test_zip_lookup_accepts_zip_plus_four() -> None:
    lookup = location_service.lookup_zip_code("49002-1234")

    assert lookup is not None
    assert lookup.zip_code == "49002"


def test_zip_lookup_rejects_invalid_format() -> None:
    with pytest.raises(InvalidZipCodeError):
        location_service.lookup_zip_code("49A02")


def test_zip_lookup_route_returns_422_for_invalid_zip() -> None:
    with pytest.raises(HTTPException) as exc_info:
        locations_route.lookup_zip_code("49A02")

    assert exc_info.value.status_code == 422


def test_zip_lookup_returns_none_for_unknown_zip() -> None:
    assert location_service.lookup_zip_code("99999") is None


def test_zip_lookup_route_returns_404_for_unknown_zip() -> None:
    with pytest.raises(HTTPException) as exc_info:
        locations_route.lookup_zip_code("99999")

    assert exc_info.value.status_code == 404


def test_zip_lookup_route_does_not_mutate_active_location(db) -> None:
    settings = _settings()
    active_location = location_service.get_active_location(db, settings)
    original_payload = location_service.location_to_dict(active_location, settings)

    lookup = locations_route.lookup_zip_code("49005")

    refreshed_payload = location_service.location_to_dict(
        location_service.get_active_location(db, settings),
        settings,
    )
    assert lookup.zip_code == "49005"
    assert refreshed_payload == original_payload


def test_zip_lookup_does_not_modify_test_alert_fixture() -> None:
    fixture_path = Path("test/alerts_test.json")
    before = hashlib.sha256(fixture_path.read_bytes()).hexdigest()

    locations_route.lookup_zip_code("49002")
    locations_route.lookup_zip_code("10001")

    after = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    assert after == before


def test_nws_point_preview_reuses_points_service_and_maps_grr_office() -> None:
    points_service = RecordingPointsService()
    service = LocationResolverService(repository=SimpleNamespace(), points_service=points_service)

    preview = service.preview_nws_point(42.2012, -85.588)

    assert points_service.calls == [(42.2012, -85.588)]
    assert preview.latitude == 42.2012
    assert preview.longitude == -85.588
    assert preview.nws_office == "GRR"
    assert preview.nws_office_code == "KGRR"
    assert preview.nws_office_name == "Grand Rapids, MI"
    assert preview.nws_grid_x == 55
    assert preview.nws_grid_y == 44
    assert preview.forecast_zone == "MIZ072"
    assert preview.county_zone == "MIC077"
    assert preview.fire_weather_zone == "MIZ072"
    assert preview.timezone == "America/Detroit"
    assert preview.status == "ok"
    assert preview.updated_at is not None


def test_nws_point_preview_includes_nearest_local_location_details() -> None:
    class PreviewLocationRepository:
        def find_nearest_zip(self, latitude: float, longitude: float):
            assert latitude == 42.2012
            assert longitude == -85.588
            return SimpleNamespace(
                primary_city="Portage",
                county="Kalamazoo",
                state="MI",
                zip_code="49002",
            )

    points_service = RecordingPointsService()
    service = LocationResolverService(repository=PreviewLocationRepository(), points_service=points_service)

    preview = service.preview_nws_point(42.2012, -85.588)

    assert preview.city == "Portage"
    assert preview.county == "Kalamazoo"
    assert preview.state == "MI"
    assert preview.zip_code == "49002"


def test_nws_point_preview_office_name_falls_back_to_grid_id() -> None:
    assert office_name_for("XYZ") == "XYZ"


def test_preview_location_points_route_does_not_mutate_active_location(db, monkeypatch) -> None:
    settings = _settings()
    active_location = location_service.get_active_location(db, settings)
    original_payload = location_service.location_to_dict(active_location, settings)
    points_service = RecordingPointsService()
    service = LocationResolverService(repository=SimpleNamespace(), points_service=points_service)
    monkeypatch.setattr(locations_route, "get_location_resolver_service", lambda: service)

    preview = locations_route.preview_location_points(
        NwsPointPreviewRequest(latitude=42.2012, longitude=-85.588)
    )

    refreshed_payload = location_service.location_to_dict(
        location_service.get_active_location(db, settings),
        settings,
    )
    assert preview.nws_office == "GRR"
    assert refreshed_payload == original_payload


def test_preview_location_points_route_returns_clear_nws_errors(monkeypatch) -> None:
    class FailingPreviewService:
        def preview_nws_point(self, latitude: float, longitude: float):
            raise NwsPointsFetchError("points failed")

    monkeypatch.setattr(locations_route, "get_location_resolver_service", lambda: FailingPreviewService())

    with pytest.raises(HTTPException) as exc_info:
        locations_route.preview_location_points(
            NwsPointPreviewRequest(latitude=42.2012, longitude=-85.588)
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "points failed"


def test_schema_evolution_adds_missing_columns_without_dropping_rows() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE locations (
                    id INTEGER PRIMARY KEY,
                    label VARCHAR(120) NOT NULL,
                    city VARCHAR(80) NOT NULL,
                    state VARCHAR(2) NOT NULL,
                    county VARCHAR(80) NOT NULL,
                    zip_code VARCHAR(10) NOT NULL,
                    latitude FLOAT NOT NULL,
                    longitude FLOAT NOT NULL,
                    is_primary BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO locations (
                    id, label, city, state, county, zip_code, latitude, longitude,
                    is_primary, created_at, updated_at
                ) VALUES (
                    1, 'Portage, MI 49002', 'Portage', 'MI', 'Kalamazoo', '49002',
                    42.2012, -85.58, 1, :created_at, :updated_at
                )
                """
            ),
            {"created_at": datetime.utcnow(), "updated_at": datetime.utcnow()},
        )

    ensure_location_schema(bind=engine)
    ensure_location_schema(bind=engine)

    with engine.connect() as connection:
        row = connection.execute(text("SELECT label, default_zoom, nws_office FROM locations")).one()

    assert row.label == "Portage, MI 49002"
    assert row.default_zoom == 9
    assert row.nws_office is None


def test_points_metadata_parses_and_normalizes_zone_ids() -> None:
    metadata = parse_points_metadata(
        {
            "properties": {
                "gridId": "GRR",
                "gridX": 55,
                "gridY": "44",
                "county": "https://api.weather.gov/zones/county/MIC077",
                "forecastZone": "https://api.weather.gov/zones/forecast/MIZ072",
                "fireWeatherZone": "https://api.weather.gov/zones/fire/MIZ072",
                "timeZone": "America/Detroit",
            }
        }
    )

    assert metadata.nws_office == "GRR"
    assert metadata.nws_grid_x == 55
    assert metadata.nws_grid_y == 44
    assert metadata.county_zone == "MIC077"
    assert metadata.forecast_zone == "MIZ072"
    assert metadata.fire_weather_zone == "MIZ072"
    assert metadata.timezone == "America/Detroit"


def test_points_metadata_missing_fields_do_not_crash() -> None:
    metadata = parse_points_metadata({"properties": {"gridId": "GRR"}})

    assert metadata.nws_office == "GRR"
    assert metadata.county_zone is None
    assert metadata.nws_grid_x is None
