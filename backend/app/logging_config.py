import logging
from logging.handlers import TimedRotatingFileHandler
from http import HTTPStatus

from app.config import Settings


LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOGGER_NAME = "molecast"


def configure_logging(settings: Settings) -> logging.Logger:
    """Configure Molecast logging once per process."""

    logger = logging.getLogger(LOGGER_NAME)
    if getattr(logger, "_molecast_configured", False):
        return logger

    settings.log_dir.mkdir(parents=True, exist_ok=True)

    logger.setLevel(_resolve_log_level(settings.effective_log_level))
    logger.propagate = False

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = TimedRotatingFileHandler(
        filename=settings.log_file_path,
        when="midnight",
        interval=1,
        backupCount=settings.log_retention_days,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger._molecast_configured = True

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def should_log_request(path: str) -> bool:
    return not path.startswith("/static/")


def log_request_completed(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    log_method = logger.error if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR else logger.info
    log_method(
        "Request completed: method=%s path=%s status_code=%s duration_ms=%.2f",
        method,
        path,
        status_code,
        duration_ms,
    )


def log_request_exception(logger: logging.Logger, method: str, path: str) -> None:
    logger.exception(
        "Unhandled exception during request: method=%s path=%s",
        method,
        path,
    )


def _resolve_log_level(log_level: str) -> int:
    resolved_level = logging.getLevelName(log_level.upper())
    return resolved_level if isinstance(resolved_level, int) else logging.INFO
