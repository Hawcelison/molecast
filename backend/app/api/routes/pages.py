from fastapi import APIRouter, Depends, Request
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
