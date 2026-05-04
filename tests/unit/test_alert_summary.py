from datetime import UTC, datetime
from types import SimpleNamespace

from app.alerts.summary import build_alert_summary, choose_highest_alert, classify_alert
from app.schemas.alert import WeatherAlert


def _alert(**overrides) -> WeatherAlert:
    data = {
        "id": "alert-1",
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


def test_classify_alert_uses_event_text() -> None:
    assert classify_alert(_alert(event="Tornado Warning")) == "warning"
    assert classify_alert(_alert(event="Tornado Watch")) == "watch"
    assert classify_alert(_alert(event="Winter Weather Advisory")) == "advisory"
    assert classify_alert(_alert(event="Special Weather Statement")) == "other"


def test_build_alert_summary_counts_warning_watch_advisory_and_other() -> None:
    alerts = [
        _alert(id="warning", event="Tornado Warning"),
        _alert(id="watch", event="Tornado Watch"),
        _alert(id="advisory", event="Winter Weather Advisory"),
        _alert(id="other", event="Special Weather Statement"),
    ]

    summary = build_alert_summary(
        alerts,
        scope="active",
        scope_label="Active Location",
        updated_at=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
        refresh_interval_seconds=60,
        affected_location_count=1,
    )

    assert summary.total == 4
    assert summary.warning_count == 1
    assert summary.watch_count == 1
    assert summary.advisory_count == 1
    assert summary.other_count == 1
    assert summary.partial is False
    assert summary.errors == []


def test_build_alert_summary_keeps_test_source_on_highest_alert() -> None:
    summary = build_alert_summary(
        [
            _alert(id="nws-watch", source="nws", event="Tornado Watch", priority_score=500, priority=500),
            _alert(
                id="test-warning",
                source="test",
                event="TEST: Tornado Warning",
                priority_score=1000,
                priority=1000,
            ),
        ],
        scope="active",
        scope_label="Active Location",
        updated_at=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
        refresh_interval_seconds=60,
        affected_location_count=1,
    )

    assert summary.highest_alert is not None
    assert summary.highest_alert.id == "test-warning"
    assert summary.highest_alert.source == "test"
    assert summary.highest_alert.event == "TEST: Tornado Warning"


def test_empty_alert_summary_has_no_highest_alert() -> None:
    summary = build_alert_summary(
        [],
        scope="active",
        scope_label="Active Location",
        updated_at=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
        refresh_interval_seconds=60,
        affected_location_count=1,
    )

    assert summary.total == 0
    assert summary.warning_count == 0
    assert summary.watch_count == 0
    assert summary.advisory_count == 0
    assert summary.other_count == 0
    assert summary.highest_alert is None


def test_highest_alert_uses_priority_score_then_priority_then_severity_rank_then_severity() -> None:
    by_priority_score = SimpleNamespace(
        id="score",
        priority_score=900,
        priority=1,
        severity_rank=1,
        severity="Minor",
    )
    by_priority = SimpleNamespace(
        id="priority",
        priority_score=800,
        priority=1000,
        severity_rank=1,
        severity="Minor",
    )

    assert choose_highest_alert([by_priority, by_priority_score]).id == "score"

    by_severity_rank = SimpleNamespace(
        id="severity-rank",
        priority_score=800,
        priority=1000,
        severity_rank=4,
        severity="Minor",
    )
    by_severity_text = SimpleNamespace(
        id="severity-text",
        priority_score=800,
        priority=1000,
        severity_rank=1,
        severity="Extreme",
    )

    assert choose_highest_alert([by_priority, by_severity_rank]).id == "severity-rank"
    assert choose_highest_alert([by_severity_text, by_priority]).id == "severity-text"
