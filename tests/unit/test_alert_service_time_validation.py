from datetime import UTC, datetime

from app.models.location import Location
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


def _feature(alert_id: str, effective, expires) -> dict:
    return {
        "type": "Feature",
        "id": alert_id,
        "properties": {
            "id": alert_id,
            "event": "Test Warning",
            "severity": "Severe",
            "urgency": "Immediate",
            "certainty": "Observed",
            "headline": "Test warning",
            "description": "Test warning details.",
            "areaDesc": "Kalamazoo",
            "effective": effective,
            "expires": expires,
        },
        "geometry": None,
    }


def test_parse_nws_alerts_keeps_utc_timestamps() -> None:
    payload = {
        "features": [
            _feature(
                "valid-alert",
                "2099-04-27T12:00:00-04:00",
                "2099-04-27T18:00:00Z",
            )
        ]
    }

    alerts = parse_nws_alerts(payload, _location())

    assert len(alerts) == 1
    assert alerts[0].effective == datetime(2099, 4, 27, 16, 0, tzinfo=UTC)
    assert alerts[0].expires == datetime(2099, 4, 27, 18, 0, tzinfo=UTC)
    assert alerts[0].raw_properties["id"] == "valid-alert"


def test_parse_nws_alerts_rejects_timezone_less_effective_timestamp() -> None:
    payload = {
        "features": [
            _feature(
                "invalid-effective",
                "2099-04-27T12:00:00",
                "2099-04-27T18:00:00Z",
            )
        ]
    }

    assert parse_nws_alerts(payload, _location()) == []


def test_parse_nws_alerts_rejects_timezone_less_expires_timestamp() -> None:
    payload = {
        "features": [
            _feature(
                "invalid-expires",
                "2099-04-27T12:00:00Z",
                "2099-04-27T18:00:00",
            )
        ]
    }

    assert parse_nws_alerts(payload, _location()) == []


def test_parse_nws_alerts_rejects_naive_datetime_timestamps() -> None:
    payload = {
        "features": [
            _feature(
                "invalid-naive",
                datetime(2099, 4, 27, 12, 0),
                datetime(2099, 4, 27, 18, 0, tzinfo=UTC),
            )
        ]
    }

    assert parse_nws_alerts(payload, _location()) == []
