from datetime import UTC, datetime

from app.api.routes import alerts as alerts_route
from app.alerts.presentation import build_alert_presentation
from app.models.location import Location
from app.schemas.alert import ActiveAlertsResponse
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
