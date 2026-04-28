import re
from datetime import UTC, datetime


ISO_TIMEZONE_PATTERN = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


def now_utc() -> datetime:
    return datetime.now(UTC)


def parse_alert_time_utc(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        parsed = value
    elif isinstance(value, str):
        if not ISO_TIMEZONE_PATTERN.search(value):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    return parsed.astimezone(UTC)


def has_invalid_alert_time(value) -> bool:
    return value is not None and parse_alert_time_utc(value) is None
