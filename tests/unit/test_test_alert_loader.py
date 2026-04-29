import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.alerts import test_alert_loader as loader_module
from app.api.routes import test_alerts as test_alerts_route
from app.models.location import Location
from app.services import alert_service
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


def _settings(alert_file) -> SimpleNamespace:
    return SimpleNamespace(test_alerts_file=alert_file)


def _alert(**overrides) -> dict:
    data = {
        "enabled": True,
        "id": "relative-test-alert",
        "source": "test",
        "event": "Tornado Warning",
        "severity": "Extreme",
        "urgency": "Immediate",
        "certainty": "Observed",
        "headline": "Relative tornado warning",
        "description": "Relative test alert.",
        "instruction": "Take shelter.",
        "areaDesc": "Kalamazoo",
        "effective": "2099-01-01T00:00:00Z",
        "expires": "2099-01-01T01:00:00Z",
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
        "parameters": {"tornadoDetection": ["OBSERVED"]},
    }
    data.update(overrides)
    return data


def _write_payload(alert_file, *alerts) -> str:
    payload = {"alerts": list(alerts)}
    text = json.dumps(payload, indent=2) + "\n"
    alert_file.write_text(text, encoding="utf-8")
    return text


def test_relative_time_creates_active_test_alert_timestamps(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    alerts = parse_nws_alerts({"features": features}, _location(), source="test")

    assert len(alerts) == 1
    assert alerts[0].effective == current_time - timedelta(minutes=5)
    assert alerts[0].expires == current_time + timedelta(minutes=90)
    assert alerts[0].source == "test"
    assert alerts[0].geometry is not None
    assert alerts[0].areaDesc == "Kalamazoo"


def test_relative_time_wins_over_absolute_timestamps(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            effective="2099-01-01T00:00:00Z",
            expires="2099-01-01T01:00:00Z",
            relative_time={
                "effective_minutes_from_now": -10,
                "expires_minutes_from_now": 30,
            },
        ),
    )

    feature = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())[0]

    assert feature["properties"]["effective"] == "2026-04-29T17:50:00Z"
    assert feature["properties"]["expires"] == "2026-04-29T18:30:00Z"


def test_absolute_timestamps_still_work_without_relative_time(tmp_path) -> None:
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            effective="2026-04-29T17:00:00Z",
            expires="2099-01-01T01:00:00Z",
            relative_time=None,
        ),
    )

    feature = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())[0]

    assert feature["properties"]["effective"] == "2026-04-29T17:00:00Z"
    assert feature["properties"]["expires"] == "2099-01-01T01:00:00Z"


def test_missing_relative_time_does_not_crash(tmp_path) -> None:
    alert_file = tmp_path / "alerts_test.json"
    original = _write_payload(alert_file, _alert())

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())

    assert len(features) == 1
    assert alert_file.read_text(encoding="utf-8") == original


def test_loader_does_not_write_resolved_timestamps_to_test_alert_file(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    original = _write_payload(
        alert_file,
        _alert(
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())

    assert alert_file.read_text(encoding="utf-8") == original


def test_test_alerts_expose_same_core_dto_fields_as_nws_alerts(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    alert = parse_nws_alerts({"features": features}, _location(), source="test")[0]
    payload = alert.model_dump(mode="json")

    assert payload["id"] == "relative-test-alert"
    assert payload["source"] == "test"
    assert payload["event"] == "Tornado Warning"
    assert payload["geometry"]["type"] == "Polygon"
    assert payload["areaDesc"] == "Kalamazoo"
    assert payload["raw_properties"]["parameters"]["tornadoDetection"] == ["OBSERVED"]
    assert payload["nws_details"]["tornadoDetection"] == "OBSERVED"


def test_editor_validation_accepts_relative_time_without_absolute_timestamps() -> None:
    payload = {
        "alerts": [
            _alert(
                effective=None,
                expires=None,
                relative_time={
                    "effective_minutes_from_now": -5,
                    "expires_minutes_from_now": 90,
                },
            )
        ]
    }

    validated = test_alerts_route._validate_test_alert_payload(payload)

    assert validated["alerts"][0]["relative_time"]["expires_minutes_from_now"] == 90
