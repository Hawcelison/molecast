from collections.abc import Sequence

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.location import Location


def list_locations(db: Session) -> Sequence[Location]:
    return db.scalars(
        select(Location).order_by(
            Location.is_primary.desc(),
            Location.last_used_at.desc().nullslast(),
            func.lower(Location.label),
            func.lower(Location.name),
            Location.id,
        )
    ).all()


def get_location_by_id(db: Session, location_id: int) -> Location | None:
    return db.get(Location, location_id)


def get_primary_location(db: Session) -> Location | None:
    return db.scalars(
        select(Location)
        .where(Location.is_primary.is_(True))
        .order_by(Location.updated_at.desc(), Location.id.desc())
    ).first()


def get_location_by_zip_code(db: Session, zip_code: str) -> Location | None:
    return db.scalars(select(Location).where(Location.zip_code == zip_code)).first()


def get_matching_location(db: Session, location_data: dict[str, Any]) -> Location | None:
    return db.scalars(
        select(Location).where(
            Location.zip_code == str(location_data.get("zip_code") or ""),
            Location.label == str(location_data.get("label") or ""),
            Location.latitude == float(location_data["latitude"]),
            Location.longitude == float(location_data["longitude"]),
        )
    ).first()


def create_location(db: Session, location_data: dict[str, Any]) -> Location:
    if location_data.get("is_primary"):
        _clear_primary_locations(db)

    location = Location(**location_data)
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def update_location(db: Session, location: Location, location_data: dict[str, Any]) -> Location:
    for key, value in location_data.items():
        setattr(location, key, value)
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def set_primary_location(db: Session, location: Location, last_used_at=None) -> Location:
    db.execute(
        update(Location)
        .where(Location.id != location.id, Location.is_primary.is_(True))
        .values(is_primary=False)
    )
    db.flush()
    location.is_primary = True
    if last_used_at is not None:
        location.last_used_at = last_used_at
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def delete_location(db: Session, location: Location) -> None:
    db.delete(location)
    db.commit()


def ensure_single_primary_location(db: Session) -> Location | None:
    primary_locations = db.scalars(
        select(Location)
        .where(Location.is_primary.is_(True))
        .order_by(Location.updated_at.desc(), Location.id.desc())
    ).all()
    if not primary_locations:
        return None

    active_location = primary_locations[0]
    for location in primary_locations[1:]:
        location.is_primary = False

    db.commit()
    db.refresh(active_location)
    return active_location


def ensure_location_exists(
    db: Session,
    location_data: dict[str, Any],
) -> Location:
    existing_location = get_matching_location(db, location_data)
    if existing_location:
        return existing_location

    return create_location(db, location_data)


def _clear_primary_locations(db: Session) -> None:
    primary_locations = db.scalars(select(Location).where(Location.is_primary.is_(True))).all()
    for location in primary_locations:
        location.is_primary = False
    db.flush()
