from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class AlertPriority:
    priority_score: int
    severity_rank: int
    urgency_rank: int
    certainty_rank: int


class MolecastAlert(BaseModel):
    id: str
    canonical_id: str | None = None
    raw_id: str | None = None
    nws_id: str | None = None
    cap_identifier: str | None = None
    source: str

    sent: datetime | None = None
    effective: datetime | None = None
    onset: datetime | None = None
    expires: datetime | None = None
    ends: datetime | None = None
    eventEndingTime: Any = None
    status: str | None = None
    messageType: str | None = None
    references: list[dict[str, Any]] | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    content_hash: str

    event: str | None = None
    eventCode: dict[str, list[str]] | None = None
    category: list[str] | None = None
    response: list[str] | None = None
    severity: str | None = None
    urgency: str | None = None
    certainty: str | None = None
    priority: int | None = None
    color_hex: str | None = None
    color_name: str | None = None
    icon: str | None = None
    sound_profile: str | None = None

    headline: str | None = None
    description: str | None = None
    instruction: str | None = None
    sender: str | None = None
    senderName: str | None = None
    web: str | None = None
    contact: str | None = None

    areaDesc: str | None = None
    geometry: dict[str, Any] | None = None
    affectedZones: list[str] | None = None
    geocode: dict[str, Any] | None = None
    matched_location_ids: list[int] = Field(default_factory=list)
    match_type: str | None = None
    match_confidence: str | None = None

    parameters: dict[str, list[str]] = Field(default_factory=dict)
    VTEC: list[str] | None = None
    EAS_ORG: list[str] | None = None
    AWIPSidentifier: list[str] | None = None
    WMOidentifier: list[str] | None = None
    NWSheadline: list[str] | None = None
    eventMotionDescription: list[str] | None = None
    tornadoDetection: list[str] | None = None
    tornadoDamageThreat: list[str] | None = None
    thunderstormDamageThreat: list[str] | None = None
    flashFloodDetection: list[str] | None = None
    flashFloodDamageThreat: list[str] | None = None
    snowSquallDetection: list[str] | None = None
    snowSquallImpact: list[str] | None = None
    waterspoutDetection: list[str] | None = None
    windThreat: list[str] | None = None
    maxWindGust: list[str] | None = None
    windGust: list[str] | None = None
    hailThreat: list[str] | None = None
    maxHailSize: list[str] | None = None
    hailSize: list[str] | None = None
    WEAHandling: list[str] | None = None
    CMAMtext: list[str] | None = None
    CMAMlongtext: list[str] | None = None
    BLOCKCHANNEL: list[str] | None = None
    expiredReferences: list[str] | None = None

    raw_properties: dict[str, Any]
    raw_feature: dict[str, Any]
