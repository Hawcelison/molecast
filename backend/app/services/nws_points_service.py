import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.config import Settings, settings


class NwsPointsFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class NwsPointsMetadata:
    nws_office: str | None = None
    nws_grid_x: int | None = None
    nws_grid_y: int | None = None
    forecast_zone: str | None = None
    county_zone: str | None = None
    fire_weather_zone: str | None = None
    timezone: str | None = None

    def has_values(self) -> bool:
        return any(
            value is not None
            for value in (
                self.nws_office,
                self.nws_grid_x,
                self.nws_grid_y,
                self.forecast_zone,
                self.county_zone,
                self.fire_weather_zone,
                self.timezone,
            )
        )

    def location_updates(self, updated_at: datetime) -> dict[str, str | int | datetime | None]:
        return {
            "nws_office": self.nws_office,
            "nws_grid_x": self.nws_grid_x,
            "nws_grid_y": self.nws_grid_y,
            "forecast_zone": self.forecast_zone,
            "county_zone": self.county_zone,
            "fire_weather_zone": self.fire_weather_zone,
            "timezone": self.timezone,
            "nws_points_updated_at": updated_at,
        }


POINT_METADATA_FIELDS = (
    "gridId",
    "gridX",
    "gridY",
    "county",
    "forecastZone",
    "fireWeatherZone",
    "timeZone",
)


class NwsPointsService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings

    def fetch_points_metadata(self, latitude: float, longitude: float) -> NwsPointsMetadata:
        payload = self._fetch_points_payload(latitude, longitude)
        return parse_points_metadata(payload)

    def _fetch_points_payload(self, latitude: float, longitude: float) -> dict[str, Any]:
        url = f"{self._nws_api_base_url()}/points/{latitude},{longitude}"
        request = Request(
            url,
            headers={
                "Accept": "application/geo+json",
                "User-Agent": self.settings.nws_user_agent,
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise NwsPointsFetchError(f"Unable to fetch NWS points metadata: {url}") from exc
        if not isinstance(payload, dict):
            raise NwsPointsFetchError(f"NWS points response was not an object: {url}")
        return payload

    def _nws_api_base_url(self) -> str:
        parsed = urlparse(self.settings.nws_active_alerts_url)
        return f"{parsed.scheme}://{parsed.netloc}"


def parse_points_metadata(payload: dict[str, Any]) -> NwsPointsMetadata:
    properties = payload.get("properties", {})
    if not isinstance(properties, dict):
        return NwsPointsMetadata()

    return NwsPointsMetadata(
        nws_office=_clean_string(properties.get("gridId")),
        nws_grid_x=_clean_int(properties.get("gridX")),
        nws_grid_y=_clean_int(properties.get("gridY")),
        forecast_zone=extract_zone_id(properties.get("forecastZone")),
        county_zone=extract_zone_id(properties.get("county")),
        fire_weather_zone=extract_zone_id(properties.get("fireWeatherZone")),
        timezone=_clean_string(properties.get("timeZone")),
    )


def extract_points_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    properties = payload.get("properties", {})
    if not isinstance(properties, dict):
        return {}
    return {field: properties.get(field) for field in POINT_METADATA_FIELDS if field in properties}


def extract_zone_id(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlparse(value.strip())
    path = parsed.path if parsed.scheme else value.strip()
    zone_id = path.rstrip("/").split("/")[-1].strip()
    return zone_id or None


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _clean_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


nws_points_service = NwsPointsService(settings)
