import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError

from app.alerts.matcher import AlertMatch, point_matches_geometry
from app.alerts.models import MolecastAlert
from app.alerts.normalize import normalize_nws_feature_collection
from app.alerts.scoring import score_alert, sort_alerts_by_priority
from app.alerts.summary import build_alert_summary
from app.alerts.test_alert_loader import TestAlertLoader
from app.logging_config import get_logger
from app.models.location import Location
from app.schemas.alert import AlertSummaryResponse, WeatherAlert
from app.services.alert_service import (
    AlertFetchError,
    AlertZoneFetchError,
    NwsAlertProvider,
    _weather_alert_data,
    choose_preferred_alert,
    stable_alert_feature_id,
)
from app.services.alert_time import has_invalid_alert_time, now_utc, parse_alert_time_utc
from app.services.nws_points_service import extract_zone_id
from app.services.nws_zone_geometry_service import NwsZoneGeometryService


@dataclass
class _AggregatedAlert:
    key: str
    alert: WeatherAlert
    affected_locations: list[dict[str, Any]] = field(default_factory=list)


class SavedAlertSummaryService:
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
        self.refresh_interval_seconds = refresh_interval_seconds
        self.zone_geometry_service = zone_geometry_service
        self._cached_fingerprint: str | None = None
        self._cached_summary: AlertSummaryResponse | None = None
        self._last_refreshed_at: datetime | None = None
        self.logger = get_logger()

    def get_saved_summary(self, locations: list[Location]) -> AlertSummaryResponse:
        now = now_utc()
        locations = _dedupe_locations(locations)
        test_alert_mtime = self.test_alert_loader.alert_file_mtime()
        fingerprint = _saved_location_fingerprint(locations, test_alert_mtime)

        if self._can_use_cache(fingerprint, now):
            return self._cached_summary or self._empty_summary(locations, now)

        features_by_source, errors = self._load_features(locations)
        aggregated = _aggregate_alerts(
            locations,
            features_by_source,
            zone_geometry_service=self.zone_geometry_service,
        )
        alerts = sort_alerts_by_priority([item.alert for item in aggregated])
        aggregate_by_alert_id = {(item.alert.source, item.alert.id): item for item in aggregated}
        alert_refs = [
            _alert_ref(aggregate_by_alert_id[(alert.source, alert.id)])
            for alert in alerts
            if (alert.source, alert.id) in aggregate_by_alert_id
        ]
        affected_location_ids = {
            location["id"] for item in aggregated for location in item.affected_locations
        }

        summary = build_alert_summary(
            alerts,
            scope="saved",
            scope_label="All Saved Locations",
            updated_at=now,
            refresh_interval_seconds=self.refresh_interval_seconds,
            saved_location_count=len(locations),
            affected_location_count=len(affected_location_ids),
            partial=bool(errors),
            errors=errors,
            alert_refs=alert_refs,
        )

        self._cached_fingerprint = fingerprint
        self._cached_summary = summary
        self._last_refreshed_at = now
        return summary

    def _can_use_cache(self, fingerprint: str, now: datetime) -> bool:
        if self._cached_summary is None or self._last_refreshed_at is None:
            return False
        if self._cached_fingerprint != fingerprint:
            return False
        return now - self._last_refreshed_at < self.refresh_interval

    def _empty_summary(self, locations: list[Location], updated_at: datetime) -> AlertSummaryResponse:
        return build_alert_summary(
            [],
            scope="saved",
            scope_label="All Saved Locations",
            updated_at=updated_at,
            refresh_interval_seconds=self.refresh_interval_seconds,
            saved_location_count=len(locations),
            affected_location_count=0,
            partial=False,
            errors=[],
            alert_refs=[],
        )

    def _load_features(self, locations: list[Location]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
        features_by_source: dict[str, list[dict[str, Any]]] = {"nws": [], "test": []}
        errors: list[str] = []

        seen_nws_feature_ids: set[str] = set()
        for zone_id in _unique_zone_ids(locations):
            try:
                payload = self.provider.fetch_zone_alerts(zone_id)
            except (AlertFetchError, AlertZoneFetchError) as exc:
                self.logger.warning(
                    "Unable to fetch saved-location NWS zone alerts; continuing. zone_id=%s",
                    zone_id,
                    exc_info=True,
                )
                errors.append(f"NWS zone {zone_id}: {exc}")
                continue
            _extend_unique_features(features_by_source["nws"], seen_nws_feature_ids, payload)

        for location in locations:
            if _location_zone_ids(location):
                continue
            try:
                payload = self.provider.fetch_active_alerts(location)
            except AlertFetchError as exc:
                self.logger.warning(
                    "Unable to fetch saved-location fallback NWS alerts; continuing. location_id=%s",
                    location.id,
                    exc_info=True,
                )
                errors.append(f"NWS location {location.id}: {exc}")
                continue
            _extend_unique_features(features_by_source["nws"], seen_nws_feature_ids, payload)

        if locations:
            try:
                test_features = self.test_alert_loader.load_enabled_alert_features(
                    locations[0],
                    include_location_area_fallback=False,
                )
            except TypeError:
                test_features = self.test_alert_loader.load_enabled_alert_features(locations[0])
            features_by_source["test"] = test_features

        return features_by_source, errors


def _aggregate_alerts(
    locations: list[Location],
    features_by_source: dict[str, list[dict[str, Any]]],
    *,
    zone_geometry_service: NwsZoneGeometryService | None,
) -> list[_AggregatedAlert]:
    aggregated_by_key: dict[str, _AggregatedAlert] = {}
    order: list[str] = []

    for source, features in features_by_source.items():
        normalized_alerts = _normalize_features(features, source)
        for normalized_alert in normalized_alerts:
            if _should_skip_alert_time(normalized_alert):
                continue

            matches = [
                (location, match)
                for location in locations
                if (match := match_saved_alert_to_location(normalized_alert, location, source)) is not None
            ]
            if not matches:
                continue

            weather_alert = _weather_alert_from_normalized(
                normalized_alert,
                matches[0][1],
                zone_geometry_service=zone_geometry_service,
            )
            if weather_alert is None:
                continue

            key = _stable_source_alert_key(normalized_alert)
            affected_locations = [_affected_location_ref(location, match) for location, match in matches]
            existing = aggregated_by_key.get(key)
            if existing is None:
                aggregated_by_key[key] = _AggregatedAlert(
                    key=key,
                    alert=weather_alert,
                    affected_locations=affected_locations,
                )
                order.append(key)
                continue

            existing.alert = choose_preferred_alert(existing.alert, weather_alert)
            _merge_affected_locations(existing.affected_locations, affected_locations)

    return [aggregated_by_key[key] for key in order]


def match_saved_alert_to_location(
    normalized_alert: MolecastAlert,
    location: Location,
    source: str,
) -> AlertMatch | None:
    geometry = normalized_alert.geometry
    if geometry and point_matches_geometry(location.longitude, location.latitude, geometry):
        return AlertMatch(
            match_type="geometry",
            matched_value=f"{location.latitude},{location.longitude}",
            confidence="high",
        )

    location_zone_ids = _location_zone_ids(location)
    alert_zone_ids = {zone_id for zone_id in _alert_zone_ids(normalized_alert) if zone_id}
    zone_match = sorted(location_zone_ids & alert_zone_ids)
    if zone_match:
        return AlertMatch(match_type="zone", matched_value=zone_match[0], confidence="high")

    geocode_match = _match_geocode(normalized_alert.geocode, location, location_zone_ids)
    if geocode_match is not None:
        return geocode_match

    county_fips_match = _match_county_fips(normalized_alert.raw_properties, location)
    if county_fips_match is not None:
        return county_fips_match

    if source == "test":
        zip_match = _match_test_zip_parameter(normalized_alert.parameters, location)
        if zip_match is not None:
            return zip_match

    return None


def _weather_alert_from_normalized(
    normalized_alert: MolecastAlert,
    match: AlertMatch,
    *,
    zone_geometry_service: NwsZoneGeometryService | None,
) -> WeatherAlert | None:
    geometry = normalized_alert.geometry
    geometry_source = "alert" if geometry is not None else None
    if geometry is None and normalized_alert.affectedZones and zone_geometry_service is not None:
        try:
            geometry = zone_geometry_service.resolve_affected_zones(normalized_alert.affectedZones)
        except Exception:
            get_logger().warning(
                "Unable to resolve saved-summary affected-zone geometry; keeping alert without map geometry. "
                "source=%s id=%s affected_zones=%s",
                normalized_alert.source,
                normalized_alert.id,
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
        return WeatherAlert.model_validate(alert_data)
    except ValidationError:
        get_logger().debug(
            "Filtered saved-summary alert failing schema validation: source=%s id=%s",
            normalized_alert.source,
            normalized_alert.id,
            exc_info=True,
        )
        return None


def _normalize_features(features: list[dict[str, Any]], source: str) -> list[MolecastAlert]:
    if not features:
        return []
    try:
        return normalize_nws_feature_collection(
            {"type": "FeatureCollection", "features": features},
            source=source,
        )
    except ValueError:
        get_logger().warning("Skipping malformed saved-summary alert payload: source=%s", source, exc_info=True)
        return []


def _should_skip_alert_time(normalized_alert: MolecastAlert) -> bool:
    properties = normalized_alert.raw_properties
    current_time = now_utc()
    if has_invalid_alert_time(properties.get("effective")) or has_invalid_alert_time(properties.get("expires")):
        return True

    expires_at = parse_alert_time_utc(properties.get("expires"))
    if expires_at is not None and current_time > expires_at:
        return True

    effective_at = parse_alert_time_utc(properties.get("effective"))
    return effective_at is not None and current_time < effective_at


def _unique_zone_ids(locations: list[Location]) -> list[str]:
    zone_ids: list[str] = []
    for location in locations:
        for zone_id in _location_zone_id_list(location):
            if zone_id not in zone_ids:
                zone_ids.append(zone_id)
    return zone_ids


def _location_zone_ids(location: Location) -> set[str]:
    return set(_location_zone_id_list(location))


def _location_zone_id_list(location: Location) -> list[str]:
    zone_ids: list[str] = []
    for zone_id in (
        extract_zone_id(location.county_zone),
        extract_zone_id(location.forecast_zone),
        extract_zone_id(location.fire_weather_zone),
    ):
        if zone_id and zone_id not in zone_ids:
            zone_ids.append(zone_id)
    return zone_ids


def _alert_zone_ids(normalized_alert: MolecastAlert) -> set[str]:
    return {
        zone_id
        for zone_id in (extract_zone_id(value) for value in (normalized_alert.affectedZones or []))
        if zone_id
    }


def _match_geocode(
    geocode: dict[str, Any] | None,
    location: Location,
    location_zone_ids: set[str],
) -> AlertMatch | None:
    if not isinstance(geocode, dict):
        return None

    for same in geocode.get("same") or []:
        if not isinstance(same, dict) or not same.get("valid"):
            continue
        same_county_fips = f"{same.get('state_fips') or ''}{same.get('county_fips') or ''}"
        if location.county_fips and same_county_fips == location.county_fips:
            return AlertMatch(
                match_type="same",
                matched_value=same.get("original") or same_county_fips,
                confidence="high",
            )

    for ugc in geocode.get("ugc") or []:
        if not isinstance(ugc, dict) or not ugc.get("valid"):
            continue
        original = str(ugc.get("original") or "").strip().upper()
        if original and original in location_zone_ids:
            return AlertMatch(match_type="ugc", matched_value=original, confidence="high")

    raw = geocode.get("raw") if isinstance(geocode.get("raw"), dict) else {}
    if raw:
        raw_same = _as_strings(raw.get("SAME"))
        if location.county_fips and any(value[1:] == location.county_fips for value in raw_same if len(value) == 6):
            return AlertMatch(match_type="same", matched_value=location.county_fips, confidence="high")

        raw_ugc = {value.strip().upper() for value in _as_strings(raw.get("UGC"))}
        matched_ugc = sorted(raw_ugc & location_zone_ids)
        if matched_ugc:
            return AlertMatch(match_type="ugc", matched_value=matched_ugc[0], confidence="high")

    return None


def _match_county_fips(properties: dict[str, Any], location: Location) -> AlertMatch | None:
    if not location.county_fips:
        return None
    for key in ("county_fips", "countyFips", "countyFIPS"):
        for value in _as_strings(properties.get(key)):
            if value == location.county_fips:
                return AlertMatch(match_type="county_fips", matched_value=value, confidence="high")
    return None


def _match_test_zip_parameter(
    parameters: dict[str, list[str]],
    location: Location,
) -> AlertMatch | None:
    if not location.zip_code:
        return None
    target_keys = {"zipcode", "zip_code", "zip", "postalcode", "postal_code"}
    location_zip = location.zip_code[:5]
    for key, values in parameters.items():
        if key.strip().lower() not in target_keys:
            continue
        for value in values:
            if str(value).strip()[:5] == location_zip:
                return AlertMatch(match_type="zip_code", matched_value=location_zip, confidence="high")
    return None


def _stable_source_alert_key(normalized_alert: MolecastAlert) -> str:
    for value in (
        normalized_alert.canonical_id,
        normalized_alert.nws_id,
        normalized_alert.cap_identifier,
        normalized_alert.id,
    ):
        if value:
            return f"{normalized_alert.source}:{value}"
    return f"{normalized_alert.source}:{normalized_alert.content_hash}"


def _affected_location_ref(location: Location, match: AlertMatch) -> dict[str, Any]:
    return {
        "id": location.id,
        "label": location.label,
        "name": location.name,
        "zip_code": location.zip_code,
        "city": location.city,
        "state": location.state,
        "county": location.county,
        "match_type": match.match_type,
    }


def _alert_ref(aggregated_alert: _AggregatedAlert) -> dict[str, Any]:
    alert = aggregated_alert.alert
    return {
        "id": alert.id,
        "source": alert.source,
        "event": alert.event,
        "priority": alert.priority,
        "priority_score": alert.priority_score,
        "color_hex": alert.color_hex,
        "affected_location_count": len(aggregated_alert.affected_locations),
        "affected_locations": aggregated_alert.affected_locations,
    }


def _merge_affected_locations(
    existing: list[dict[str, Any]],
    additions: list[dict[str, Any]],
) -> None:
    seen_ids = {item["id"] for item in existing}
    for addition in additions:
        if addition["id"] in seen_ids:
            continue
        existing.append(addition)
        seen_ids.add(addition["id"])


def _extend_unique_features(
    features: list[dict[str, Any]],
    seen_feature_ids: set[str],
    payload: dict[str, Any],
) -> None:
    raw_features = payload.get("features", [])
    if not isinstance(raw_features, list):
        return
    for feature in raw_features:
        if not isinstance(feature, dict):
            continue
        stable_id = stable_alert_feature_id(feature)
        if stable_id in seen_feature_ids:
            continue
        seen_feature_ids.add(stable_id)
        features.append(feature)


def _dedupe_locations(locations: list[Location]) -> list[Location]:
    deduped: list[Location] = []
    seen_ids: set[int] = set()
    for location in locations:
        if location.id in seen_ids:
            continue
        deduped.append(location)
        seen_ids.add(location.id)
    return deduped


def _saved_location_fingerprint(locations: list[Location], test_alert_mtime: float | None) -> str:
    data = {
        "locations": [
            {
                "id": location.id,
                "updated_at": _datetime_fingerprint(location.updated_at),
                "zip_code": location.zip_code,
                "county_fips": location.county_fips,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "county_zone": location.county_zone,
                "forecast_zone": location.forecast_zone,
                "fire_weather_zone": location.fire_weather_zone,
            }
            for location in sorted(locations, key=lambda item: item.id)
        ],
        "test_alert_mtime": test_alert_mtime,
    }
    encoded = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _datetime_fingerprint(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _as_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return [str(item).strip() for item in value if item is not None and str(item).strip()]
    if str(value).strip():
        return [str(value).strip()]
    return []
