from datetime import UTC, datetime, timezone, timedelta

from app.services.alert_time import has_invalid_alert_time, parse_alert_time_utc


def test_parse_alert_time_utc_converts_zulu_timestamp_to_utc() -> None:
    parsed = parse_alert_time_utc("2026-04-27T12:30:00Z")

    assert parsed == datetime(2026, 4, 27, 12, 30, tzinfo=UTC)


def test_parse_alert_time_utc_converts_offset_timestamp_to_utc() -> None:
    parsed = parse_alert_time_utc("2026-04-27T08:30:00-04:00")

    assert parsed == datetime(2026, 4, 27, 12, 30, tzinfo=UTC)


def test_parse_alert_time_utc_rejects_timezone_less_string() -> None:
    assert parse_alert_time_utc("2026-04-27T12:30:00") is None
    assert has_invalid_alert_time("2026-04-27T12:30:00") is True


def test_parse_alert_time_utc_rejects_naive_datetime() -> None:
    naive_timestamp = datetime(2026, 4, 27, 12, 30)

    assert parse_alert_time_utc(naive_timestamp) is None
    assert has_invalid_alert_time(naive_timestamp) is True


def test_parse_alert_time_utc_converts_aware_datetime_to_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    aware_timestamp = datetime(2026, 4, 27, 8, 30, tzinfo=eastern)

    assert parse_alert_time_utc(aware_timestamp) == datetime(
        2026,
        4,
        27,
        12,
        30,
        tzinfo=UTC,
    )


def test_missing_alert_time_is_not_invalid() -> None:
    assert parse_alert_time_utc(None) is None
    assert has_invalid_alert_time(None) is False
