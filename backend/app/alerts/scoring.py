from app.alerts.models import AlertPriority


SEVERITY_RANKS = {
    "extreme": 5,
    "severe": 4,
    "moderate": 3,
    "minor": 2,
    "unknown": 1,
}

URGENCY_RANKS = {
    "immediate": 5,
    "expected": 4,
    "future": 3,
    "past": 2,
    "unknown": 1,
}

CERTAINTY_RANKS = {
    "observed": 5,
    "likely": 4,
    "possible": 3,
    "unlikely": 2,
    "unknown": 1,
}


def score_alert(
    severity: str | None,
    urgency: str | None,
    certainty: str | None,
) -> AlertPriority:
    severity_rank = rank_alert_value(severity, SEVERITY_RANKS)
    urgency_rank = rank_alert_value(urgency, URGENCY_RANKS)
    certainty_rank = rank_alert_value(certainty, CERTAINTY_RANKS)

    return AlertPriority(
        priority_score=(severity_rank * 100) + (urgency_rank * 10) + certainty_rank,
        severity_rank=severity_rank,
        urgency_rank=urgency_rank,
        certainty_rank=certainty_rank,
    )


def sort_alerts_by_priority(alerts):
    return sorted(
        alerts,
        key=lambda alert: (
            alert.priority_score,
            alert.severity_rank,
            alert.urgency_rank,
            alert.certainty_rank,
            alert.effective.isoformat() if alert.effective else "",
        ),
        reverse=True,
    )


def rank_alert_value(value: str | None, rank_map: dict[str, int]) -> int:
    normalized_value = normalize_alert_value(value)
    return rank_map.get(normalized_value, rank_map["unknown"])


def normalize_alert_value(value: str | None) -> str:
    if value is None:
        return "unknown"
    return value.strip().lower() or "unknown"

