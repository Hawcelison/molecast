from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.alerts.catalog import get_hazard_catalog
from app.services import location_service


router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=settings.templates_dir)


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    active_location = location_service.get_active_location(db, settings)
    active_location_config = jsonable_encoder(location_service.location_to_dict(active_location, settings))
    frontend_config = {
        **settings.frontend_config,
        "activeLocation": active_location_config,
        "map": {
            "containerId": "map",
            "center": {
                "latitude": active_location.latitude,
                "longitude": active_location.longitude,
            },
            "zoom": active_location.default_zoom or settings.default_location_zoom,
        },
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "frontend_config": frontend_config,
        },
    )


@router.get("/test-alerts")
def test_alert_editor(request: Request, db: Session = Depends(get_db)):
    if not settings.test_alerts_enabled:
        return templates.TemplateResponse(
            "test_alerts_blocked.html",
            {
                "request": request,
                "public_mode": settings.molecast_public_mode,
                "test_alerts_configured": settings.molecast_enable_test_alerts,
                "disabled_reason": settings.test_alerts_disabled_reason,
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )

    active_location = location_service.get_active_location(db, settings)
    frontend_config = {
        "mapbox": settings.frontend_config.get("mapbox", {}),
        "activeLocation": jsonable_encoder(location_service.location_to_dict(active_location, settings)),
        "alertEvents": [
            {"event": entry["event"]}
            for entry in sorted(get_hazard_catalog().values(), key=lambda item: item["event"])
            if isinstance(entry.get("event"), str)
        ],
    }
    return templates.TemplateResponse(
        "test_alerts.html",
        {
            "request": request,
            "frontend_config": frontend_config,
        },
    )
