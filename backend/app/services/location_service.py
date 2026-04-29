from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.location import Location
from app.repositories import location_repository
from app.services.nws_points_service import NwsPointsFetchError, nws_points_service
from app.services.zip_lookup_service import (
    InvalidZipCodeError,
    ZipCodeLookupResult,
    get_zip_lookup_service,
)


class DefaultLocationDeletionError(ValueError):
    pass


def ensure_default_location(db: Session, settings: Settings) -> Location:
    return location_repository.ensure_location_exists(
        db,
        settings.default_location_data,
    )


def get_default_location(db: Session, settings: Settings) -> Location:
    return ensure_default_location(db, settings)


def get_active_location(db: Session, settings: Settings) -> Location:
    return ensure_active_location(db, settings)


def is_default_location(location: Location, settings: Settings) -> bool:
    return (
        location.zip_code == settings.default_location_postal_code
        and abs(location.latitude - settings.default_location_latitude) < 0.0001
        and abs(location.longitude - settings.default_location_longitude) < 0.0001
    )


def location_to_dict(location: Location, settings: Settings) -> dict[str, Any]:
    return {
        "id": location.id,
        "label": location.label,
        "name": location.name,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "zip_code": location.zip_code,
        "city": location.city,
        "county": location.county,
        "state": location.state,
        "timezone": location.timezone,
        "default_zoom": location.default_zoom or settings.default_location_zoom,
        "nws_office": location.nws_office,
        "nws_grid_x": location.nws_grid_x,
        "nws_grid_y": location.nws_grid_y,
        "forecast_zone": location.forecast_zone,
        "county_zone": location.county_zone,
        "fire_weather_zone": location.fire_weather_zone,
        "nws_points_updated_at": location.nws_points_updated_at,
        "is_primary": location.is_primary,
        "using_default": is_default_location(location, settings),
        "created_at": location.created_at,
        "updated_at": location.updated_at,
    }


def ensure_active_location(db: Session, settings: Settings) -> Location:
    primary_location = location_repository.ensure_single_primary_location(db)
    if primary_location:
        return primary_location

    default_location = ensure_default_location(db, settings)
    return location_repository.set_primary_location(db, default_location)


def list_locations(db: Session, settings: Settings) -> list[Location]:
    ensure_active_location(db, settings)
    return list(location_repository.list_locations(db))


def create_location(
    db: Session,
    location_data: dict[str, Any],
) -> Location:
    existing_location = location_repository.get_location_by_zip_code(
        db,
        str(location_data["zip_code"]),
    )
    if existing_location:
        if location_data.get("is_primary"):
            return location_repository.set_primary_location(db, existing_location)
        return existing_location

    return location_repository.create_location(db, location_data)


def lookup_zip_code(zip_code: str) -> ZipCodeLookupResult | None:
    return get_zip_lookup_service().lookup(zip_code)


def set_active_location(db: Session, location_id: int) -> Location | None:
    location = location_repository.get_location_by_id(db, location_id)
    if location is None:
        return None

    return location_repository.set_primary_location(db, location)


def set_active_location_from_payload(
    db: Session,
    settings: Settings,
    payload_data: dict[str, Any],
) -> Location:
    location_data = _build_location_data(settings, payload_data)
    refresh_nws_metadata(location_data)

    existing_location = None
    zip_code = location_data.get("zip_code")
    if zip_code:
        existing_location = location_repository.get_location_by_zip_code(db, str(zip_code))

    if existing_location is None:
        location = location_repository.create_location(db, {**location_data, "is_primary": True})
    else:
        location = location_repository.update_location(
            db,
            existing_location,
            {**location_data, "is_primary": existing_location.is_primary},
        )
        location = location_repository.set_primary_location(db, location)

    return location


def refresh_nws_metadata(location_data: dict[str, Any]) -> str | None:
    try:
        metadata = nws_points_service.fetch_points_metadata(
            float(location_data["latitude"]),
            float(location_data["longitude"]),
        )
    except NwsPointsFetchError:
        return "NWS point metadata could not be fetched; location was saved without metadata."

    if not metadata.has_values():
        return "NWS point metadata response did not include usable fields."

    for key, value in metadata.location_updates(datetime.now(UTC)).items():
        if key == "timezone" and location_data.get("timezone") and value is None:
            continue
        location_data[key] = value
    return None


def get_location_status(db: Session, settings: Settings) -> dict[str, Any]:
    active_location = get_active_location(db, settings)
    metadata_status = "current" if active_location.nws_points_updated_at else "missing"
    warning = None
    if metadata_status == "missing":
        warning = "NWS point metadata is missing; alerts can still use point-based fallback."

    return {
        "active_location": location_to_dict(active_location, settings),
        "using_default": is_default_location(active_location, settings),
        "nws_metadata_status": metadata_status,
        "warning": warning,
    }


def _build_location_data(settings: Settings, payload_data: dict[str, Any]) -> dict[str, Any]:
    latitude = payload_data["latitude"]
    longitude = payload_data["longitude"]
    city = payload_data.get("city") or "Unknown"
    state = (payload_data.get("state") or "NA").upper()
    county = payload_data.get("county") or "Unknown"
    zip_code = payload_data.get("zip_code") or ""
    name = payload_data.get("name")
    label = payload_data.get("label") or name or _build_label(city, state, zip_code, latitude, longitude)

    return {
        "label": label,
        "name": name,
        "city": city,
        "state": state,
        "county": county,
        "zip_code": zip_code,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": payload_data.get("timezone"),
        "default_zoom": payload_data.get("default_zoom") or settings.default_location_zoom,
    }


def _build_label(
    city: str,
    state: str,
    zip_code: str,
    latitude: float,
    longitude: float,
) -> str:
    if city != "Unknown" and state != "NA":
        return f"{city}, {state} {zip_code}".strip()
    return f"{latitude:.4f}, {longitude:.4f}"


def delete_location(db: Session, settings: Settings, location_id: int) -> Location | None:
    location = location_repository.get_location_by_id(db, location_id)
    if location is None:
        return None

    if location.zip_code == settings.default_location_postal_code:
        raise DefaultLocationDeletionError("Default location cannot be deleted.")

    location_repository.delete_location(db, location)
    return ensure_active_location(db, settings)
