from datetime import UTC, datetime

from app.api.routes import alerts as alerts_route
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
            "effective": "2026-01-01T00:00:00Z",
            "expires": "2099-01-01T00:00:00Z",
            "geocode": {
                "SAME": ["026077"],
                "UGC": ["MIC077", "MIZ072"],
            },
        },
        "geometry": None,
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
    assert alert["raw_properties"]["priority"] == 1000
    assert alert["raw_properties"]["color_hex"] == "#FF0000"
    assert alert["raw_properties"]["icon"] == "tornado"
    assert alert["raw_properties"]["sound_profile"] == "tornado"
    assert alert["raw_properties"]["normalized_geocode"]["same"][0]["original"] == "026077"
    assert [ugc["original"] for ugc in alert["raw_properties"]["normalized_geocode"]["ugc"]] == [
        "MIC077",
        "MIZ072",
    ]
