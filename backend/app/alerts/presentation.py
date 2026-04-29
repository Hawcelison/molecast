import math
from datetime import datetime
from typing import Any, Protocol

from app.schemas.alert import AlertPresentation, WeatherAlert
from app.services.alert_time import now_utc, parse_alert_time_utc


class AlertPresentationLocation(Protocol):
    county: str
    state: str


SEVERITY_COLOR_MAP = {
    "Extreme": "severity-extreme",
    "Severe": "severity-severe",
    "Moderate": "severity-moderate",
    "Minor": "severity-minor",
    "Unknown": "severity-unknown",
}


def build_alert_presentations(
    alerts: list[WeatherAlert],
    location: AlertPresentationLocation,
    now: datetime | None = None,
) -> list[AlertPresentation]:
    current_time = parse_alert_time_utc(now) or now_utc()
    return [
        build_alert_presentation(alert, location, current_time)
        for alert in alerts
        if not is_expired(alert, current_time)
    ]


def build_alert_presentation(
    alert: WeatherAlert,
    location: AlertPresentationLocation,
    now: datetime | None = None,
) -> AlertPresentation:
    current_time = parse_alert_time_utc(now) or now_utc()
    alert_data = alert.model_dump()
    alert_data.update(
        {
            "title": build_title(alert),
            "subtitle": build_subtitle(location),
            "expires_in": build_expires_in(alert.expires, current_time),
            "severity_color": build_severity_color(alert.severity),
            "tags": build_tags(alert),
            "geometry_bounds": build_geometry_bounds(alert.geometry),
        }
    )
    return AlertPresentation.model_validate(alert_data)


def build_geometry_bounds(geometry: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(geometry, dict):
        return None

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type not in {"Polygon", "MultiPolygon"} or not isinstance(coordinates, list):
        return None

    positions: list[tuple[float, float]] = []
    _collect_positions(coordinates, positions)
    if not positions:
        return None

    longitudes = [position[0] for position in positions]
    latitudes = [position[1] for position in positions]
    return {
        "west": min(longitudes),
        "south": min(latitudes),
        "east": max(longitudes),
        "north": max(latitudes),
    }


def _collect_positions(value: Any, positions: list[tuple[float, float]]) -> None:
    if not isinstance(value, list):
        return

    if _is_position(value):
        longitude = float(value[0])
        latitude = float(value[1])
        if -180 <= longitude <= 180 and -90 <= latitude <= 90:
            positions.append((longitude, latitude))
        return

    for item in value:
        _collect_positions(item, positions)


def _is_position(value: list[Any]) -> bool:
    if len(value) < 2:
        return False
    return _is_finite_number(value[0]) and _is_finite_number(value[1])


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def build_title(alert: WeatherAlert) -> str:
    return (alert.event or "Weather Alert").upper()


def build_subtitle(location: AlertPresentationLocation) -> str:
    parts = [location.county, location.state]
    return ", ".join(part for part in parts if part)


def build_expires_in(expires_at: datetime | None, now: datetime | None = None) -> str:
    if expires_at is None:
        return "Unknown"

    current_time = parse_alert_time_utc(now) or now_utc()
    utc_expires_at = parse_alert_time_utc(expires_at)
    if utc_expires_at is None:
        return "Unknown"

    remaining_seconds = int((utc_expires_at - current_time).total_seconds())
    if remaining_seconds <= 0:
        return "Expired"

    remaining_minutes = (remaining_seconds + 59) // 60
    if remaining_minutes < 60:
        return _format_unit(remaining_minutes, "minute")

    remaining_hours = remaining_minutes // 60
    minutes = remaining_minutes % 60
    if remaining_hours < 24:
        if minutes == 0:
            return _format_unit(remaining_hours, "hour")
        return f"{_format_unit(remaining_hours, 'hour')} {_format_unit(minutes, 'minute')}"

    remaining_days = remaining_hours // 24
    hours = remaining_hours % 24
    if hours == 0:
        return _format_unit(remaining_days, "day")
    return f"{_format_unit(remaining_days, 'day')} {_format_unit(hours, 'hour')}"


def build_severity_color(severity: str | None) -> str:
    normalized_severity = normalize_severity(severity)
    return SEVERITY_COLOR_MAP.get(normalized_severity, SEVERITY_COLOR_MAP["Unknown"])


def is_expired(alert: WeatherAlert, now: datetime | None = None) -> bool:
    if alert.expires is None:
        return False

    current_time = parse_alert_time_utc(now) or now_utc()
    utc_expires_at = parse_alert_time_utc(alert.expires)
    if utc_expires_at is None:
        return False

    return utc_expires_at <= current_time


def normalize_severity(severity: str | None) -> str:
    if not severity:
        return "Unknown"
    return severity.strip().title()


def build_tags(alert: WeatherAlert) -> list[str]:
    tags = []
    searchable_text = " ".join(
        value
        for value in (
            alert.event,
            alert.headline,
            alert.description,
            alert.certainty,
            _flatten_tag_text(alert.raw_properties.get("instruction")),
            _flatten_tag_text(alert.raw_properties.get("parameters")),
        )
        if value
    ).lower()

    if (alert.certainty or "").lower() == "observed" or "observed" in searchable_text:
        tags.append("OBSERVED")
    if "radar" in searchable_text:
        tags.append("RADAR")
    if "particularly dangerous situation" in searchable_text or " pds " in f" {searchable_text} ":
        tags.append("PDS")

    return tags


def _format_unit(value: int, unit: str) -> str:
    suffix = "" if value == 1 else "s"
    return f"{value} {unit}{suffix}"


def _flatten_tag_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_tag_text(item) for item in value.values())
    if isinstance(value, list | tuple | set):
        return " ".join(_flatten_tag_text(item) for item in value)
    return str(value)
