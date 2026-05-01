from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import locations as locations_route
from app.database import Base
from app.db_init import ensure_location_schema
from app.models.location import Location
from app.schemas.location import ActiveLocationDirectUpdate
from app.services import location_service
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


def test_location_status_reports_missing_metadata(db) -> None:
    status = location_service.get_location_status(db, _settings())

    assert status["active_location"]["label"] == "Portage, MI 49002"
    assert status["using_default"] is True
    assert status["nws_metadata_status"] == "missing"
    assert "metadata is missing" in status["warning"]


def test_zip_lookup_returns_local_location_data() -> None:
    lookup = locations_route.lookup_zip_code("49002")

    assert lookup.zip_code == "49002"
    assert lookup.city == "Portage"
    assert lookup.state == "MI"
    assert lookup.county == "Kalamazoo"
    assert lookup.default_zoom == 9


def test_zip_lookup_accepts_zip_plus_four() -> None:
    lookup = location_service.lookup_zip_code("49002-1234")

    assert lookup is not None
    assert lookup.zip_code == "49002"


def test_zip_lookup_rejects_invalid_format() -> None:
    with pytest.raises(InvalidZipCodeError):
        location_service.lookup_zip_code("49A02")


def test_zip_lookup_returns_none_for_unknown_zip() -> None:
    assert location_service.lookup_zip_code("99999") is None


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
