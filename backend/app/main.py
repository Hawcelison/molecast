import asyncio

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi import Request
from fastapi.staticfiles import StaticFiles

from app.alert_ingestion import run_alert_ingestion, stop_alert_ingestion
from app.api.routes import alerts, app_info, health, locations, pages, test_alerts
from app.config import settings
from app.db_init import init_database
from app.logging_config import (
    configure_logging,
    log_request_completed,
    log_request_exception,
    should_log_request,
)


logger = configure_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    alert_ingestion_task = None
    logger.info(
        "Application startup: %s version=%s environment=%s",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )
    init_database(settings)
    logger.info("Database initialized with default location: %s", settings.default_location_display_name)
    alert_ingestion_task = asyncio.create_task(run_alert_ingestion(settings))
    logger.info("Alert ingestion started with refresh interval: %s seconds", settings.alert_refresh_seconds)
    logger.debug(
        "Debug mode enabled: log_level=%s default_location=%s",
        settings.effective_log_level,
        settings.default_location_display_name,
    )
    try:
        yield
    finally:
        await stop_alert_ingestion(alert_ingestion_task)
        logger.info("Application shutdown: %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=False,
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    @app.middleware("http")
    async def log_api_requests(request: Request, call_next):
        start_time = perf_counter()
        request_path = request.url.path
        should_log = should_log_request(request_path)

        try:
            response = await call_next(request)
        except Exception:
            if should_log:
                log_request_exception(logger, request.method, request_path)
            raise

        if should_log:
            duration_ms = (perf_counter() - start_time) * 1000
            log_request_completed(
                logger,
                request.method,
                request_path,
                response.status_code,
                duration_ms,
            )

        return response

    app.include_router(pages.router)
    app.include_router(health.router)
    app.include_router(app_info.router, prefix="/api")
    app.include_router(locations.router, prefix="/api")
    app.include_router(alerts.router, prefix="/api")
    app.include_router(test_alerts.router, prefix="/api")
    return app


app = create_app()
