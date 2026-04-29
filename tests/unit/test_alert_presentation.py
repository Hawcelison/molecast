from datetime import UTC, datetime
from types import SimpleNamespace

from app.alerts.presentation import (
    build_alert_presentation,
    build_alert_presentations,
    build_expires_in,
)
from app.schemas.alert import WeatherAlert


def _location() -> SimpleNamespace:
    return SimpleNamespace(county="Kalamazoo", state="MI")


def _alert(**overrides) -> WeatherAlert:
    data = {
        "id": "test-alert",
        "source": "nws",
        "event": "Tornado Warning",
        "severity": "Extreme",
        "urgency": "Immediate",
        "certainty": "Observed",
        "headline": "Radar indicated tornado warning",
        "description": "This is a particularly dangerous situation.",
        "areaDesc": "Kalamazoo",
        "effective": datetime(2099, 4, 27, 16, 0, tzinfo=UTC),
        "expires": datetime(2099, 4, 27, 18, 30, tzinfo=UTC),
        "geometry": None,
        "raw_properties": {
            "id": "test-alert",
            "event": "Tornado Warning",
            "instruction": "Take shelter now.",
            "parameters": {"NWSheadline": ["Radar indicated tornado warning"]},
        },
        "match": {
            "match_type": "county",
            "matched_value": "Kalamazoo",
            "confidence": "medium",
        },
        "color_hex": "#FF0000",
        "icon": "tornado",
        "sound_profile": "tornado",
        "priority": 1000,
        "priority_score": 100,
        "severity_rank": 4,
        "urgency_rank": 4,
        "certainty_rank": 4,
        "nws_details": {
            "tornadoDetection": "OBSERVED",
            "tornadoDamageThreat": "CONSIDERABLE",
        },
    }
    data.update(overrides)
    return WeatherAlert.model_validate(data)


def test_build_alert_presentation_preserves_original_fields() -> None:
    alert = _alert()

    presentation = build_alert_presentation(
        alert,
        _location(),
        now=datetime(2099, 4, 27, 17, 0, tzinfo=UTC),
    )

    assert presentation.id == alert.id
    assert presentation.source == alert.source
    assert presentation.event == alert.event
    assert presentation.effective == alert.effective
    assert presentation.expires == alert.expires
    assert presentation.geometry == alert.geometry
    assert presentation.raw_properties == alert.raw_properties
    assert presentation.match == alert.match
    assert presentation.nws_details == alert.nws_details


def test_build_alert_presentation_adds_ui_ready_fields() -> None:
    presentation = build_alert_presentation(
        _alert(),
        _location(),
        now=datetime(2099, 4, 27, 17, 0, tzinfo=UTC),
    )

    assert presentation.title == "TORNADO WARNING"
    assert presentation.subtitle == "Kalamazoo, MI"
    assert presentation.expires_in == "1 hour 30 minutes"
    assert presentation.severity_color == "severity-extreme"
    assert presentation.tags == ["OBSERVED", "RADAR", "PDS"]
    assert presentation.nws_details.tornadoDetection == "OBSERVED"


def test_build_alert_presentation_adds_polygon_bounds() -> None:
    presentation = build_alert_presentation(
        _alert(
            geometry={
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
        ),
        _location(),
        now=datetime(2099, 4, 27, 17, 0, tzinfo=UTC),
    )

    assert presentation.geometry_bounds is not None
    assert presentation.geometry_bounds.model_dump() == {
        "west": -85.7,
        "south": 42.1,
        "east": -85.4,
        "north": 42.3,
    }


def test_build_alert_presentation_adds_multipolygon_bounds() -> None:
    presentation = build_alert_presentation(
        _alert(
            geometry={
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [-85.7, 42.1],
                            [-85.6, 42.1],
                            [-85.6, 42.2],
                            [-85.7, 42.1],
                        ]
                    ],
                    [
                        [
                            [-85.3, 42.4],
                            [-85.1, 42.4],
                            [-85.1, 42.6],
                            [-85.3, 42.4],
                        ]
                    ],
                ],
            },
        ),
        _location(),
        now=datetime(2099, 4, 27, 17, 0, tzinfo=UTC),
    )

    assert presentation.geometry_bounds is not None
    assert presentation.geometry_bounds.model_dump() == {
        "west": -85.7,
        "south": 42.1,
        "east": -85.1,
        "north": 42.6,
    }


def test_build_alert_presentation_uses_null_bounds_for_missing_geometry() -> None:
    presentation = build_alert_presentation(
        _alert(geometry=None),
        _location(),
        now=datetime(2099, 4, 27, 17, 0, tzinfo=UTC),
    )

    assert presentation.geometry_bounds is None


def test_build_alert_presentation_uses_null_bounds_for_malformed_geometry() -> None:
    presentation = build_alert_presentation(
        _alert(geometry={"type": "Polygon", "coordinates": [[["bad", 42.1]]]}),
        _location(),
        now=datetime(2099, 4, 27, 17, 0, tzinfo=UTC),
    )

    assert presentation.geometry_bounds is None


def test_build_alert_presentation_detects_tags_from_raw_properties() -> None:
    presentation = build_alert_presentation(
        _alert(
            certainty="Likely",
            headline="Tornado warning",
            description="Move to shelter.",
            raw_properties={
                "instruction": "This is a particularly dangerous situation.",
                "parameters": {
                    "detection": ["Radar indicated rotation"],
                    "nested": {"source": "NWS"},
                },
            },
        ),
        _location(),
        now=datetime(2099, 4, 27, 17, 0, tzinfo=UTC),
    )

    assert presentation.tags == ["RADAR", "PDS"]


def test_build_alert_presentation_uses_unknown_severity_placeholder() -> None:
    presentation = build_alert_presentation(
        _alert(severity=None),
        _location(),
        now=datetime(2099, 4, 27, 17, 0, tzinfo=UTC),
    )

    assert presentation.severity_color == "severity-unknown"


def test_build_alert_presentation_normalizes_severity_color_mapping() -> None:
    presentation = build_alert_presentation(
        _alert(severity=" severe "),
        _location(),
        now=datetime(2099, 4, 27, 17, 0, tzinfo=UTC),
    )

    assert presentation.severity_color == "severity-severe"


def test_build_alert_presentations_filters_expired_alerts() -> None:
    current_time = datetime(2099, 4, 27, 17, 0, tzinfo=UTC)
    expired_alert = _alert(id="expired-alert", expires=current_time)
    active_alert = _alert(id="active-alert", expires=datetime(2099, 4, 27, 17, 1, tzinfo=UTC))

    presentations = build_alert_presentations(
        [expired_alert, active_alert],
        _location(),
        now=current_time,
    )

    assert [presentation.id for presentation in presentations] == ["active-alert"]


def test_build_expires_in_uses_utc_duration_without_display_time_formatting() -> None:
    now = datetime(2099, 4, 27, 17, 0, tzinfo=UTC)

    assert build_expires_in(datetime(2099, 4, 27, 17, 1, tzinfo=UTC), now) == "1 minute"
    assert build_expires_in(datetime(2099, 4, 27, 19, 0, tzinfo=UTC), now) == "2 hours"
    assert build_expires_in(datetime(2099, 4, 29, 18, 0, tzinfo=UTC), now) == "2 days 1 hour"
    assert build_expires_in(datetime(2099, 4, 27, 16, 59, tzinfo=UTC), now) == "Expired"
    assert build_expires_in(None, now) == "Unknown"
