from sqlalchemy.orm import Session

from app.config import Settings
from app.models.location import Location
from app.repositories import location_repository
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
    location_data: dict[str, str | float | bool],
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


def delete_location(db: Session, settings: Settings, location_id: int) -> Location | None:
    location = location_repository.get_location_by_id(db, location_id)
    if location is None:
        return None

    if location.zip_code == settings.default_location_postal_code:
        raise DefaultLocationDeletionError("Default location cannot be deleted.")

    location_repository.delete_location(db, location)
    return ensure_active_location(db, settings)
