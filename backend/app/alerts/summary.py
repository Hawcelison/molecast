from datetime import datetime
from typing import Any

from app.schemas.alert import AlertSummaryHighestAlert, AlertSummaryResponse, WeatherAlert


SEVERITY_RANKS = {
    "extreme": 4,
    "severe": 3,
    "moderate": 2,
    "minor": 1,
    "unknown": 0,
}


def build_alert_summary(
    alerts: list[WeatherAlert],
    *,
    scope: str,
    scope_label: str,
    updated_at: datetime,
    refresh_interval_seconds: int,
    saved_location_count: int | None = None,
    affected_location_count: int | None = None,
    partial: bool = False,
    errors: list[str] | None = None,
) -> AlertSummaryResponse:
    warning_count = 0
    watch_count = 0
    advisory_count = 0
    other_count = 0

    for alert in alerts:
        category = classify_alert(alert)
        if category == "warning":
            warning_count += 1
        elif category == "watch":
            watch_count += 1
        elif category == "advisory":
            advisory_count += 1
        else:
            other_count += 1

    highest_alert = choose_highest_alert(alerts)

    return AlertSummaryResponse(
        scope=scope,
        scope_label=scope_label,
        total=len(alerts),
        warning_count=warning_count,
        watch_count=watch_count,
        advisory_count=advisory_count,
        other_count=other_count,
        highest_alert=build_highest_alert_ref(highest_alert) if highest_alert else None,
        updated_at=updated_at,
        refresh_interval_seconds=refresh_interval_seconds,
        saved_location_count=saved_location_count,
        affected_location_count=affected_location_count,
        partial=partial,
        errors=errors or [],
    )


def classify_alert(alert: WeatherAlert) -> str:
    event = (alert.event or "").lower()
    if "warning" in event:
        return "warning"
    if "watch" in event:
        return "watch"
    if "advisory" in event:
        return "advisory"
    return "other"


def choose_highest_alert(alerts: list[WeatherAlert]) -> WeatherAlert | None:
    if not alerts:
        return None
    return max(alerts, key=highest_alert_sort_key)


def highest_alert_sort_key(alert: WeatherAlert) -> tuple[int, int, int, int]:
    return (
        _int_value(getattr(alert, "priority_score", None)),
        _int_value(getattr(alert, "priority", None)),
        _int_value(getattr(alert, "severity_rank", None)),
        severity_rank(getattr(alert, "severity", None)),
    )


def build_highest_alert_ref(alert: WeatherAlert) -> AlertSummaryHighestAlert:
    return AlertSummaryHighestAlert(
        id=alert.id,
        source=alert.source,
        event=alert.event,
        priority=alert.priority,
        priority_score=alert.priority_score,
        color_hex=alert.color_hex,
    )


def severity_rank(severity: str | None) -> int:
    if not severity:
        return -1
    return SEVERITY_RANKS.get(severity.strip().lower(), -1)


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return -1
    if isinstance(value, int):
        return value
    return -1
