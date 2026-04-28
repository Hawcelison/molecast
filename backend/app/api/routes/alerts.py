from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.schemas.alert import ActiveAlertsResponse
from app.services import location_service
from app.services.alert_presentation import build_alert_presentations
from app.services.alert_service import AlertFetchError, active_alert_service


router = APIRouter(prefix="/alerts", tags=["alerts"])


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
