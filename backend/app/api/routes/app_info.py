from typing import Any

from fastapi import APIRouter

from app.config import settings


router = APIRouter(tags=["app"])


@router.get("/app-info")
def app_info() -> dict[str, Any]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "version_info": settings.safe_version_info,
        "environment": settings.app_env,
        "debug": settings.debug,
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "debug": settings.safe_debug_status,
        "default_location": settings.default_location_display_name,
        "weather_refresh_seconds": settings.weather_refresh_seconds,
        "alert_refresh_seconds": settings.alert_refresh_seconds,
        "log_retention_days": settings.log_retention_days,
    }
