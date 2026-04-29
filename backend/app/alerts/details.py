from typing import Any


NWS_DETAIL_FIELDS = (
    "tornadoDetection",
    "tornadoDamageThreat",
    "thunderstormDamageThreat",
    "hailSize",
    "maxHailSize",
    "windGust",
    "maxWindGust",
    "eventMotionDescription",
    "eventEndingTime",
    "VTEC",
    "WEAHandling",
)


def build_nws_details(parameters: dict[str, Any] | None) -> dict[str, str | list[str] | None]:
    values = parameters if isinstance(parameters, dict) else {}
    lookup = {str(key).lower(): key for key in values}
    details: dict[str, str | list[str] | None] = {}

    for field_name in NWS_DETAIL_FIELDS:
        raw_value = None
        source_key = lookup.get(field_name.lower())
        if source_key is not None:
            raw_value = values[source_key]
        details[field_name] = _detail_value(raw_value)

    return details


def _detail_value(value: Any) -> str | list[str] | None:
    items = _string_values(value)
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    return items


def _string_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return [
            item.strip() if isinstance(item, str) else str(item)
            for item in value
            if item is not None and str(item).strip()
        ]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value)]
