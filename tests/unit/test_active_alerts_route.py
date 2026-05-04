from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api.routes import alerts as alerts_route
from app.alerts.presentation import build_alert_presentation
from app.models.location import Location
from app.schemas.alert import ActiveAlertsResponse, AlertSummaryResponse, WeatherAlert
from app.services.alert_service import parse_nws_alerts


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


def _normalized_feature() -> dict:
    return {
        "type": "Feature",
        "id": "normalized-route-alert",
        "properties": {
            "id": "normalized-route-alert",
            "event": "Tornado Warning",
            "severity": "Extreme",
            "urgency": "Immediate",
            "certainty": "Observed",
            "headline": "Tornado Warning headline",
            "description": "Tornado Warning description",
            "areaDesc": "Kalamazoo",
            "affectedZones": ["https://api.weather.gov/zones/county/MIC077"],
            "effective": "2026-01-01T00:00:00Z",
            "expires": "2099-01-01T00:00:00Z",
            "geocode": {
                "SAME": ["026077"],
                "UGC": ["MIC077", "MIZ072"],
            },
            "parameters": {
                "tornadoDetection": ["OBSERVED"],
                "tornadoDamageThreat": ["CONSIDERABLE"],
                "eventMotionDescription": ["MOVING EAST AT 35 MPH"],
                "VTEC": ["/O.NEW.KGRR.TO.W.0049.260101T0000Z-260101T0100Z/"],
            },
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-85.7, 42.1],
                    [-85.4, 42.1],
                    [-85.4, 42.3],
                    [-85.7, 42.3],
                    [-85.7, 42.1],
                ]
            ],
        },
    }


class FakeActiveAlertService:
    def get_active_alerts(self, location: Location):
        alerts = parse_nws_alerts(
            {"type": "FeatureCollection", "features": [_normalized_feature()]},
            location,
            source="nws",
        )
        return alerts, datetime(2026, 4, 29, 12, 0, tzinfo=UTC)


def _weather_alert(**overrides) -> WeatherAlert:
    data = {
        "id": "summary-alert",
        "source": "nws",
        "event": "Tornado Warning",
        "severity": "Extreme",
        "urgency": "Immediate",
        "certainty": "Observed",
        "headline": "Tornado Warning headline",
        "description": "Tornado Warning description",
        "areaDesc": "Kalamazoo",
        "effective": datetime(2099, 1, 1, tzinfo=UTC),
        "expires": datetime(2099, 1, 1, 1, tzinfo=UTC),
        "geometry": None,
        "raw_properties": {},
        "match": {
            "match_type": "county",
            "matched_value": "Kalamazoo",
            "confidence": "medium",
        },
        "color_hex": "#FF0000",
        "icon": "alert-circle",
        "sound_profile": "default",
        "priority": 1000,
        "priority_score": 1000,
        "severity_rank": 4,
        "urgency_rank": 4,
        "certainty_rank": 4,
    }
    data.update(overrides)
    return WeatherAlert.model_validate(data)


class FakeSummaryActiveAlertService:
    def __init__(self, alerts):
        self.alerts = alerts
        self.calls = []

    def get_active_alerts(self, location: Location):
        self.calls.append(location.id)
        return self.alerts, datetime(2026, 5, 4, 12, 0, tzinfo=UTC)


def test_normalized_alerts_flow_through_active_alerts_endpoint(monkeypatch) -> None:
    location = _location()
    monkeypatch.setattr(alerts_route.location_service, "get_active_location", lambda db, settings: location)
    monkeypatch.setattr(alerts_route, "active_alert_service", FakeActiveAlertService())

    response = ActiveAlertsResponse.model_validate(alerts_route.get_active_alerts(db=None))

    payload = response.model_dump(mode="json")
    assert payload["location_id"] == location.id
    assert [alert["id"] for alert in payload["alerts"]] == ["normalized-route-alert"]

    alert = payload["alerts"][0]
    assert alert["priority"] == 1000
    assert alert["priority_score"] == 1000
    assert alert["color_hex"] == "#FF0000"
    assert alert["icon"] == "tornado"
    assert alert["sound_profile"] == "tornado"
    assert alert["areaDesc"] == "Kalamazoo"
    assert alert["affectedZones"] == ["https://api.weather.gov/zones/county/MIC077"]
    assert alert["geometry"]["type"] == "Polygon"
    assert alert["geometry_source"] == "alert"
    assert alert["geometry_bounds"] == {
        "west": -85.7,
        "south": 42.1,
        "east": -85.4,
        "north": 42.3,
    }
    assert alert["nws_details"]["tornadoDetection"] == "OBSERVED"
    assert alert["nws_details"]["tornadoDamageThreat"] == "CONSIDERABLE"
    assert alert["nws_details"]["eventMotionDescription"] == "MOVING EAST AT 35 MPH"
    assert alert["nws_details"]["VTEC"] == "/O.NEW.KGRR.TO.W.0049.260101T0000Z-260101T0100Z/"
    assert alert["raw_properties"]["priority"] == 1000
    assert alert["raw_properties"]["color_hex"] == "#FF0000"
    assert alert["raw_properties"]["icon"] == "tornado"
    assert alert["raw_properties"]["sound_profile"] == "tornado"
    assert alert["raw_properties"]["normalized_geocode"]["same"][0]["original"] == "026077"
    assert [ugc["original"] for ugc in alert["raw_properties"]["normalized_geocode"]["ugc"]] == [
        "MIC077",
        "MIZ072",
    ]


def test_test_alert_details_use_same_dto_shape() -> None:
    feature = _normalized_feature()
    feature["id"] = "test-detail-alert"
    feature["properties"]["id"] = "test-detail-alert"
    feature["properties"]["event"] = "Severe Thunderstorm Warning"
    feature["properties"]["parameters"] = {
        "thunderstormDamageThreat": ["CONSIDERABLE"],
        "maxWindGust": ["070 MPH"],
        "maxHailSize": ["1.75 IN"],
        "WEAHandling": ["IMMEDIATE"],
    }

    alerts = parse_nws_alerts(
        {"type": "FeatureCollection", "features": [feature]},
        _location(),
        source="test",
    )
    payload = alerts[0].model_dump(mode="json")
    presentation = build_alert_presentation(alerts[0], _location()).model_dump(mode="json")

    assert payload["source"] == "test"
    assert payload["geometry"]["type"] == "Polygon"
    assert payload["geometry_source"] == "alert"
    assert payload["affectedZones"] == ["https://api.weather.gov/zones/county/MIC077"]
    assert presentation["geometry_bounds"] == {
        "west": -85.7,
        "south": 42.1,
        "east": -85.4,
        "north": 42.3,
    }
    assert payload["nws_details"]["thunderstormDamageThreat"] == "CONSIDERABLE"
    assert payload["nws_details"]["maxWindGust"] == "070 MPH"
    assert payload["nws_details"]["maxHailSize"] == "1.75 IN"
    assert payload["nws_details"]["WEAHandling"] == "IMMEDIATE"


def test_active_alert_summary_uses_same_active_alert_stream(monkeypatch) -> None:
    location = _location()
    stream = [
        _weather_alert(id="warning", source="nws", event="Tornado Warning"),
        _weather_alert(id="watch", source="test", event="TEST: Tornado Watch", priority_score=500, priority=500),
        _weather_alert(id="advisory", source="nws", event="Winter Weather Advisory", priority_score=250, priority=250),
        _weather_alert(id="other", source="nws", event="Special Weather Statement", priority_score=100, priority=100),
    ]
    fake_service = FakeSummaryActiveAlertService(stream)
    monkeypatch.setattr(alerts_route.location_service, "get_active_location", lambda db, settings: location)
    monkeypatch.setattr(alerts_route, "active_alert_service", fake_service)

    active_response = ActiveAlertsResponse.model_validate(alerts_route.get_active_alerts(db=None))
    summary_response = AlertSummaryResponse.model_validate(alerts_route.get_alert_summary(db=None))

    assert [alert.id for alert in active_response.alerts] == [alert.id for alert in stream]
    assert fake_service.calls == [location.id, location.id]
    assert summary_response.scope == "active"
    assert summary_response.scope_label == "Active Location"
    assert summary_response.total == len(active_response.alerts)
    assert summary_response.warning_count == 1
    assert summary_response.watch_count == 1
    assert summary_response.advisory_count == 1
    assert summary_response.other_count == 1
    assert summary_response.saved_location_count is None
    assert summary_response.affected_location_count == 1
    assert summary_response.partial is False
    assert summary_response.errors == []


def test_active_alert_summary_preserves_test_source_identity(monkeypatch) -> None:
    location = _location()
    fake_service = FakeSummaryActiveAlertService(
        [
            _weather_alert(id="nws-watch", source="nws", event="Tornado Watch", priority_score=500, priority=500),
            _weather_alert(
                id="test-warning",
                source="test",
                event="TEST: Tornado Warning",
                priority_score=1000,
                priority=1000,
            ),
        ]
    )
    monkeypatch.setattr(alerts_route.location_service, "get_active_location", lambda db, settings: location)
    monkeypatch.setattr(alerts_route, "active_alert_service", fake_service)

    response = AlertSummaryResponse.model_validate(alerts_route.get_alert_summary(db=None))

    assert response.highest_alert is not None
    assert response.highest_alert.id == "test-warning"
    assert response.highest_alert.source == "test"
    assert response.highest_alert.event == "TEST: Tornado Warning"


def test_empty_active_alert_summary_has_zero_counts(monkeypatch) -> None:
    location = _location()
    monkeypatch.setattr(alerts_route.location_service, "get_active_location", lambda db, settings: location)
    monkeypatch.setattr(alerts_route, "active_alert_service", FakeSummaryActiveAlertService([]))

    response = AlertSummaryResponse.model_validate(alerts_route.get_alert_summary(db=None))

    assert response.total == 0
    assert response.warning_count == 0
    assert response.watch_count == 0
    assert response.advisory_count == 0
    assert response.other_count == 0
    assert response.highest_alert is None


def test_saved_alert_summary_scope_is_not_implemented() -> None:
    with pytest.raises(HTTPException) as exc_info:
        alerts_route.get_alert_summary(scope="saved", db=None)

    assert exc_info.value.status_code == 501
    assert "Only active alert summary scope is implemented" in exc_info.value.detail
