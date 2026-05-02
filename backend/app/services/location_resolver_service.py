from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.repositories.location_lookup_repository import (
    CityLocationRecord,
    LocationLookupRepository,
    ZipLocationRecord,
)
from app.schemas.location_resolver import (
    LocationSearchResponse,
    LocationSearchSuggestion,
    NwsPointPreviewResponse,
)
from app.services.nws_points_service import NwsPointsService, nws_points_service


MIN_SEARCH_QUERY_LENGTH = 2
DEFAULT_SEARCH_LIMIT = 8
MAX_SEARCH_LIMIT = 20
VALID_SEARCH_TYPES = {"zip", "city"}
OFFICE_MAPPING_PATH = settings.app_dir / "data" / "nws_offices.json"


class InvalidLocationSearchTypeError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedCityQuery:
    city: str
    state: str | None = None


class LocationResolverService:
    def __init__(
        self,
        repository: LocationLookupRepository,
        points_service: NwsPointsService = nws_points_service,
    ) -> None:
        self.repository = repository
        self.points_service = points_service

    def search(
        self,
        query: str,
        limit: int = DEFAULT_SEARCH_LIMIT,
        types: str | None = None,
    ) -> LocationSearchResponse:
        normalized_query = normalize_search_query(query)
        capped_limit = normalize_search_limit(limit)
        search_types = parse_search_types(types)

        if len(normalized_query) < MIN_SEARCH_QUERY_LENGTH:
            return LocationSearchResponse(query=normalized_query, count=0, results=[])

        results: list[LocationSearchSuggestion] = []
        seen_refs: set[str] = set()

        if "zip" in search_types:
            for record in self.repository.search_zip_prefix(_zip_query(normalized_query), capped_limit):
                _append_unique(results, seen_refs, zip_suggestion(record), capped_limit)

        if "city" in search_types and len(results) < capped_limit:
            parsed_city_query = parse_city_query(normalized_query)
            remaining_limit = capped_limit - len(results)
            for record in self.repository.search_city_prefix(
                parsed_city_query.city,
                remaining_limit,
                parsed_city_query.state,
            ):
                _append_unique(results, seen_refs, city_suggestion(record), capped_limit)

        return LocationSearchResponse(
            query=normalized_query,
            count=len(results),
            results=results,
        )

    def preview_nws_point(self, latitude: float, longitude: float) -> NwsPointPreviewResponse:
        metadata = self.points_service.fetch_points_metadata(latitude, longitude)
        office = normalize_office_id(metadata.nws_office)
        office_code = office_code_for(office)
        office_name = office_name_for(office)

        return NwsPointPreviewResponse(
            latitude=latitude,
            longitude=longitude,
            nws_office=office,
            nws_office_code=office_code,
            nws_office_name=office_name,
            nws_grid_x=metadata.nws_grid_x,
            nws_grid_y=metadata.nws_grid_y,
            forecast_zone=metadata.forecast_zone,
            county_zone=metadata.county_zone,
            fire_weather_zone=metadata.fire_weather_zone,
            timezone=metadata.timezone,
            status="ok",
            updated_at=datetime.now(UTC),
        )


def normalize_search_query(query: str | None) -> str:
    if query is None:
        return ""
    return re.sub(r"\s+", " ", query.strip())


def normalize_search_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_SEARCH_LIMIT
    return min(max(int(limit), 1), MAX_SEARCH_LIMIT)


def parse_search_types(types: str | None) -> set[str]:
    if not types:
        return set(VALID_SEARCH_TYPES)

    parsed_types = {item.strip().lower() for item in types.split(",") if item.strip()}
    if not parsed_types:
        return set(VALID_SEARCH_TYPES)
    invalid_types = parsed_types - VALID_SEARCH_TYPES
    if invalid_types:
        raise InvalidLocationSearchTypeError(
            f"Unsupported location search type: {', '.join(sorted(invalid_types))}."
        )
    return parsed_types


def parse_city_query(query: str) -> ParsedCityQuery:
    city_state_query = re.sub(r"[,]+", " ", query)
    parts = city_state_query.split()
    if len(parts) >= 2 and len(parts[-1]) == 2 and parts[-1].isalpha():
        return ParsedCityQuery(city=" ".join(parts[:-1]), state=parts[-1].upper())
    return ParsedCityQuery(city=city_state_query)


def zip_suggestion(record: ZipLocationRecord) -> LocationSearchSuggestion:
    county = format_county(record.county)
    county_label = f" - {county}" if county else ""
    return LocationSearchSuggestion(
        ref=f"zip:{record.zip_code}",
        kind="zip",
        label=f"{record.zip_code} - {record.primary_city}, {record.state}{county_label}",
        zip=record.zip_code,
        city=record.primary_city,
        state=record.state,
        county=county,
        latitude=record.latitude,
        longitude=record.longitude,
        default_zoom=record.default_zoom,
        accuracy="zip_centroid",
        source="local",
    )


def city_suggestion(record: CityLocationRecord) -> LocationSearchSuggestion:
    county = format_county(record.county)
    return LocationSearchSuggestion(
        ref=f"city:{slugify_ref(record.primary_city)}-{record.state.lower()}",
        kind="city",
        label=f"{record.primary_city}, {record.state}",
        city=record.primary_city,
        state=record.state,
        county=county,
        latitude=record.latitude,
        longitude=record.longitude,
        default_zoom=max(record.default_zoom, 10),
        accuracy="city_representative",
        source="local",
    )


def format_county(county: str | None) -> str | None:
    if not county:
        return None
    county = county.strip()
    if county.lower().endswith(" county"):
        return county
    return f"{county} County"


def slugify_ref(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def normalize_office_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().upper()
    return normalized or None


def office_code_for(office: str | None) -> str | None:
    if not office:
        return None
    mapped = get_nws_office_mapping().get(mapping_key_for(office), {})
    office_code = mapped.get("office_code")
    if isinstance(office_code, str) and office_code.strip():
        return office_code.strip().upper()
    return office if office.startswith("K") else f"K{office}"


def office_name_for(office: str | None) -> str | None:
    if not office:
        return None
    mapped = get_nws_office_mapping().get(mapping_key_for(office), {})
    name = mapped.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return office


def mapping_key_for(office: str) -> str:
    return office[1:] if office.startswith("K") and len(office) == 4 else office


@lru_cache
def get_nws_office_mapping() -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(OFFICE_MAPPING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}

    mapping: dict[str, dict[str, str]] = {}
    for office, details in payload.items():
        if not isinstance(office, str) or not isinstance(details, dict):
            continue
        office_key = mapping_key_for(office.strip().upper())
        mapping[office_key] = {
            key: value
            for key, value in details.items()
            if key in {"office_code", "name"} and isinstance(value, str)
        }
    return mapping


def _append_unique(
    results: list[LocationSearchSuggestion],
    seen_refs: set[str],
    suggestion: LocationSearchSuggestion,
    limit: int,
) -> None:
    if len(results) >= limit or suggestion.ref in seen_refs:
        return
    seen_refs.add(suggestion.ref)
    results.append(suggestion)


def _zip_query(query: str) -> str:
    return query[:5] if query.isdigit() else query


@lru_cache
def get_location_resolver_service() -> LocationResolverService:
    db_path: Path = settings.app_dir / "data" / "location_lookup.sqlite3"
    return LocationResolverService(LocationLookupRepository(db_path))
