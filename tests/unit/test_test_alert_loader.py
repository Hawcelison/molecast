import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.alerts import test_alert_loader as loader_module
from app.alerts.presentation import build_alert_presentation
from app.alerts.test_targets import normalize_test_alert_targets
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
        county_fips="26077",
        zip_code="49002",
        latitude=42.2012,
        longitude=-85.58,
        county_zone="MIC077",
        forecast_zone="MIZ072",
        fire_weather_zone="MIZ072",
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


class FakeZoneGeometryService:
    def __init__(self, geometry: dict) -> None:
        self.geometry = geometry
        self.calls: list[list[str]] = []

    def resolve_affected_zones(self, affected_zones: list[str] | None) -> dict | None:
        self.calls.append(list(affected_zones or []))
        return self.geometry


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


def test_test_alert_editor_get_does_not_rewrite_fixture(tmp_path, monkeypatch) -> None:
    alert_file = tmp_path / "alerts_test.json"
    original = _write_payload(
        alert_file,
        _alert(source=None),
    )
    monkeypatch.setattr(test_alerts_route, "_resolve_test_alert_file", lambda: alert_file)

    response = test_alerts_route.get_test_alerts()

    assert response["alert_count"] == 1
    assert response["alerts"][0]["source"] == "test"
    assert alert_file.read_text(encoding="utf-8") == original


def test_test_alert_status_does_not_rewrite_relative_time_fixture(tmp_path, monkeypatch) -> None:
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
    monkeypatch.setattr(test_alerts_route, "_resolve_test_alert_file", lambda: alert_file)
    monkeypatch.setattr(
        test_alerts_route,
        "_active_source_counts",
        lambda db, refresh=False: {
            "test": 1,
            "nws": 0,
            "total": 1,
            "refreshed_at": datetime(2026, 4, 29, 18, 0, tzinfo=UTC),
        },
    )

    response = test_alerts_route.get_test_alert_status(refresh=True, db=object())

    assert response["test_enabled"] == 1
    assert response["test_active"] == 1
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


def test_known_catalog_event_polygon_mode_works_with_non_tornado_event(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            id="flash-flood-polygon",
            event="Flash Flood Warning",
            severity="Severe",
            urgency="Immediate",
            certainty="Likely",
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    alert = parse_nws_alerts({"features": features}, _location(), source="test")[0]

    assert alert.event == "Flash Flood Warning"
    assert alert.geometry is not None
    assert alert.geometry_source == "alert"
    assert alert.color_hex == "#00FF00"


def test_loader_preserves_zone_alert_fields(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    zone_url = "https://api.weather.gov/zones/forecast/MIZ072"
    _write_payload(
        alert_file,
        _alert(
            event="Freeze Watch",
            severity="Severe",
            urgency="Future",
            certainty="Possible",
            geometry=None,
            affectedZones=[zone_url],
            geocode={"UGC": ["MIZ072"], "SAME": ["026077"]},
        ),
    )

    feature = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())[0]

    assert feature["geometry"] is None
    assert feature["properties"]["affectedZones"] == [zone_url]
    assert feature["properties"]["geocode"] == {"UGC": ["MIZ072"], "SAME": ["026077"]}


def test_target_normalization_normalizes_supported_fields() -> None:
    targets = normalize_test_alert_targets(
        {
            "zip_codes": ["49002-1234", 10001],
            "location_ids": ["1", 4],
            "county_fips": ["6077", "26077"],
            "county_zones": ["mic077"],
            "forecast_zones": ["https://api.weather.gov/zones/forecast/miz072"],
            "same": ["26077"],
            "ugc": ["mic077", "miz072"],
        }
    )

    assert targets == {
        "zip_codes": ["49002", "10001"],
        "location_ids": [1, 4],
        "county_fips": ["06077", "26077"],
        "county_zones": ["MIC077"],
        "forecast_zones": ["MIZ072"],
        "same": ["026077"],
        "ugc": ["MIC077", "MIZ072"],
    }


def test_editor_validation_normalizes_targets_and_forces_test_source() -> None:
    payload = {
        "alerts": [
            _alert(
                source="nws",
                geometry=None,
                targets={
                    "zip_codes": ["49002-1234"],
                    "location_ids": ["1"],
                    "county_fips": ["26077"],
                    "county_zones": ["mic077"],
                    "forecast_zones": ["miz072"],
                    "same": ["26077"],
                    "ugc": ["mic077"],
                },
            )
        ]
    }

    validated = test_alerts_route._validate_test_alert_payload(payload)

    alert = validated["alerts"][0]
    assert alert["source"] == "test"
    assert alert["targets"] == {
        "zip_codes": ["49002"],
        "location_ids": [1],
        "county_fips": ["26077"],
        "county_zones": ["MIC077"],
        "forecast_zones": ["MIZ072"],
        "same": ["026077"],
        "ugc": ["MIC077"],
    }


def test_loader_preserves_normalized_targets(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            source="nws",
            geometry=None,
            targets={"zip_codes": ["49002-1234"], "forecast_zones": ["miz072"]},
        ),
    )

    feature = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())[0]

    assert feature["source"] == "test"
    assert feature["properties"]["source"] == "test"
    assert feature["properties"]["targets"] == {
        "zip_codes": ["49002"],
        "forecast_zones": ["MIZ072"],
    }


def test_zip_targeted_test_alert_matches_active_location_only_when_zip_matches(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            geometry=None,
            areaDesc="Kalamazoo",
            targets={"zip_codes": ["49002"]},
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    alerts = parse_nws_alerts({"features": features}, _location(), source="test")

    assert [alert.id for alert in alerts] == ["relative-test-alert"]
    assert alerts[0].match.match_type == "zip_code"


def test_zip_targeted_test_alert_for_10001_does_not_match_active_49002(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            geometry=None,
            areaDesc="Kalamazoo",
            targets={"zip_codes": ["10001"]},
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    alerts = parse_nws_alerts({"features": features}, _location(), source="test")

    assert alerts == []


def test_explicit_targets_are_authoritative_over_area_desc_fallback(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            geometry=None,
            areaDesc="Kalamazoo",
            targets={"location_ids": [999]},
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    alerts = parse_nws_alerts({"features": features}, _location(), source="test")

    assert alerts == []


def test_no_target_legacy_test_alert_still_matches_active_area_desc(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            geometry=None,
            areaDesc="Kalamazoo",
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    alerts = parse_nws_alerts({"features": features}, _location(), source="test")

    assert [alert.id for alert in alerts] == ["relative-test-alert"]
    assert alerts[0].match.match_type == "county"


def test_zone_mode_test_alert_gets_affected_zone_fallback_geometry(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    zone_url = "https://api.weather.gov/zones/forecast/MIZ072"
    fallback_geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [-85.7, 42.1],
                [-85.4, 42.1],
                [-85.4, 42.3],
                [-85.7, 42.1],
            ]
        ],
    }
    _write_payload(
        alert_file,
        _alert(
            event="Freeze Watch",
            severity="Severe",
            urgency="Future",
            certainty="Possible",
            geometry=None,
            affectedZones=[zone_url],
            geocode={"UGC": ["MIZ072"]},
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    zone_service = FakeZoneGeometryService(fallback_geometry)
    alert = parse_nws_alerts(
        {"features": features},
        _location(),
        source="test",
        zone_geometry_service=zone_service,
    )[0]

    assert alert.geometry == fallback_geometry
    assert alert.geometry_source == "affectedZones"
    assert alert.affectedZones == [zone_url]
    assert zone_service.calls == [[zone_url]]


def test_zone_mode_works_with_non_freeze_event(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    zone_url = "https://api.weather.gov/zones/forecast/MIZ072"
    fallback_geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [-85.7, 42.1],
                [-85.4, 42.1],
                [-85.4, 42.3],
                [-85.7, 42.1],
            ]
        ],
    }
    _write_payload(
        alert_file,
        _alert(
            id="winter-weather-zone",
            event="Winter Weather Advisory",
            severity="Minor",
            urgency="Expected",
            certainty="Likely",
            geometry=None,
            affectedZones=[zone_url],
            geocode={"UGC": ["MIZ072"]},
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    alert = parse_nws_alerts(
        {"features": features},
        _location(),
        source="test",
        zone_geometry_service=FakeZoneGeometryService(fallback_geometry),
    )[0]

    assert alert.event == "Winter Weather Advisory"
    assert alert.geometry_source == "affectedZones"
    assert alert.geometry == fallback_geometry
    assert alert.affectedZones == [zone_url]


def test_unknown_custom_event_saves_and_uses_backend_fallback_presentation(tmp_path, monkeypatch) -> None:
    current_time = datetime(2026, 4, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(loader_module, "now_utc", lambda: current_time)
    monkeypatch.setattr(alert_service, "now_utc", lambda: current_time)
    alert_file = tmp_path / "alerts_test.json"
    _write_payload(
        alert_file,
        _alert(
            id="custom-local-event",
            event="Custom NWS Style Test Event",
            severity="Moderate",
            urgency="Expected",
            certainty="Possible",
            relative_time={
                "effective_minutes_from_now": -5,
                "expires_minutes_from_now": 90,
            },
        ),
    )
    test_alerts_route._validate_test_alert_payload(
        {"alerts": [_alert(event="Custom NWS Style Test Event", severity="Moderate")]}
    )

    features = loader_module.TestAlertLoader(_settings(alert_file)).load_enabled_alert_features(_location())
    alert = parse_nws_alerts({"features": features}, _location(), source="test")[0]
    presentation = build_alert_presentation(alert, _location())

    assert alert.event == "Custom NWS Style Test Event"
    assert alert.color_hex == "#FFFF00"
    assert alert.icon == "alert-circle"
    assert alert.sound_profile == "default"
    assert alert.priority == 300
    assert presentation.title == "CUSTOM NWS STYLE TEST EVENT"


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


def test_editor_validation_accepts_zone_mode_alert() -> None:
    zone_url = "https://api.weather.gov/zones/forecast/MIZ072"
    payload = {
        "alerts": [
            _alert(
                geometry=None,
                affectedZones=[zone_url],
                geocode={"UGC": ["MIZ072"], "SAME": ["026077"]},
            )
        ]
    }

    validated = test_alerts_route._validate_test_alert_payload(payload)

    assert validated["alerts"][0]["geometry"] is None
    assert validated["alerts"][0]["affectedZones"] == [zone_url]


def test_editor_validation_accepts_multipolygon_geometry() -> None:
    payload = {
        "alerts": [
            _alert(
                geometry={
                    "type": "MultiPolygon",
                    "coordinates": [
                        [
                            [
                                [-85.7, 42.1],
                                [-85.4, 42.1],
                                [-85.4, 42.3],
                                [-85.7, 42.1],
                            ]
                        ]
                    ],
                },
            )
        ]
    }

    validated = test_alerts_route._validate_test_alert_payload(payload)

    assert validated["alerts"][0]["geometry"]["type"] == "MultiPolygon"


def test_editor_validation_rejects_invalid_polygon() -> None:
    payload = {
        "alerts": [
            _alert(
                geometry={
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-85.7, 42.1],
                            [-85.4, 42.1],
                            [-85.4, 42.3],
                        ]
                    ],
                },
            )
        ]
    }

    try:
        test_alerts_route._validate_test_alert_payload(payload)
    except Exception as exc:
        assert "polygon ring needs at least 4 coordinate pairs" in exc.detail
    else:
        raise AssertionError("Invalid polygon should be rejected.")


def test_editor_validation_rejects_invalid_affected_zones() -> None:
    payload = {"alerts": [_alert(geometry=None, affectedZones=["https://example.com/zones/forecast/MIZ072"])]}

    try:
        test_alerts_route._validate_test_alert_payload(payload)
    except Exception as exc:
        assert "affectedZones must contain NWS zone URLs" in exc.detail
    else:
        raise AssertionError("Invalid affectedZones should be rejected.")


def test_editor_validation_rejects_non_list_geocode_values() -> None:
    payload = {"alerts": [_alert(geometry=None, geocode={"UGC": "MIZ072"})]}

    try:
        test_alerts_route._validate_test_alert_payload(payload)
    except Exception as exc:
        assert "geocode.UGC must be an array" in exc.detail
    else:
        raise AssertionError("Invalid geocode should be rejected.")
