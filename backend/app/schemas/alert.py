from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AlertMatchMetadata(BaseModel):
    match_type: str
    matched_value: str
    confidence: str


class NwsAlertDetails(BaseModel):
    tornadoDetection: str | list[str] | None = None
    tornadoDamageThreat: str | list[str] | None = None
    thunderstormDamageThreat: str | list[str] | None = None
    hailSize: str | list[str] | None = None
    maxHailSize: str | list[str] | None = None
    windGust: str | list[str] | None = None
    maxWindGust: str | list[str] | None = None
    eventMotionDescription: str | list[str] | None = None
    eventEndingTime: str | list[str] | None = None
    VTEC: str | list[str] | None = None
    WEAHandling: str | list[str] | None = None


class GeometryBounds(BaseModel):
    west: float
    south: float
    east: float
    north: float


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
    affectedZones: list[str] | None = None
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
    nws_details: NwsAlertDetails = Field(default_factory=NwsAlertDetails)

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
    geometry_bounds: GeometryBounds | None = None


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
