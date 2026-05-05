from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.alerts.presentation import build_alert_presentations
from app.alerts.saved_summary import SavedAlertSummaryService
from app.alerts.summary import build_alert_summary
from app.alerts.test_alert_loader import TestAlertLoader
from app.schemas.alert import ActiveAlertsResponse, AlertSummaryResponse
from app.services import location_service
from app.services.alert_service import AlertFetchError, active_alert_service
from app.services.nws_zone_geometry_service import nws_zone_geometry_service


router = APIRouter(prefix="/alerts", tags=["alerts"])
saved_alert_summary_service = SavedAlertSummaryService(
    provider=active_alert_service.provider,
    test_alert_loader=TestAlertLoader(settings),
    refresh_interval_seconds=settings.alert_refresh_seconds,
    zone_geometry_service=nws_zone_geometry_service,
)


@router.get("/active", response_model=ActiveAlertsResponse)
def get_active_alerts(db: Session = Depends(get_db)):
    active_location = location_service.get_active_location(db, settings)

    try:
        alerts, refreshed_at = active_alert_service.get_active_alerts(active_location)
    except AlertFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "location_id": active_location.id,
        "location_label": active_location.label,
        "refreshed_at": refreshed_at,
        "refresh_interval_seconds": settings.alert_refresh_seconds,
        "alerts": build_alert_presentations(alerts, active_location),
    }


@router.get("/summary", response_model=AlertSummaryResponse, response_model_exclude_none=True)
def get_alert_summary(
    scope: str = "active",
    db: Session = Depends(get_db),
):
    normalized_scope = scope.strip().lower()
    if normalized_scope == "saved":
        locations = location_service.list_locations(db, settings)
        active_location = location_service.get_active_location(db, settings)
        active_alerts = None
        try:
            active_alerts, _ = active_alert_service.get_active_alerts(active_location)
        except AlertFetchError:
            active_alerts = None
        return saved_alert_summary_service.get_saved_summary(
            locations,
            active_location=active_location,
            active_alerts=active_alerts,
        )

    if normalized_scope != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported alert summary scope.",
        )

    active_location = location_service.get_active_location(db, settings)

    try:
        alerts, refreshed_at = active_alert_service.get_active_alerts(active_location)
    except AlertFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return build_alert_summary(
        alerts,
        scope="active",
        scope_label="Active Location",
        updated_at=refreshed_at,
        refresh_interval_seconds=settings.alert_refresh_seconds,
        saved_location_count=None,
        affected_location_count=1,
        partial=False,
        errors=[],
    )
