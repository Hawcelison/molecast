from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.services import location_service


router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=settings.templates_dir)


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    active_location = location_service.get_active_location(db, settings)
    frontend_config = {
        **settings.frontend_config,
        "map": {
            "containerId": "map",
            "center": {
                "latitude": active_location.latitude,
                "longitude": active_location.longitude,
            },
            "zoom": 9,
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
def test_alert_editor(request: Request):
    frontend_config = {
        "mapbox": settings.frontend_config.get("mapbox", {}),
    }
    return templates.TemplateResponse(
        "test_alerts.html",
        {
            "request": request,
            "frontend_config": frontend_config,
        },
    )
