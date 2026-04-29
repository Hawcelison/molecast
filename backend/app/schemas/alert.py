from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, field_validator


class AlertMatchMetadata(BaseModel):
    match_type: str
    matched_value: str
    confidence: str


class WeatherAlert(BaseModel):
    id: str
    source: str
    event: str | None = None
    severity: str | None = None
    urgency: str | None = None
    certainty: str | None = None
    headline: str | None = None
    description: str | None = None
    areaDesc: str | None = None
    effective: datetime | None = None
    expires: datetime | None = None
    geometry: dict[str, Any] | None = None
    raw_properties: dict[str, Any]
    match: AlertMatchMetadata
    color_hex: str
    icon: str
    sound_profile: str
    priority: int
    priority_score: int
    severity_rank: int
    urgency_rank: int
    certainty_rank: int

    @field_validator("effective", "expires")
    @classmethod
    def require_utc_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Alert timestamps must include timezone information.")
        return value.astimezone(UTC)


class AlertPresentation(WeatherAlert):
    title: str
    subtitle: str
    expires_in: str
    severity_color: str
    tags: list[str]


class ActiveAlertsResponse(BaseModel):
    location_id: int
    location_label: str
    refreshed_at: datetime
    refresh_interval_seconds: int
    alerts: list[AlertPresentation]

    @field_validator("refreshed_at")
    @classmethod
    def require_utc_refreshed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Alert refresh timestamp must include timezone information.")
        return value.astimezone(UTC)
