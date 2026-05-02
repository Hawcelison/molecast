from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Settings, settings
from app.geocoders.base import (
    AddressGeocodeCandidate,
    AddressGeocodeRequest,
    AddressGeocodeResponse,
    AddressGeocoderBadResponse,
    AddressGeocoderTimeout,
    AddressGeocoderUnavailable,
    AddressGeocoderValidationError,
    normalize_address_request,
)


CENSUS_ATTRIBUTION = (
    "This product uses the Census Bureau Data API but is not endorsed or certified "
    "by the Census Bureau."
)
APPROXIMATE_WARNING = "Address point may be approximate."


class CensusAddressGeocoder:
    provider_name = "census"
    attribution = CENSUS_ATTRIBUTION

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings

    def geocode(self, request: AddressGeocodeRequest) -> AddressGeocodeResponse:
        normalized = normalize_address_request(request)
        payload = self._fetch_payload(normalized)
        candidates = parse_census_candidates(payload)
        limited_candidates = candidates[: normalized.limit]
        return AddressGeocodeResponse(
            query=normalized.query,
            provider=self.provider_name,
            count=len(limited_candidates),
            candidates=limited_candidates,
            attribution=self.attribution,
        )

    def _fetch_payload(self, normalized_request) -> dict[str, Any]:
        url = self._build_url(normalized_request)
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": self.settings.geocoder_user_agent,
            },
        )
        try:
            with urlopen(request, timeout=self.settings.geocoder_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise AddressGeocoderTimeout("Census geocoder request timed out.") from exc
        except HTTPError as exc:
            raise AddressGeocoderUnavailable(
                f"Census geocoder returned HTTP {exc.code}."
            ) from exc
        except URLError as exc:
            raise AddressGeocoderUnavailable("Census geocoder is unavailable.") from exc
        except OSError as exc:
            raise AddressGeocoderUnavailable("Census geocoder request failed.") from exc
        except json.JSONDecodeError as exc:
            raise AddressGeocoderBadResponse("Census geocoder returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise AddressGeocoderBadResponse("Census geocoder response was not an object.")
        return payload

    def _build_url(self, normalized_request) -> str:
        endpoint = (
            f"{self.settings.census_geocoder_base_url.rstrip('/')}"
            f"/locations/{normalized_request.search_type}"
        )
        query: dict[str, str] = {
            "benchmark": self.settings.census_geocoder_benchmark,
            "format": "json",
            "returntype": "locations",
        }
        if normalized_request.search_type == "onelineaddress":
            if not normalized_request.address:
                raise AddressGeocoderValidationError("One-line address is required.")
            query["address"] = normalized_request.address
        else:
            if not normalized_request.street:
                raise AddressGeocoderValidationError("Street is required.")
            query["street"] = normalized_request.street
            if normalized_request.city:
                query["city"] = normalized_request.city
            if normalized_request.state:
                query["state"] = normalized_request.state
            if normalized_request.zip_code:
                query["zip"] = normalized_request.zip_code
        return f"{endpoint}?{urlencode(query)}"


def parse_census_candidates(payload: dict[str, Any]) -> list[AddressGeocodeCandidate]:
    result = payload.get("result")
    if not isinstance(result, dict):
        raise AddressGeocoderBadResponse("Census geocoder response missing result object.")

    matches = result.get("addressMatches", [])
    if matches is None:
        matches = []
    if not isinstance(matches, list):
        raise AddressGeocoderBadResponse("Census addressMatches was not a list.")

    candidates: list[AddressGeocodeCandidate] = []
    for index, match in enumerate(matches):
        if not isinstance(match, dict):
            continue
        candidate = parse_census_match(match, index)
        if candidate:
            candidates.append(candidate)
    return candidates


def parse_census_match(match: dict[str, Any], index: int) -> AddressGeocodeCandidate | None:
    coordinates = match.get("coordinates")
    if not isinstance(coordinates, dict):
        return None

    latitude = _clean_float(coordinates.get("y"), minimum=-90, maximum=90)
    longitude = _clean_float(coordinates.get("x"), minimum=-180, maximum=180)
    if latitude is None or longitude is None:
        return None

    components = match.get("addressComponents", {})
    if not isinstance(components, dict):
        components = {}

    matched_address = _clean_string(match.get("matchedAddress")) or "Matched address"
    city = _clean_string(components.get("city"))
    state = _clean_string(components.get("state"))
    zip_code = _clean_string(components.get("zip"))

    return AddressGeocodeCandidate(
        ref=census_ref(match, index),
        matched_address=matched_address,
        display_label=display_label(matched_address, city, state, zip_code),
        latitude=latitude,
        longitude=longitude,
        city=city,
        state=state,
        zip_code=zip_code,
        source="census",
        accuracy="address_range_interpolated",
        match_quality="matched",
        score=None,
        warnings=[APPROXIMATE_WARNING],
        raw=match,
    )


def census_ref(match: dict[str, Any], index: int) -> str:
    tiger_line = match.get("tigerLine")
    if isinstance(tiger_line, dict):
        tiger_line_id = _clean_string(tiger_line.get("tigerLineId")) or _clean_string(
            tiger_line.get("id")
        )
        side = _clean_string(tiger_line.get("side")) or "unknown"
        if tiger_line_id:
            return f"census:{tiger_line_id}:{side}:{index}"
    return f"census:{index}"


def display_label(
    matched_address: str,
    city: str | None,
    state: str | None,
    zip_code: str | None,
) -> str:
    city_state = ", ".join(part for part in (city, state) if part)
    if city_state or zip_code:
        return f"{city_state} {zip_code or ''}".strip()
    return matched_address


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_float(value: Any, *, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not (minimum <= parsed <= maximum):
        return None
    return parsed
