import json
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import ValidationError

from app.config import Settings, settings
from app.logging_config import get_logger
from app.models.location import Location
from app.schemas.alert import WeatherAlert
from app.services.alert_matcher import match_alert_to_location
from app.services.alert_scoring import score_alert, sort_alerts_by_priority
from app.services.alert_time import has_invalid_alert_time, now_utc, parse_alert_time_utc
from app.services.test_alert_loader import TestAlertLoader


class AlertFetchError(RuntimeError):
    pass


class NwsAlertProvider:
    def __init__(self, app_settings: Settings) -> None:
        self.settings = app_settings

    def fetch_active_alerts(self, location: Location) -> dict[str, Any]:
        query_string = urlencode(
            {
                "point": f"{location.latitude},{location.longitude}",
            }
        )
        url = f"{self.settings.nws_active_alerts_url}?{query_string}"
        request = Request(
            url,
            headers={
                "Accept": "application/geo+json",
                "User-Agent": self.settings.nws_user_agent,
            },
        )

        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except OSError as exc:
            raise AlertFetchError("Unable to fetch active NWS alerts.") from exc


class ActiveAlertService:
    def __init__(
        self,
        provider: NwsAlertProvider,
        test_alert_loader: TestAlertLoader,
        refresh_interval_seconds: int,
    ) -> None:
        self.provider = provider
        self.test_alert_loader = test_alert_loader
        self.refresh_interval = timedelta(seconds=refresh_interval_seconds)
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
        test_payload = {
            "features": self.test_alert_loader.load_enabled_alert_features(location),
        }
        test_alerts = parse_nws_alerts(test_payload, location, source="test")

        try:
            live_payload = self.provider.fetch_active_alerts(location)
        except AlertFetchError:
            self.logger.warning(
                "Unable to fetch live NWS alerts; returning local test alerts only. "
                "test_alert_count=%s",
                len(test_alerts),
            )
            live_alerts = []
        else:
            live_alerts = parse_nws_alerts(live_payload, location, source="nws")

        return sort_alerts_by_priority([*live_alerts, *test_alerts])


def parse_nws_alerts(
    payload: dict[str, Any],
    location: Location,
    source: str = "nws",
) -> list[WeatherAlert]:
    alerts: list[WeatherAlert] = []
    logger = get_logger()
    current_time = now_utc()

    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        alert_id = properties.get("id") or feature.get("id")
        match = match_alert_to_location(feature, location)
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

        priority = score_alert(
            properties.get("severity"),
            properties.get("urgency"),
            properties.get("certainty"),
        )
        alert_data = {
            "id": properties.get("id") or feature.get("id"),
            "source": feature.get("source") or properties.get("source") or source,
            "event": properties.get("event"),
            "severity": properties.get("severity"),
            "urgency": properties.get("urgency"),
            "certainty": properties.get("certainty"),
            "headline": properties.get("headline"),
            "description": properties.get("description"),
            "areaDesc": properties.get("areaDesc"),
            "effective": effective_at,
            "expires": expires_at,
            "geometry": feature.get("geometry"),
            "raw_properties": properties,
            "match": {
                "match_type": match.match_type,
                "matched_value": match.matched_value,
                "confidence": match.confidence,
            },
            "priority_score": priority.priority_score,
            "severity_rank": priority.severity_rank,
            "urgency_rank": priority.urgency_rank,
            "certainty_rank": priority.certainty_rank,
        }

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


def is_alert_expired(expires: Any, now: datetime | None = None) -> bool:
    expires_at = parse_alert_time_utc(expires)
    if expires_at is None:
        return False

    current_time = parse_alert_time_utc(now) or now_utc()

    return current_time > expires_at


active_alert_service = ActiveAlertService(
    provider=NwsAlertProvider(settings),
    test_alert_loader=TestAlertLoader(settings),
    refresh_interval_seconds=settings.alert_refresh_seconds,
)
