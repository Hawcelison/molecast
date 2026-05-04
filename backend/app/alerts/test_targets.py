from typing import Any

from app.models.location import Location
from app.services.nws_points_service import extract_zone_id


TARGET_FIELDS = (
    "zip_codes",
    "location_ids",
    "county_fips",
    "county_zones",
    "forecast_zones",
    "same",
    "ugc",
)


def normalize_test_alert_targets(value: Any) -> dict[str, list[Any]] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("targets must be a JSON object.")

    normalized: dict[str, list[Any]] = {}
    zip_codes = _normalize_zip_codes(value.get("zip_codes"))
    location_ids = _normalize_location_ids(value.get("location_ids"))
    county_fips = _normalize_county_fips(value.get("county_fips"))
    county_zones = _normalize_zone_ids(value.get("county_zones"))
    forecast_zones = _normalize_zone_ids(value.get("forecast_zones"))
    same = _normalize_same(value.get("same"))
    ugc = _normalize_zone_ids(value.get("ugc"))

    if zip_codes:
        normalized["zip_codes"] = zip_codes
    if location_ids:
        normalized["location_ids"] = location_ids
    if county_fips:
        normalized["county_fips"] = county_fips
    if county_zones:
        normalized["county_zones"] = county_zones
    if forecast_zones:
        normalized["forecast_zones"] = forecast_zones
    if same:
        normalized["same"] = same
    if ugc:
        normalized["ugc"] = ugc

    return normalized


def has_explicit_test_targets(properties: dict[str, Any]) -> bool:
    return isinstance(properties.get("targets"), dict)


def match_test_targets_to_location(
    targets: dict[str, Any] | None,
    location: Location,
) -> Any:
    from app.alerts.matcher import AlertMatch

    if not isinstance(targets, dict):
        return None

    location_id = getattr(location, "id", None)
    if isinstance(location_id, int) and location_id in set(targets.get("location_ids") or []):
        return AlertMatch(match_type="location_id", matched_value=str(location_id), confidence="high")

    zip_code = _five_digit_zip(getattr(location, "zip_code", None))
    if zip_code and zip_code in set(targets.get("zip_codes") or []):
        return AlertMatch(match_type="zip_code", matched_value=zip_code, confidence="high")

    county_fips = _normalize_county_fips_value(getattr(location, "county_fips", None))
    if county_fips and county_fips in set(targets.get("county_fips") or []):
        return AlertMatch(match_type="county_fips", matched_value=county_fips, confidence="high")

    county_zone = _zone_id(getattr(location, "county_zone", None))
    if county_zone and county_zone in set(targets.get("county_zones") or []):
        return AlertMatch(match_type="county_zone", matched_value=county_zone, confidence="high")

    forecast_zone = _zone_id(getattr(location, "forecast_zone", None))
    if forecast_zone and forecast_zone in set(targets.get("forecast_zones") or []):
        return AlertMatch(match_type="forecast_zone", matched_value=forecast_zone, confidence="high")

    location_zone_ids = {
        zone_id
        for zone_id in (
            county_zone,
            forecast_zone,
            _zone_id(getattr(location, "fire_weather_zone", None)),
        )
        if zone_id
    }
    ugc_match = sorted(location_zone_ids & set(targets.get("ugc") or []))
    if ugc_match:
        return AlertMatch(match_type="ugc", matched_value=ugc_match[0], confidence="high")

    if county_fips:
        same_targets = set(targets.get("same") or [])
        same_match = next((same for same in sorted(same_targets) if same[1:] == county_fips), None)
        if same_match:
            return AlertMatch(match_type="same", matched_value=same_match, confidence="high")

    return None


def _normalize_zip_codes(value: Any) -> list[str]:
    zip_codes: list[str] = []
    for item in _as_list(value):
        zip_code = _five_digit_zip(item)
        if not zip_code:
            raise ValueError("targets.zip_codes values must be 5-digit ZIP codes.")
        if zip_code not in zip_codes:
            zip_codes.append(zip_code)
    return zip_codes


def _normalize_location_ids(value: Any) -> list[int]:
    location_ids: list[int] = []
    for item in _as_list(value):
        if isinstance(item, bool):
            raise ValueError("targets.location_ids values must be integers.")
        try:
            location_id = int(item)
        except (TypeError, ValueError) as exc:
            raise ValueError("targets.location_ids values must be integers.") from exc
        if location_id < 1:
            raise ValueError("targets.location_ids values must be positive integers.")
        if location_id not in location_ids:
            location_ids.append(location_id)
    return location_ids


def _normalize_county_fips(value: Any) -> list[str]:
    county_fips_values: list[str] = []
    for item in _as_list(value):
        county_fips = _normalize_county_fips_value(item)
        if not county_fips:
            raise ValueError("targets.county_fips values must be 5-digit FIPS codes.")
        if county_fips not in county_fips_values:
            county_fips_values.append(county_fips)
    return county_fips_values


def _normalize_county_fips_value(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() and len(text) <= 5:
        text = text.zfill(5)
    return text if len(text) == 5 and text.isdigit() else None


def _normalize_zone_ids(value: Any) -> list[str]:
    zone_ids: list[str] = []
    for item in _as_list(value):
        zone_id = _zone_id(item)
        if not zone_id:
            raise ValueError("target zone values must be valid NWS UGC zone IDs.")
        if zone_id not in zone_ids:
            zone_ids.append(zone_id)
    return zone_ids


def _normalize_same(value: Any) -> list[str]:
    same_values: list[str] = []
    for item in _as_list(value):
        if item is None or isinstance(item, bool):
            raise ValueError("targets.same values must be 6-digit SAME codes.")
        same = str(item).strip()
        if same.isdigit() and len(same) <= 6:
            same = same.zfill(6)
        if len(same) != 6 or not same.isdigit():
            raise ValueError("targets.same values must be 6-digit SAME codes.")
        if same not in same_values:
            same_values.append(same)
    return same_values


def _five_digit_zip(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 5 and text[:5].isdigit() and (len(text) == 5 or text[5] == "-"):
        return text[:5]
    return None


def _zone_id(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    zone_id = extract_zone_id(str(value).strip())
    if zone_id is None:
        return None
    zone_id = zone_id.upper()
    if len(zone_id) != 6 or not zone_id[:2].isalpha() or zone_id[2] not in {"C", "Z"} or not zone_id[3:].isdigit():
        return None
    return zone_id


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
