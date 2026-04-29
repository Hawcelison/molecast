import hashlib
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from typing import Any

from app.alerts.catalog import (
    DEFAULT_ICON,
    get_event_color,
    get_event_icon,
    get_event_priority,
    get_hazard_entry,
)
from app.alerts.geocodes import normalize_geocodes
from app.alerts.models import MolecastAlert


logger = logging.getLogger(__name__)

KNOWN_PARAMETER_FIELDS = (
    "VTEC",
    "EAS_ORG",
    "AWIPSidentifier",
    "WMOidentifier",
    "NWSheadline",
    "eventMotionDescription",
    "eventEndingTime",
    "tornadoDetection",
    "tornadoDamageThreat",
    "thunderstormDamageThreat",
    "flashFloodDetection",
    "flashFloodDamageThreat",
    "snowSquallDetection",
    "snowSquallImpact",
    "waterspoutDetection",
    "windThreat",
    "maxWindGust",
    "windGust",
    "hailThreat",
    "maxHailSize",
    "hailSize",
    "WEAHandling",
    "CMAMtext",
    "CMAMlongtext",
    "BLOCKCHANNEL",
    "expiredReferences",
)


def normalize_nws_feature(feature: dict, source: str = "nws") -> MolecastAlert:
    if not isinstance(feature, dict):
        logger.warning("Cannot normalize malformed NWS alert feature: feature=%r", feature)
        raise ValueError("NWS alert feature must be a JSON object.")

    properties = feature.get("properties")
    if not isinstance(properties, dict):
        logger.warning("Cannot normalize NWS alert with malformed properties: feature=%r", feature)
        raise ValueError("NWS alert feature properties must be a JSON object.")

    parameters = _normalize_parameters(properties.get("parameters"))
    geocode = _normalize_geocode(properties.get("geocode"))
    event_name = _string_or_none(properties.get("event"))
    severity = _string_or_none(properties.get("severity"))
    hazard_entry = get_hazard_entry(event_name) or {}
    raw_id = _string_or_none(feature.get("id")) or _string_or_none(properties.get("id"))
    nws_id = _string_or_none(properties.get("id"))
    cap_identifier = _string_or_none(properties.get("identifier")) or nws_id
    alert_id = raw_id or nws_id or _content_hash({"properties": properties, "geometry": feature.get("geometry")})

    data: dict[str, Any] = {
        "id": alert_id,
        "canonical_id": _canonical_id(source, cap_identifier or alert_id),
        "raw_id": raw_id,
        "nws_id": nws_id,
        "cap_identifier": cap_identifier,
        "source": source,
        "sent": _parse_time(properties.get("sent")),
        "effective": _parse_time(properties.get("effective")),
        "onset": _parse_time(properties.get("onset")),
        "expires": _parse_time(properties.get("expires")),
        "ends": _parse_time(properties.get("ends")),
        "eventEndingTime": parameters.get("eventEndingTime"),
        "status": _string_or_none(properties.get("status")),
        "messageType": _string_or_none(properties.get("messageType")),
        "references": _list_of_dicts(properties.get("references")),
        "first_seen_at": None,
        "last_seen_at": None,
        "content_hash": _content_hash(
            {
                "id": nws_id or raw_id,
                "sent": properties.get("sent"),
                "effective": properties.get("effective"),
                "onset": properties.get("onset"),
                "expires": properties.get("expires"),
                "ends": properties.get("ends"),
                "status": properties.get("status"),
                "messageType": properties.get("messageType"),
                "event": properties.get("event"),
                "severity": properties.get("severity"),
                "urgency": properties.get("urgency"),
                "certainty": properties.get("certainty"),
                "headline": properties.get("headline"),
                "description": properties.get("description"),
                "instruction": properties.get("instruction"),
                "areaDesc": properties.get("areaDesc"),
                "affectedZones": properties.get("affectedZones"),
                "geocode": properties.get("geocode"),
                "parameters": parameters,
                "geometry": feature.get("geometry"),
            }
        ),
        "event": event_name,
        "eventCode": _normalize_parameters(properties.get("eventCode")) or None,
        "category": _list_of_strings(properties.get("category")),
        "response": _list_of_strings(properties.get("response")),
        "severity": severity,
        "urgency": _string_or_none(properties.get("urgency")),
        "certainty": _string_or_none(properties.get("certainty")),
        "priority": get_event_priority(event_name, severity),
        "color_hex": get_event_color(event_name, severity),
        "color_name": _string_or_none(hazard_entry.get("color_name")),
        "icon": get_event_icon(event_name) or DEFAULT_ICON,
        "sound_profile": _string_or_none(hazard_entry.get("default_sound")) or "default",
        "headline": _string_or_none(properties.get("headline")),
        "description": _string_or_none(properties.get("description")),
        "instruction": _string_or_none(properties.get("instruction")),
        "sender": _string_or_none(properties.get("sender")),
        "senderName": _string_or_none(properties.get("senderName")),
        "web": _string_or_none(properties.get("web")),
        "contact": _string_or_none(properties.get("contact")),
        "areaDesc": _string_or_none(properties.get("areaDesc")),
        "geometry": feature.get("geometry") if isinstance(feature.get("geometry"), dict) else None,
        "affectedZones": _list_of_strings(properties.get("affectedZones")),
        "geocode": geocode,
        "matched_location_ids": [],
        "match_type": None,
        "match_confidence": None,
        "parameters": parameters,
        "raw_properties": dict(properties),
        "raw_feature": dict(feature),
    }

    for parameter_name in KNOWN_PARAMETER_FIELDS:
        if parameter_name in parameters:
            data[parameter_name] = parameters[parameter_name]

    return MolecastAlert.model_validate(data)


def normalize_nws_feature_collection(payload: dict, source: str = "nws") -> list[MolecastAlert]:
    if not isinstance(payload, dict):
        logger.warning("Cannot normalize malformed NWS feature collection: payload=%r", payload)
        raise ValueError("NWS feature collection must be a JSON object.")

    features = payload.get("features", [])
    if not isinstance(features, list):
        logger.warning("Cannot normalize NWS feature collection with malformed features: payload=%r", payload)
        raise ValueError("NWS feature collection features must be an array.")

    alerts: list[MolecastAlert] = []
    for feature in features:
        try:
            alerts.append(normalize_nws_feature(feature, source=source))
        except ValueError:
            logger.warning("Skipping malformed NWS alert during collection normalization.", exc_info=True)
    return alerts


def _normalize_parameters(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _list_of_strings(raw_value) for key, raw_value in value.items()}


def _normalize_geocode(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    normalized = normalize_geocodes(value)
    return _to_plain_data(normalized)


def _parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(UTC)
    if not isinstance(value, str):
        return None
    if not (value.endswith("Z") or len(value) >= 6 and value[-6] in ("+", "-") and value[-3] == ":"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _list_of_dicts(value: Any) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    return [item for item in value if isinstance(item, dict)]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _canonical_id(source: str, identifier: str) -> str:
    return f"{source}:{identifier}"


def _content_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain_data(item) for item in value]
    return value

