from dataclasses import dataclass
from typing import Any

from app.models.location import Location
from app.alerts.test_targets import has_explicit_test_targets, match_test_targets_to_location


STATE_NAMES_BY_ABBREVIATION = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
}


@dataclass(frozen=True)
class AlertMatch:
    match_type: str
    matched_value: str
    confidence: str


def match_alert_to_location(feature: dict[str, Any], location: Location) -> AlertMatch | None:
    geometry = feature.get("geometry")
    if geometry and point_matches_geometry(location.longitude, location.latitude, geometry):
        return AlertMatch(
            match_type="geometry",
            matched_value=f"{location.latitude},{location.longitude}",
            confidence="high",
        )

    properties = feature.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}

    source = str(feature.get("source") or properties.get("source") or "").strip().lower()
    if source == "test" and has_explicit_test_targets(properties):
        return match_test_targets_to_location(properties.get("targets"), location)

    area_desc = properties.get("areaDesc") or ""

    county_match = match_area_desc_county(area_desc, location.county)
    if county_match:
        return AlertMatch(
            match_type="county",
            matched_value=county_match,
            confidence="medium",
        )

    if not location.county:
        state_match = match_area_desc_state(area_desc, location.state)
        if state_match:
            return AlertMatch(
                match_type="state",
                matched_value=state_match,
                confidence="low",
            )

    return None


def match_area_desc_county(area_desc: str, county: str | None) -> str | None:
    if not county:
        return None

    area_tokens = _normalize_area_tokens(area_desc)
    county_variants = _county_variants(county)

    for county_variant in county_variants:
        if _normalize_text(county_variant) in area_tokens:
            return county_variant

    return None


def match_area_desc_state(area_desc: str, state: str | None) -> str | None:
    if not state:
        return None

    state_abbreviation = state.strip().upper()
    state_name = STATE_NAMES_BY_ABBREVIATION.get(state_abbreviation, state.strip())
    area_tokens = _normalize_area_tokens(area_desc)

    for candidate in (state_abbreviation, state_name):
        if candidate and _normalize_text(candidate) in area_tokens:
            return candidate

    return None


def point_matches_geometry(longitude: float, latitude: float, geometry: dict[str, Any]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "Polygon":
        return _point_in_polygon(longitude, latitude, coordinates)
    if geometry_type == "MultiPolygon":
        return any(_point_in_polygon(longitude, latitude, polygon) for polygon in coordinates or [])

    return False


def _point_in_polygon(longitude: float, latitude: float, polygon: list[Any] | None) -> bool:
    if not polygon:
        return False

    outer_ring = polygon[0]
    if not _point_in_ring(longitude, latitude, outer_ring):
        return False

    holes = polygon[1:]
    return not any(_point_in_ring(longitude, latitude, hole) for hole in holes)


def _point_in_ring(longitude: float, latitude: float, ring: list[Any]) -> bool:
    if len(ring) < 4:
        return False

    inside = False
    previous_longitude, previous_latitude = ring[-1][0], ring[-1][1]

    for point in ring:
        current_longitude, current_latitude = point[0], point[1]
        intersects = (current_latitude > latitude) != (previous_latitude > latitude)
        if intersects:
            slope_longitude = (
                (previous_longitude - current_longitude)
                * (latitude - current_latitude)
                / (previous_latitude - current_latitude)
                + current_longitude
            )
            if longitude < slope_longitude:
                inside = not inside

        previous_longitude, previous_latitude = current_longitude, current_latitude

    return inside


def _normalize_area_tokens(area_desc: str) -> set[str]:
    return {_normalize_text(token) for token in area_desc.split(";") if token.strip()}


def _county_variants(county: str) -> tuple[str, ...]:
    clean_county = county.strip()
    if _normalize_text(clean_county).endswith(" county"):
        without_suffix = clean_county[: -len(" county")].strip()
        return (clean_county, without_suffix)
    return (clean_county, f"{clean_county} County")


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().replace(",", " ").split())
