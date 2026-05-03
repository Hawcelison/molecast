from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    LocationUpdate,
    ZipLookupResponse,
)
from app.schemas.location_resolver import (
    LocationSearchResponse,
    NwsPointPreviewRequest,
    NwsPointPreviewResponse,
)
from app.services import location_service
from app.services.location_resolver_service import (
    InvalidLocationSearchTypeError,
    get_location_resolver_service,
)
from app.services.nws_points_service import NwsPointsFetchError
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


@router.get("/location/search", response_model=LocationSearchResponse)
def search_locations(
    q: str = Query(default=""),
    limit: int = Query(default=8, ge=1),
    search_type: str | None = Query(default=None, alias="type"),
):
    try:
        return get_location_resolver_service().search(q, limit, search_type)
    except InvalidLocationSearchTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/location/points/preview", response_model=NwsPointPreviewResponse)
def preview_location_points(payload: NwsPointPreviewRequest):
    try:
        return get_location_resolver_service().preview_nws_point(
            payload.latitude,
            payload.longitude,
        )
    except NwsPointsFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/location/zip/{zip_code}", response_model=ZipLookupResponse)
def lookup_zip_code(zip_code: str):
    return _lookup_zip_code_response(zip_code)


@router.get(
    "/location/lookup/{zip_code}",
    response_model=ZipLookupResponse,
    include_in_schema=False,
)
def lookup_zip_code_legacy(zip_code: str):
    return _lookup_zip_code_response(zip_code)


def _lookup_zip_code_response(zip_code: str) -> ZipLookupResponse:
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
    return ZipLookupResponse(
        zip=lookup_result.zip_code,
        zip_code=lookup_result.zip_code,
        city=lookup_result.city,
        state=lookup_result.state,
        county=lookup_result.county,
        county_fips=lookup_result.county_fips,
        latitude=lookup_result.latitude,
        longitude=lookup_result.longitude,
        default_zoom=lookup_result.default_zoom,
        source=lookup_result.source,
        source_year=lookup_result.source_year,
        source_version=lookup_result.source_version,
        dataset_version=lookup_result.dataset_version,
        imported_at=lookup_result.imported_at,
        location_type=lookup_result.location_type,
        is_zcta=lookup_result.is_zcta,
        confidence=lookup_result.confidence,
    )


@router.post("/location/active", response_model=LocationRead)
def set_active_location(
    payload: ActiveLocationUpdate,
    db: Session = Depends(get_db),
):
    location = location_service.activate_location(db, settings, payload.location_id)
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
    return [
        location_service.location_to_dict(location, settings)
        for location in location_service.list_locations(db, settings)
    ]


@router.post(
    "/locations",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    payload: LocationCreate,
    db: Session = Depends(get_db),
):
    location = location_service.create_location(db, settings, payload.model_dump())
    return location_service.location_to_dict(location, settings)


@router.put("/locations/{location_id}", response_model=LocationRead)
def update_location(
    location_id: int,
    payload: LocationUpdate,
    db: Session = Depends(get_db),
):
    location = location_service.update_location(
        db,
        settings,
        location_id,
        payload.model_dump(exclude_unset=True),
    )
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found.",
        )
    return location_service.location_to_dict(location, settings)


@router.post("/locations/{location_id}/activate", response_model=LocationRead)
def activate_location(location_id: int, db: Session = Depends(get_db)):
    location = location_service.activate_location(db, settings, location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found.",
        )
    return location_service.location_to_dict(location, settings)


@router.delete("/locations/{location_id}", response_model=LocationDeleteResponse)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    try:
        active_location = location_service.delete_location(db, settings, location_id)
    except location_service.ActiveLocationDeletionError as exc:
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
        "active_location": location_service.location_to_dict(active_location, settings),
    }
