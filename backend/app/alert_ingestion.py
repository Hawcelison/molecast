import asyncio
from contextlib import suppress

from app.config import Settings, settings
from app.database import SessionLocal
from app.logging_config import get_logger
from app.services import location_service
from app.services.alert_service import AlertFetchError, active_alert_service


async def run_alert_ingestion(app_settings: Settings = settings) -> None:
    logger = get_logger()

    while True:
        try:
            await asyncio.to_thread(_refresh_active_location_alerts, app_settings)
        except AlertFetchError as exc:
            logger.warning("Alert ingestion refresh failed: %s", exc)
        except Exception:
            logger.exception("Alert ingestion encountered an unexpected error")

        await asyncio.sleep(app_settings.alert_refresh_seconds)


def _refresh_active_location_alerts(app_settings: Settings) -> None:
    with SessionLocal() as db:
        active_location = location_service.get_active_location(db, app_settings)
        active_alert_service.refresh_active_alerts(active_location)


async def stop_alert_ingestion(task: asyncio.Task | None) -> None:
    if task is None:
        return

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
