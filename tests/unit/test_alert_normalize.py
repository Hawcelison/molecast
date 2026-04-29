from datetime import UTC, datetime

from app.alerts.catalog import DEFAULT_COLOR_HEX
from app.alerts.normalize import normalize_nws_feature, normalize_nws_feature_collection


def _feature(**property_overrides):
    properties = {
        "id": "urn:oid:2.49.0.1.840.0.test",
        "sent": "2099-04-27T16:00:00Z",
        "effective": "2099-04-27T16:05:00Z",
        "onset": "2099-04-27T16:10:00Z",
        "expires": "2099-04-27T17:00:00Z",
        "ends": None,
        "status": "Actual",
        "messageType": "Alert",
        "category": ["Met"],
        "response": ["Shelter"],
        "event": "Tornado Warning",
        "severity": "Extreme",
        "urgency": "Immediate",
        "certainty": "Observed",
        "headline": "Tornado Warning issued",
        "description": "A tornado warning has been issued.",
        "instruction": "Take shelter now.",
        "sender": "w-nws.webmaster@noaa.gov",
        "senderName": "NWS Kalamazoo",
        "web": "https://alerts.weather.gov",
        "contact": "NWS",
        "areaDesc": "Kalamazoo",
        "affectedZones": ["https://api.weather.gov/zones/county/MIC077"],
        "geocode": {
            "SAME": ["026077"],
            "UGC": ["MIC077", "MIZ072"],
        },
        "parameters": {
            "NWSheadline": ["Radar indicated tornado warning"],
            "tornadoDetection": ["OBSERVED"],
            "tornadoDamageThreat": ["CONSIDERABLE"],
            "windGust": "70 MPH",
            "hailSize": ["1.75 IN"],
            "unknownParameter": ["kept"],
        },
    }
    properties.update(property_overrides)
    return {
        "type": "Feature",
        "id": "https://api.weather.gov/alerts/test-alert",
        "properties": properties,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        },
    }


def test_normalize_nws_alert_preserves_text_fields() -> None:
    alert = normalize_nws_feature(_feature())

    assert alert.id == "https://api.weather.gov/alerts/test-alert"
    assert alert.nws_id == "urn:oid:2.49.0.1.840.0.test"
    assert alert.canonical_id == "nws:urn:oid:2.49.0.1.840.0.test"
    assert alert.headline == "Tornado Warning issued"
    assert alert.description == "A tornado warning has been issued."
    assert alert.instruction == "Take shelter now."
    assert alert.effective == datetime(2099, 4, 27, 16, 5, tzinfo=UTC)
    assert alert.raw_properties["headline"] == "Tornado Warning issued"
    assert alert.raw_feature["type"] == "Feature"
    assert len(alert.content_hash) == 64


def test_normalize_nws_alert_preserves_geocode_same_and_ugc() -> None:
    alert = normalize_nws_feature(_feature())

    assert alert.geocode["same"][0]["original"] == "026077"
    assert alert.geocode["same"][0]["state_fips"] == "26"
    assert alert.geocode["same"][0]["county_fips"] == "077"
    assert [ugc["original"] for ugc in alert.geocode["ugc"]] == ["MIC077", "MIZ072"]
    assert [ugc["kind"] for ugc in alert.geocode["ugc"]] == ["county", "zone"]
    assert alert.geocode["raw"]["SAME"] == ["026077"]


def test_normalize_nws_alert_preserves_parameters_and_unknown_parameters() -> None:
    alert = normalize_nws_feature(_feature())

    assert alert.parameters["NWSheadline"] == ["Radar indicated tornado warning"]
    assert alert.parameters["windGust"] == ["70 MPH"]
    assert alert.parameters["unknownParameter"] == ["kept"]


def test_normalize_nws_alert_normalizes_known_tornado_parameters() -> None:
    alert = normalize_nws_feature(_feature())

    assert alert.NWSheadline == ["Radar indicated tornado warning"]
    assert alert.tornadoDetection == ["OBSERVED"]
    assert alert.tornadoDamageThreat == ["CONSIDERABLE"]
    assert alert.windGust == ["70 MPH"]
    assert alert.hailSize == ["1.75 IN"]


def test_normalize_nws_alert_preserves_affected_zones() -> None:
    alert = normalize_nws_feature(_feature())

    assert alert.affectedZones == ["https://api.weather.gov/zones/county/MIC077"]


def test_normalize_nws_alert_allows_missing_geometry() -> None:
    feature = _feature()
    feature["geometry"] = None

    alert = normalize_nws_feature(feature)

    assert alert.geometry is None


def test_normalize_nws_alert_unknown_event_falls_back_safely() -> None:
    alert = normalize_nws_feature(
        _feature(
            event="Unknown Local Event",
            severity="Unknown",
            parameters={},
        )
    )

    assert alert.priority == 100
    assert alert.color_hex == DEFAULT_COLOR_HEX
    assert alert.color_name is None
    assert alert.icon == "alert-circle"
    assert alert.sound_profile == "default"


def test_normalize_nws_feature_collection_uses_fixtures() -> None:
    alerts = normalize_nws_feature_collection({"features": [_feature()]})

    assert len(alerts) == 1
    assert alerts[0].event == "Tornado Warning"

