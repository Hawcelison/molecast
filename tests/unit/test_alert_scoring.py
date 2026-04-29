from datetime import UTC, datetime
from types import SimpleNamespace

from app.alerts.scoring import (
    CERTAINTY_RANKS,
    SEVERITY_RANKS,
    normalize_alert_value,
    rank_alert_value,
    score_alert,
    sort_alerts_by_priority,
)


def test_score_alert_preserves_severity_urgency_certainty_ranking() -> None:
    priority = score_alert("Severe", "Immediate", "Observed")

    assert priority.priority_score == 455
    assert priority.severity_rank == 4
    assert priority.urgency_rank == 5
    assert priority.certainty_rank == 5


def test_score_alert_normalizes_unknown_values() -> None:
    priority = score_alert(" ", None, "Not A Certainty")

    assert priority.priority_score == 111
    assert normalize_alert_value(" Severe ") == "severe"
    assert rank_alert_value("Extreme", SEVERITY_RANKS) == 5
    assert rank_alert_value("Observed", CERTAINTY_RANKS) == 5


def test_score_alert_extreme_immediate_observed_priority_remains_stable() -> None:
    priority = score_alert("Extreme", "Immediate", "Observed")

    assert priority.priority_score == 555
    assert priority.severity_rank == 5
    assert priority.urgency_rank == 5
    assert priority.certainty_rank == 5


def test_sort_alerts_by_priority_preserves_existing_ordering() -> None:
    low = SimpleNamespace(
        priority_score=111,
        severity_rank=1,
        urgency_rank=1,
        certainty_rank=1,
        effective=datetime(2099, 1, 1, tzinfo=UTC),
    )
    high = SimpleNamespace(
        priority_score=455,
        severity_rank=4,
        urgency_rank=5,
        certainty_rank=5,
        effective=datetime(2099, 1, 1, tzinfo=UTC),
    )

    assert sort_alerts_by_priority([low, high]) == [high, low]
