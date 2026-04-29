import json
from copy import deepcopy
from functools import lru_cache
from importlib import resources
from typing import Any


DEFAULT_COLOR_HEX = "#3399FF"
DEFAULT_ICON = "alert-circle"
DEFAULT_PRIORITY = 100
DEFAULT_SOUND_PROFILE = "default"

SEVERITY_COLOR_FALLBACKS = {
    "extreme": "#FF0000",
    "severe": "#FFA500",
    "moderate": "#FFFF00",
    "minor": "#00FF00",
    "unknown": DEFAULT_COLOR_HEX,
}


@lru_cache
def _load_hazard_catalog() -> dict[str, dict[str, Any]]:
    catalog_path = resources.files("app.alerts.data").joinpath("nws_hazards.json")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    hazards = payload.get("hazards", [])
    if not isinstance(hazards, list):
        raise ValueError("NWS hazard catalog must include a hazards array.")

    catalog: dict[str, dict[str, Any]] = {}
    for entry in hazards:
        if not isinstance(entry, dict) or not isinstance(entry.get("event"), str):
            continue
        catalog[_normalize_event_name(entry["event"])] = entry
    return catalog


def get_hazard_catalog() -> dict[str, dict[str, Any]]:
    return deepcopy(_load_hazard_catalog())


def get_hazard_entry(event_name: str | None) -> dict[str, Any] | None:
    if not event_name:
        return None
    entry = _load_hazard_catalog().get(_normalize_event_name(event_name))
    return deepcopy(entry) if entry is not None else None


def get_event_color(event_name: str | None, severity: str | None = None) -> str:
    entry = get_hazard_entry(event_name)
    if entry and isinstance(entry.get("color_hex"), str):
        return entry["color_hex"]
    return SEVERITY_COLOR_FALLBACKS.get(_normalize_alert_value(severity), DEFAULT_COLOR_HEX)


def get_event_priority(event_name: str | None, severity: str | None = None) -> int:
    entry = get_hazard_entry(event_name)
    if entry and isinstance(entry.get("priority"), int):
        return entry["priority"]

    severity_priority = {
        "extreme": 500,
        "severe": 400,
        "moderate": 300,
        "minor": 200,
        "unknown": DEFAULT_PRIORITY,
    }
    return severity_priority.get(_normalize_alert_value(severity), DEFAULT_PRIORITY)


def get_event_icon(event_name: str | None) -> str:
    entry = get_hazard_entry(event_name)
    if entry and isinstance(entry.get("icon"), str):
        return entry["icon"]
    return DEFAULT_ICON


def get_event_sound_profile(event_name: str | None) -> str:
    entry = get_hazard_entry(event_name)
    if entry and isinstance(entry.get("default_sound"), str):
        return entry["default_sound"]
    return DEFAULT_SOUND_PROFILE


def _normalize_event_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _normalize_alert_value(value: str | None) -> str:
    if value is None:
        return "unknown"
    return value.strip().lower() or "unknown"
