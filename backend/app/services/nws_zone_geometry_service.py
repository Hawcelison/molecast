import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.config import Settings, settings
from app.logging_config import get_logger


class NwsZoneGeometryFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class _CacheEntry:
    geometry: dict[str, Any] | None
    expires_at: float


class NwsZoneGeometryService:
    def __init__(self, app_settings: Settings = settings, ttl_seconds: int = 6 * 60 * 60) -> None:
        self.settings = app_settings
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, _CacheEntry] = {}

    def resolve_affected_zones(self, affected_zones: list[str] | None) -> dict[str, Any] | None:
        geometries: list[dict[str, Any]] = []
        for zone_ref in affected_zones or []:
            geometry = self.resolve_zone(zone_ref)
            if geometry is not None:
                geometries.append(geometry)
        return combine_zone_geometries(geometries)

    def resolve_zone(self, zone_ref: str) -> dict[str, Any] | None:
        zone_url = self._zone_url(zone_ref)
        if zone_url is None:
            get_logger().warning("Skipping unsupported NWS zone reference: zone_ref=%s", zone_ref)
            return None

        now = time.monotonic()
        cached = self._cache.get(zone_url)
        if cached and cached.expires_at > now:
            return cached.geometry

        try:
            payload = self._fetch_zone_payload(zone_url)
        except NwsZoneGeometryFetchError:
            get_logger().warning(
                "Unable to fetch NWS zone geometry; continuing without this zone. zone_url=%s",
                zone_url,
                exc_info=True,
            )
            self._cache[zone_url] = _CacheEntry(None, now + min(self.ttl_seconds, 5 * 60))
            return None

        geometry = extract_zone_geometry(payload)
        if geometry is None:
            get_logger().warning("NWS zone response did not include renderable geometry. zone_url=%s", zone_url)
        self._cache[zone_url] = _CacheEntry(geometry, now + self.ttl_seconds)
        return geometry

    def _fetch_zone_payload(self, zone_url: str) -> dict[str, Any]:
        request = Request(
            zone_url,
            headers={
                "Accept": "application/geo+json",
                "User-Agent": self.settings.nws_user_agent,
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise NwsZoneGeometryFetchError(f"Unable to fetch NWS zone JSON: {zone_url}") from exc
        if not isinstance(payload, dict):
            raise NwsZoneGeometryFetchError(f"NWS zone JSON response was not an object: {zone_url}")
        return payload

    def _zone_url(self, zone_ref: str) -> str | None:
        if not isinstance(zone_ref, str) or not zone_ref.strip():
            return None

        clean_ref = zone_ref.strip()
        parsed = urlparse(clean_ref)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return clean_ref

        zone_id = clean_ref.rstrip("/").split("/")[-1].strip().upper()
        if not zone_id:
            return None

        zone_type = _zone_type_from_id(zone_id)
        if zone_type is None:
            return None
        return f"{self._nws_api_base_url()}/zones/{zone_type}/{zone_id}"

    def _nws_api_base_url(self) -> str:
        parsed = urlparse(self.settings.nws_active_alerts_url)
        return f"{parsed.scheme}://{parsed.netloc}"


def extract_zone_geometry(payload: dict[str, Any]) -> dict[str, Any] | None:
    geometry = payload.get("geometry")
    return geometry if is_renderable_geometry(geometry) else None


def combine_zone_geometries(geometries: list[dict[str, Any]]) -> dict[str, Any] | None:
    polygon_groups: list[list[Any]] = []
    for geometry in geometries:
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        if geometry_type == "Polygon" and isinstance(coordinates, list):
            polygon_groups.append(coordinates)
        elif geometry_type == "MultiPolygon" and isinstance(coordinates, list):
            polygon_groups.extend(polygon for polygon in coordinates if isinstance(polygon, list))

    if not polygon_groups:
        return None
    if len(polygon_groups) == 1:
        return {"type": "Polygon", "coordinates": polygon_groups[0]}
    return {"type": "MultiPolygon", "coordinates": polygon_groups}


def is_renderable_geometry(geometry: Any) -> bool:
    return (
        isinstance(geometry, dict)
        and geometry.get("type") in {"Polygon", "MultiPolygon"}
        and isinstance(geometry.get("coordinates"), list)
    )


def _zone_type_from_id(zone_id: str) -> str | None:
    if len(zone_id) < 3:
        return None
    if zone_id[2] == "C":
        return "county"
    if zone_id[2] == "Z":
        return "forecast"
    return None


nws_zone_geometry_service = NwsZoneGeometryService(settings)
