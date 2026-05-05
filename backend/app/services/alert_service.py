import json
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from pydantic import ValidationError

from app.alerts.details import build_nws_details
from app.alerts.matcher import match_alert_to_location
from app.alerts.models import MolecastAlert
from app.alerts.normalize import normalize_nws_feature_collection
from app.alerts.scoring import score_alert, sort_alerts_by_priority
from app.alerts.test_alert_loader import TestAlertLoader
from app.config import Settings, settings
from app.logging_config import get_logger
from app.models.location import Location
from app.schemas.alert import WeatherAlert
from app.services.alert_time import has_invalid_alert_time, now_utc, parse_alert_time_utc
from app.services.nws_points_service import extract_points_metadata, extract_zone_id
from app.services.nws_zone_geometry_service import NwsZoneGeometryService, nws_zone_geometry_service


class AlertFetchError(RuntimeError):
    pass


class AlertZoneFetchError(RuntimeError):
    pass


class NwsAlertProvider:
    def __init__(self, app_settings: Settings) -> None:
        self.settings = app_settings
        self._cached_points_location_key: str | None = None
        self._cached_points_metadata: dict[str, Any] | None = None

    def fetch_active_alerts(self, location: Location) -> dict[str, Any]:
        payloads: list[dict[str, Any]] = []
        point_error: AlertFetchError | None = None

        try:
            payloads.append(self._fetch_point_alerts(location))
        except AlertFetchError as exc:
            point_error = exc

        for zone_id in self._get_alert_zone_ids(location):
            try:
                payloads.append(self._fetch_zone_alerts(zone_id))
            except AlertZoneFetchError:
                get_logger().warning(
                    "Unable to fetch active NWS zone alerts; continuing with other alert feeds. "
                    "zone_id=%s",
                    zone_id,
                    exc_info=True,
                )

        if not payloads:
            raise point_error or AlertFetchError("Unable to fetch active NWS alerts.")

        return {"type": "FeatureCollection", "features": self._dedupe_features(payloads)}

    def fetch_zone_alerts(self, zone_id: str) -> dict[str, Any]:
        return self._fetch_zone_alerts(zone_id)

    def fetch_point_alerts(self, location: Location) -> dict[str, Any]:
        return self._fetch_point_alerts(location)

    def get_points_metadata(self, location: Location) -> dict[str, Any] | None:
        location_key = self._get_location_key(location)
        if self._cached_points_location_key == location_key:
            return self._cached_points_metadata

        try:
            payload = self._fetch_points_payload(location)
        except AlertFetchError:
            get_logger().warning(
                "Unable to fetch NWS point metadata; continuing without zone alert feeds. "
                "location=%s,%s",
                location.latitude,
                location.longitude,
                exc_info=True,
            )
            return None

        metadata = extract_points_metadata(payload)
        self._cached_points_location_key = location_key
        self._cached_points_metadata = metadata
        return metadata

    def _fetch_point_alerts(self, location: Location) -> dict[str, Any]:
        query_string = urlencode(
            {
                "point": f"{location.latitude},{location.longitude}",
            }
        )
        url = f"{self.settings.nws_active_alerts_url}?{query_string}"
        try:
            return self._fetch_json(url, accept="application/geo+json")
        except AlertFetchError as exc:
            raise AlertFetchError("Unable to fetch active NWS alerts.") from exc

    def _fetch_zone_alerts(self, zone_id: str) -> dict[str, Any]:
        url = f"{self._nws_api_base_url()}/alerts/active/zone/{zone_id}"
        try:
            return self._fetch_json(url, accept="application/geo+json")
        except AlertFetchError as exc:
            raise AlertZoneFetchError(f"Unable to fetch active NWS alerts for zone {zone_id}.") from exc

    def _fetch_points_payload(self, location: Location) -> dict[str, Any]:
        url = f"{self._nws_api_base_url()}/points/{location.latitude},{location.longitude}"
        return self._fetch_json(url, accept="application/geo+json")

    def _fetch_json(self, url: str, accept: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={
                "Accept": accept,
                "User-Agent": self.settings.nws_user_agent,
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AlertFetchError(f"Unable to fetch NWS JSON: {url}") from exc
        if not isinstance(payload, dict):
            raise AlertFetchError(f"NWS JSON response was not an object: {url}")
        return payload

    def _get_alert_zone_ids(self, location: Location) -> list[str]:
        persisted_zone_ids = [
            zone_id
            for zone_id in (location.county_zone, location.forecast_zone, location.fire_weather_zone)
            if zone_id
        ]
        if persisted_zone_ids:
            return list(dict.fromkeys(persisted_zone_ids))

        metadata = self.get_points_metadata(location)
        if not metadata:
            return []

        zone_ids: list[str] = []
        for key in ("county", "forecastZone", "fireWeatherZone"):
            zone_id = extract_zone_id(metadata.get(key))
            if zone_id and zone_id not in zone_ids:
                zone_ids.append(zone_id)
        return zone_ids

    def _dedupe_features(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        features: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for payload in payloads:
            raw_features = payload.get("features", [])
            if not isinstance(raw_features, list):
                continue
            for feature in raw_features:
                if not isinstance(feature, dict):
                    continue
                stable_id = stable_alert_feature_id(feature)
                if stable_id in seen_ids:
                    continue
                seen_ids.add(stable_id)
                features.append(feature)
        return features

    def _nws_api_base_url(self) -> str:
        parsed = urlparse(self.settings.nws_active_alerts_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _get_location_key(self, location: Location) -> str:
        return f"{location.id}:{location.latitude}:{location.longitude}"


def stable_alert_feature_id(feature: dict[str, Any]) -> str:
    properties = feature.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    for value in (
        properties.get("canonical_id"),
        properties.get("canonicalId"),
        properties.get("id"),
        properties.get("@id"),
        properties.get("identifier"),
        feature.get("canonical_id"),
        feature.get("canonicalId"),
        feature.get("id"),
        feature.get("@id"),
    ):
        if value:
            return str(value)
    return json.dumps(feature, sort_keys=True, default=str)


class ActiveAlertService:
    def __init__(
        self,
        provider: NwsAlertProvider,
        test_alert_loader: TestAlertLoader,
        refresh_interval_seconds: int,
        zone_geometry_service: NwsZoneGeometryService | None = None,
    ) -> None:
        self.provider = provider
        self.test_alert_loader = test_alert_loader
        self.refresh_interval = timedelta(seconds=refresh_interval_seconds)
        self.zone_geometry_service = zone_geometry_service
        self._cached_location_key: str | None = None
        self._cached_alerts: list[WeatherAlert] = []
        self._last_refreshed_at: datetime | None = None
        self._cached_test_alert_mtime: float | None = None
        self.logger = get_logger()

    def get_active_alerts(self, location: Location) -> tuple[list[WeatherAlert], datetime]:
        now = now_utc()
        location_key = self._get_location_key(location)
        test_alert_mtime = self.test_alert_loader.alert_file_mtime()

        if self._can_use_cache(location_key, now, test_alert_mtime):
            return self._cached_alerts, self._last_refreshed_at or now

        alerts = self._load_active_alerts(location)

        self._cached_location_key = location_key
        self._cached_alerts = alerts
        self._last_refreshed_at = now
        self._cached_test_alert_mtime = test_alert_mtime

        return alerts, now

    def refresh_active_alerts(self, location: Location) -> tuple[list[WeatherAlert], datetime]:
        test_alert_mtime = self.test_alert_loader.alert_file_mtime()
        alerts = self._load_active_alerts(location)
        refreshed_at = now_utc()

        self._cached_location_key = self._get_location_key(location)
        self._cached_alerts = alerts
        self._last_refreshed_at = refreshed_at
        self._cached_test_alert_mtime = test_alert_mtime

        return alerts, refreshed_at

    def _can_use_cache(
        self,
        location_key: str,
        now: datetime,
        test_alert_mtime: float | None,
    ) -> bool:
        if self._last_refreshed_at is None:
            return False
        if self._cached_location_key != location_key:
            return False
        if self._cached_test_alert_mtime != test_alert_mtime:
            return False
        return now - self._last_refreshed_at < self.refresh_interval

    def _get_location_key(self, location: Location) -> str:
        return f"{location.id}:{location.latitude}:{location.longitude}"

    def _load_active_alerts(self, location: Location) -> list[WeatherAlert]:
        test_alerts: list[WeatherAlert] = []
        if _test_alert_loader_enabled(self.test_alert_loader):
            test_payload = {
                "features": self.test_alert_loader.load_enabled_alert_features(location),
            }
            test_alerts = parse_nws_alerts(
                test_payload,
                location,
                source="test",
                zone_geometry_service=self.zone_geometry_service,
            )

        try:
            live_payload = self.provider.fetch_active_alerts(location)
        except AlertFetchError:
            fallback_description = "local test alerts only" if test_alerts else "no alerts"
            self.logger.warning(
                "Unable to fetch live NWS alerts; returning %s. "
                "test_alert_count=%s",
                fallback_description,
                len(test_alerts),
            )
            live_alerts = []
        else:
            live_alerts = parse_nws_alerts(
                live_payload,
                location,
                source="nws",
                zone_geometry_service=self.zone_geometry_service,
            )

        return sort_alerts_by_priority(dedupe_alerts_by_id([*live_alerts, *test_alerts]))


def parse_nws_alerts(
    payload: dict[str, Any],
    location: Location,
    source: str = "nws",
    zone_geometry_service: NwsZoneGeometryService | None = None,
) -> list[WeatherAlert]:
    alerts: list[WeatherAlert] = []
    logger = get_logger()
    current_time = now_utc()

    try:
        normalized_alerts = normalize_nws_feature_collection(payload, source=source)
    except ValueError:
        logger.warning("Skipping malformed NWS alert payload: source=%s payload=%r", source, payload)
        return []

    for normalized_alert in normalized_alerts:
        feature = normalized_alert.raw_feature
        properties = normalized_alert.raw_properties
        alert_id = normalized_alert.id
        try:
            match = match_alert_to_location(feature, location)
        except Exception:
            logger.warning(
                "Skipping alert with malformed match data: source=%s id=%s geometry=%s",
                source,
                alert_id,
                "present" if feature.get("geometry") else "missing",
                exc_info=True,
            )
            continue
        if match is None:
            logger.debug(
                "Filtered alert with no location match: source=%s id=%s areaDesc=%s "
                "geometry=%s location=%s,%s county=%s state=%s",
                source,
                alert_id,
                properties.get("areaDesc"),
                "present" if feature.get("geometry") else "missing",
                location.latitude,
                location.longitude,
                location.county,
                location.state,
            )
            continue

        if has_invalid_alert_time(properties.get("effective")) or has_invalid_alert_time(
            properties.get("expires")
        ):
            logger.debug(
                "Filtered alert with invalid timestamp: source=%s id=%s "
                "effective=%s expires=%s now_utc=%s",
                source,
                alert_id,
                properties.get("effective"),
                properties.get("expires"),
                current_time.isoformat(),
            )
            continue

        expires_at = parse_alert_time_utc(properties.get("expires"))
        if expires_at is not None and is_alert_expired(expires_at, current_time):
            logger.debug(
                "Filtered expired alert: source=%s id=%s effective=%s expires=%s "
                "parsed_expires=%s now_utc=%s",
                source,
                alert_id,
                properties.get("effective"),
                properties.get("expires"),
                expires_at.isoformat(),
                current_time.isoformat(),
            )
            continue
        effective_at = parse_alert_time_utc(properties.get("effective"))
        if effective_at is not None and current_time < effective_at:
            logger.debug(
                "Filtered future alert: source=%s id=%s effective=%s expires=%s "
                "parsed_effective=%s now_utc=%s",
                source,
                alert_id,
                properties.get("effective"),
                properties.get("expires"),
                effective_at.isoformat(),
                current_time.isoformat(),
            )
            continue

        geometry = normalized_alert.geometry
        geometry_source = "alert" if geometry is not None else None
        if geometry is None and normalized_alert.affectedZones and zone_geometry_service is not None:
            try:
                geometry = zone_geometry_service.resolve_affected_zones(normalized_alert.affectedZones)
            except Exception:
                logger.warning(
                    "Unable to resolve affected-zone geometry; keeping alert without map geometry. "
                    "source=%s id=%s affected_zones=%s",
                    source,
                    alert_id,
                    normalized_alert.affectedZones,
                    exc_info=True,
                )
                geometry = None
            if geometry is not None:
                geometry_source = "affectedZones"

        ranking = score_alert(
            normalized_alert.severity,
            normalized_alert.urgency,
            normalized_alert.certainty,
        )
        alert_data = _weather_alert_data(normalized_alert, match, ranking, geometry, geometry_source)

        try:
            alerts.append(WeatherAlert.model_validate(alert_data))
            logger.debug(
                "Accepted alert: source=%s id=%s match_type=%s effective=%s expires=%s "
                "now_utc=%s",
                source,
                alert_id,
                match.match_type,
                effective_at.isoformat() if effective_at else None,
                expires_at.isoformat() if expires_at else None,
                current_time.isoformat(),
            )
        except ValidationError:
            logger.debug(
                "Filtered alert failing schema validation: source=%s id=%s",
                source,
                alert_id,
                exc_info=True,
            )
            continue

    return sort_alerts_by_priority(alerts)


def _weather_alert_data(
    normalized_alert: MolecastAlert,
    match: Any,
    ranking: Any,
    geometry: dict[str, Any] | None,
    geometry_source: str | None,
) -> dict[str, Any]:
    raw_properties = dict(normalized_alert.raw_properties)
    if normalized_alert.color_hex is not None:
        raw_properties["color_hex"] = normalized_alert.color_hex
    if normalized_alert.icon is not None:
        raw_properties["icon"] = normalized_alert.icon
    if normalized_alert.priority is not None:
        raw_properties["priority"] = normalized_alert.priority
    if normalized_alert.sound_profile is not None:
        raw_properties["sound_profile"] = normalized_alert.sound_profile
    if normalized_alert.geocode is not None:
        raw_properties["normalized_geocode"] = normalized_alert.geocode

    priority = normalized_alert.priority or ranking.priority_score

    return {
        "id": normalized_alert.id,
        "source": normalized_alert.source,
        "event": normalized_alert.event,
        "severity": normalized_alert.severity,
        "urgency": normalized_alert.urgency,
        "certainty": normalized_alert.certainty,
        "headline": normalized_alert.headline,
        "description": normalized_alert.description,
        "areaDesc": normalized_alert.areaDesc,
        "affectedZones": normalized_alert.affectedZones,
        "effective": normalized_alert.effective,
        "expires": normalized_alert.expires,
        "geometry": geometry,
        "geometry_source": geometry_source or "none",
        "raw_properties": raw_properties,
        "match": {
            "match_type": match.match_type,
            "matched_value": match.matched_value,
            "confidence": match.confidence,
        },
        "color_hex": normalized_alert.color_hex,
        "icon": normalized_alert.icon,
        "sound_profile": normalized_alert.sound_profile,
        "priority": priority,
        "priority_score": priority,
        "severity_rank": ranking.severity_rank,
        "urgency_rank": ranking.urgency_rank,
        "certainty_rank": ranking.certainty_rank,
        "nws_details": build_nws_details(normalized_alert.parameters),
    }


def dedupe_alerts_by_id(alerts: list[WeatherAlert]) -> list[WeatherAlert]:
    deduped: dict[str, WeatherAlert] = {}
    order: list[str] = []
    for alert in alerts:
        existing = deduped.get(alert.id)
        if existing is None:
            deduped[alert.id] = alert
            order.append(alert.id)
            continue
        deduped[alert.id] = choose_preferred_alert(existing, alert)
    return [deduped[alert_id] for alert_id in order]


def choose_preferred_alert(current: WeatherAlert, candidate: WeatherAlert) -> WeatherAlert:
    if candidate.priority > current.priority:
        return candidate
    if candidate.priority < current.priority:
        return current

    candidate_time = candidate.effective or candidate.expires
    current_time = current.effective or current.expires
    if candidate_time and current_time and candidate_time > current_time:
        return candidate
    if candidate_time and current_time is None:
        return candidate
    return current


def is_alert_expired(expires: Any, now: datetime | None = None) -> bool:
    expires_at = parse_alert_time_utc(expires)
    if expires_at is None:
        return False

    current_time = parse_alert_time_utc(now) or now_utc()

    return current_time > expires_at


def _test_alert_loader_enabled(test_alert_loader: TestAlertLoader) -> bool:
    loader_settings = getattr(test_alert_loader, "settings", None)
    return bool(getattr(loader_settings, "test_alerts_enabled", True))


active_alert_service = ActiveAlertService(
    provider=NwsAlertProvider(settings),
    test_alert_loader=TestAlertLoader(settings),
    refresh_interval_seconds=settings.alert_refresh_seconds,
    zone_geometry_service=nws_zone_geometry_service,
)
