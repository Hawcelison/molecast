from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.schemas.location import (
    ActiveLocationDirectUpdate,
    ActiveLocationUpdate,
    LocationCreate,
    LocationDeleteResponse,
    LocationRead,
    LocationStatus,
    ZipLookupResponse,
)
from app.services import location_service
from app.services.zip_lookup_service import InvalidZipCodeError


router = APIRouter(tags=["locations"])


@router.get("/location/default", response_model=LocationRead)
def get_default_location(db: Session = Depends(get_db)):
    return location_service.get_default_location(db, settings)


@router.get("/location/active", response_model=LocationRead)
def get_active_location(db: Session = Depends(get_db)):
    location = location_service.get_active_location(db, settings)
    return location_service.location_to_dict(location, settings)


@router.get("/location/status", response_model=LocationStatus)
def get_location_status(db: Session = Depends(get_db)):
    return location_service.get_location_status(db, settings)


@router.get("/location/lookup/{zip_code}", response_model=ZipLookupResponse)
def lookup_zip_code(zip_code: str):
    try:
        lookup_result = location_service.lookup_zip_code(zip_code)
    except InvalidZipCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if lookup_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ZIP code not found in local lookup data.",
        )
    return lookup_result


@router.post("/location/active", response_model=LocationRead)
def set_active_location(
    payload: ActiveLocationUpdate,
    db: Session = Depends(get_db),
):
    location = location_service.set_active_location(db, payload.location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found.",
        )
    return location_service.location_to_dict(location, settings)


@router.put("/location/active", response_model=LocationRead)
def put_active_location(
    payload: ActiveLocationDirectUpdate,
    db: Session = Depends(get_db),
):
    location = location_service.set_active_location_from_payload(
        db,
        settings,
        payload.model_dump(exclude_unset=True),
    )
    return location_service.location_to_dict(location, settings)


@router.get("/locations", response_model=list[LocationRead])
def list_locations(db: Session = Depends(get_db)):
    return location_service.list_locations(db, settings)


@router.post(
    "/locations",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    payload: LocationCreate,
    db: Session = Depends(get_db),
):
    return location_service.create_location(db, payload.model_dump())


@router.delete("/locations/{location_id}", response_model=LocationDeleteResponse)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    try:
        active_location = location_service.delete_location(db, settings, location_id)
    except location_service.DefaultLocationDeletionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if active_location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found.",
        )
    return {
        "deleted": True,
        "active_location": active_location,
    }
