from types import SimpleNamespace

from app.models.location import Location
from app.services.alert_service import (
    ActiveAlertService,
    AlertFetchError,
    AlertZoneFetchError,
    NwsAlertProvider,
    extract_points_metadata,
    extract_zone_id,
)


def _location() -> Location:
    return Location(
        id=1,
        label="Portage, MI",
        city="Portage",
        state="MI",
        county="Kalamazoo",
        zip_code="49002",
        latitude=42.2012,
        longitude=-85.58,
        is_primary=True,
    )


def _feature(alert_id: str, event: str = "Tornado Warning") -> dict:
    return {
        "type": "Feature",
        "id": alert_id,
        "properties": {
            "id": alert_id,
            "event": event,
            "severity": "Extreme",
            "urgency": "Immediate",
            "certainty": "Observed",
            "headline": f"{event} headline",
            "description": f"{event} description",
            "areaDesc": "Kalamazoo",
            "effective": "2026-01-01T00:00:00Z",
            "expires": "2099-01-01T00:00:00Z",
        },
        "geometry": None,
    }


def _payload(*features: dict) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}


def _points_payload() -> dict:
    return {
        "properties": {
            "forecastOffice": "https://api.weather.gov/offices/GRR",
            "gridId": "GRR",
            "gridX": 55,
            "gridY": 44,
            "forecast": "https://api.weather.gov/gridpoints/GRR/55,44/forecast",
            "forecastHourly": "https://api.weather.gov/gridpoints/GRR/55,44/forecast/hourly",
            "forecastGridData": "https://api.weather.gov/gridpoints/GRR/55,44",
            "observationStations": "https://api.weather.gov/gridpoints/GRR/55,44/stations",
            "county": "https://api.weather.gov/zones/county/MIC077",
            "forecastZone": "https://api.weather.gov/zones/forecast/MIZ072",
            "fireWeatherZone": "https://api.weather.gov/zones/fire/MIZ072",
            "timeZone": "America/Detroit",
            "radarStation": "KGRR",
        }
    }


class FakeNwsAlertProvider(NwsAlertProvider):
    def __init__(
        self,
        *,
        point_payload: dict | None = None,
        points_payload: dict | None = None,
        zone_payloads: dict[str, dict] | None = None,
        point_error: bool = False,
        points_error: bool = False,
        zone_errors: set[str] | None = None,
    ) -> None:
        super().__init__(
            SimpleNamespace(
                nws_active_alerts_url="https://api.weather.gov/alerts/active",
                nws_user_agent="Molecast test",
            )
        )
        self.point_payload = point_payload if point_payload is not None else _payload()
        self.points_payload = points_payload if points_payload is not None else _points_payload()
        self.zone_payloads = zone_payloads or {}
        self.point_error = point_error
        self.points_error = points_error
        self.zone_errors = zone_errors or set()
        self.point_calls = 0
        self.points_calls = 0
        self.zone_calls: list[str] = []

    def _fetch_point_alerts(self, location: Location) -> dict:
        self.point_calls += 1
        if self.point_error:
            raise AlertFetchError("point failed")
        return self.point_payload

    def _fetch_points_payload(self, location: Location) -> dict:
        self.points_calls += 1
        if self.points_error:
            raise AlertFetchError("points failed")
        return self.points_payload

    def _fetch_zone_alerts(self, zone_id: str) -> dict:
        self.zone_calls.append(zone_id)
        if zone_id in self.zone_errors:
            raise AlertZoneFetchError("zone failed")
        return self.zone_payloads.get(zone_id, _payload())


class FakeTestAlertLoader:
    def __init__(self, features: list[dict] | None = None) -> None:
        self.features = features or []

    def alert_file_mtime(self) -> float:
        return 1.0

    def load_enabled_alert_features(self, location: Location) -> list[dict]:
        return self.features


def test_point_only_fetch_still_works_when_points_lookup_fails() -> None:
    provider = FakeNwsAlertProvider(
        point_payload=_payload(_feature("point-alert")),
        points_error=True,
    )

    payload = provider.fetch_active_alerts(_location())

    assert [feature["properties"]["id"] for feature in payload["features"]] == ["point-alert"]
    assert provider.point_calls == 1
    assert provider.points_calls == 1
    assert provider.zone_calls == []


def test_zone_ids_extracted_from_points_response_urls() -> None:
    metadata = extract_points_metadata(_points_payload())

    assert extract_zone_id(metadata["county"]) == "MIC077"
    assert extract_zone_id(metadata["forecastZone"]) == "MIZ072"
    assert extract_zone_id(metadata["fireWeatherZone"]) == "MIZ072"


def test_duplicate_alert_removed_across_point_and_zone_feeds() -> None:
    provider = FakeNwsAlertProvider(
        point_payload=_payload(_feature("duplicate-alert"), _feature("point-only")),
        zone_payloads={
            "MIC077": _payload(_feature("duplicate-alert"), _feature("county-only")),
            "MIZ072": _payload(_feature("forecast-only")),
        },
    )

    payload = provider.fetch_active_alerts(_location())

    assert [feature["properties"]["id"] for feature in payload["features"]] == [
        "duplicate-alert",
        "point-only",
        "county-only",
        "forecast-only",
    ]


def test_nws_failure_still_returns_test_alerts() -> None:
    service = ActiveAlertService(
        provider=FakeNwsAlertProvider(point_error=True, points_error=True),
        test_alert_loader=FakeTestAlertLoader([_feature("test-alert")]),
        refresh_interval_seconds=60,
    )

    alerts, _refreshed_at = service.refresh_active_alerts(_location())

    assert [alert.id for alert in alerts] == ["test-alert"]
    assert alerts[0].source == "test"


def test_zone_failure_does_not_break_point_alert_fetch() -> None:
    provider = FakeNwsAlertProvider(
        point_payload=_payload(_feature("point-alert")),
        zone_payloads={"MIZ072": _payload(_feature("forecast-zone-alert"))},
        zone_errors={"MIC077"},
    )

    payload = provider.fetch_active_alerts(_location())

    assert [feature["properties"]["id"] for feature in payload["features"]] == [
        "point-alert",
        "forecast-zone-alert",
    ]
    assert provider.zone_calls == ["MIC077", "MIZ072"]

