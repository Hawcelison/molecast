from datetime import UTC, datetime
from pathlib import Path

from app.alerts.saved_summary import SavedAlertSummaryService
from app.models.location import Location
from app.schemas.alert import WeatherAlert
from app.services.alert_service import AlertZoneFetchError


def _location(**overrides) -> Location:
    data = {
        "id": 1,
        "label": "Portage, MI",
        "name": "Portage",
        "city": "Portage",
        "state": "MI",
        "county": "Kalamazoo",
        "county_fips": "26077",
        "zip_code": "49002",
        "latitude": 42.2012,
        "longitude": -85.58,
        "county_zone": "MIC077",
        "forecast_zone": "MIZ072",
        "fire_weather_zone": "MIZ072",
        "updated_at": datetime(2026, 5, 4, 12, 0),
        "is_primary": True,
    }
    data.update(overrides)
    return Location(**data)


def _feature(
    alert_id: str,
    *,
    event: str = "Tornado Warning",
    severity: str = "Extreme",
    affected_zones: list[str] | None = None,
    geocode: dict | None = None,
    parameters: dict | None = None,
    targets: dict | None = None,
    geometry: dict | None = None,
) -> dict:
    return {
        "type": "Feature",
        "id": alert_id,
        "properties": {
            "id": alert_id,
            "event": event,
            "severity": severity,
            "urgency": "Immediate",
            "certainty": "Observed",
            "headline": f"{event} headline",
            "description": f"{event} description",
            "areaDesc": None,
            "affectedZones": affected_zones or [],
            "effective": "2026-01-01T00:00:00Z",
            "expires": "2099-01-01T00:00:00Z",
            "geocode": geocode or {},
            "parameters": parameters or {},
            "targets": targets,
        },
        "geometry": geometry,
    }


class FakeProvider:
    def __init__(self, zone_payloads=None, failing_zones=None, fallback_payloads=None) -> None:
        self.zone_payloads = zone_payloads or {}
        self.failing_zones = set(failing_zones or [])
        self.fallback_payloads = fallback_payloads or {}
        self.zone_calls = []
        self.fallback_calls = []

    def fetch_zone_alerts(self, zone_id: str) -> dict:
        self.zone_calls.append(zone_id)
        if zone_id in self.failing_zones:
            raise AlertZoneFetchError(f"{zone_id} failed")
        return {"type": "FeatureCollection", "features": self.zone_payloads.get(zone_id, [])}

    def fetch_active_alerts(self, location: Location) -> dict:
        self.fallback_calls.append(location.id)
        return {
            "type": "FeatureCollection",
            "features": self.fallback_payloads.get(location.id, []),
        }


class FakeTestAlertLoader:
    def __init__(self, features=None) -> None:
        self.features = features or []
        self.calls = []
        self.mtime = 123.0

    def alert_file_mtime(self):
        return self.mtime

    def load_enabled_alert_features(self, location: Location, *, include_location_area_fallback=True):
        self.calls.append(include_location_area_fallback)
        return self.features


def _service(provider: FakeProvider, loader: FakeTestAlertLoader) -> SavedAlertSummaryService:
    return SavedAlertSummaryService(
        provider=provider,
        test_alert_loader=loader,
        refresh_interval_seconds=60,
    )


def _active_alert(
    alert_id: str,
    *,
    source: str = "nws",
    event: str = "Special Weather Statement",
    priority: int = 150,
    match_type: str = "geometry",
) -> WeatherAlert:
    return WeatherAlert.model_validate(
        {
            "id": alert_id,
            "source": source,
            "event": event,
            "severity": "Moderate",
            "urgency": "Expected",
            "certainty": "Observed",
            "headline": f"{event} headline",
            "description": f"{event} description",
            "areaDesc": "Kalamazoo",
            "affectedZones": [],
            "effective": datetime(2026, 1, 1, tzinfo=UTC),
            "expires": datetime(2099, 1, 1, tzinfo=UTC),
            "geometry": None,
            "geometry_source": None,
            "raw_properties": {"id": alert_id, "source": source},
            "match": {
                "match_type": match_type,
                "matched_value": "42.2012,-85.58",
                "confidence": "high",
            },
            "color_hex": "#FFE4B5",
            "icon": "info",
            "sound_profile": "none",
            "priority": priority,
            "priority_score": priority,
            "severity_rank": 3,
            "urgency_rank": 4,
            "certainty_rank": 5,
            "nws_details": {},
        }
    )


def test_saved_summary_aggregates_saved_locations_and_dedupes_shared_alert() -> None:
    locations = [
        _location(id=1, county_zone="MIC077", forecast_zone="MIZ072", zip_code="49002"),
        _location(
            id=2,
            label="Battle Creek, MI",
            city="Battle Creek",
            county="Calhoun",
            county_fips="26025",
            zip_code="49015",
            county_zone="MIC025",
            forecast_zone="MIZ078",
        ),
    ]
    shared = _feature(
        "shared-warning",
        affected_zones=[
            "https://api.weather.gov/zones/county/MIC077",
            "https://api.weather.gov/zones/county/MIC025",
        ],
        geocode={"UGC": ["MIC077", "MIC025"]},
    )
    provider = FakeProvider(zone_payloads={"MIC077": [shared], "MIC025": [shared]})

    summary = _service(provider, FakeTestAlertLoader()).get_saved_summary(locations)

    assert summary.scope == "saved"
    assert summary.scope_label == "All Saved Locations"
    assert summary.total == 1
    assert summary.warning_count == 1
    assert summary.saved_location_count == 2
    assert summary.affected_location_count == 2
    assert provider.fallback_calls == []
    assert summary.alert_refs[0].source == "nws"
    assert summary.alert_refs[0].affected_location_count == 2
    assert [ref.id for ref in summary.alert_refs[0].affected_locations] == [1, 2]
    assert {ref.match_type for ref in summary.alert_refs[0].affected_locations} == {"zone"}


def test_saved_summary_includes_active_stream_alert_under_active_location() -> None:
    active_location = _location(id=1, county_zone="MIC077", forecast_zone="MIZ072")
    other_location = _location(
        id=2,
        label="New York, NY",
        city="New York",
        state="NY",
        county="New York",
        county_fips="36061",
        zip_code="10001",
        county_zone="NYC061",
        forecast_zone="NYZ072",
    )
    active_alert = _active_alert("active-only-special-weather-statement")

    summary = _service(FakeProvider(), FakeTestAlertLoader()).get_saved_summary(
        [active_location, other_location],
        active_location=active_location,
        active_alerts=[active_alert],
    )

    assert summary.total == 1
    assert summary.alert_refs[0].id == active_alert.id
    assert summary.alert_refs[0].source == "nws"
    assert [ref.id for ref in summary.alert_refs[0].affected_locations] == [active_location.id]
    assert summary.alert_refs[0].affected_locations[0].match_type == "geometry"


def test_saved_summary_dedupes_active_stream_alert_already_in_saved_aggregation() -> None:
    active_location = _location(id=1, county_zone="MIC077", forecast_zone="MIZ072")
    other_location = _location(
        id=2,
        label="Battle Creek, MI",
        city="Battle Creek",
        county="Calhoun",
        county_fips="26025",
        zip_code="49015",
        county_zone="MIC025",
        forecast_zone="MIZ078",
    )
    shared = _feature(
        "shared-special-weather-statement",
        event="Special Weather Statement",
        severity="Moderate",
        affected_zones=["MIC077", "MIC025"],
        geocode={"UGC": ["MIC077", "MIC025"]},
    )
    active_alert = _active_alert("shared-special-weather-statement")
    provider = FakeProvider(zone_payloads={"MIC077": [shared], "MIC025": [shared]})

    summary = _service(provider, FakeTestAlertLoader()).get_saved_summary(
        [active_location, other_location],
        active_location=active_location,
        active_alerts=[active_alert],
    )

    assert summary.total == 1
    assert summary.alert_refs[0].id == active_alert.id
    assert [ref.id for ref in summary.alert_refs[0].affected_locations] == [1, 2]


def test_saved_summary_active_no_target_test_alert_matches_active_location_only() -> None:
    active_location = _location(id=1, zip_code="49002")
    other_location = _location(id=2, zip_code="49015", county_zone="MIC025", forecast_zone="MIZ078")
    blank_test_feature = _feature("blank-test-warning", event="TEST: Tornado Warning")
    active_alert = _active_alert(
        "blank-test-warning",
        source="test",
        event="TEST: Tornado Warning",
        priority=1000,
        match_type="county",
    )

    summary = _service(FakeProvider(), FakeTestAlertLoader([blank_test_feature])).get_saved_summary(
        [active_location, other_location],
        active_location=active_location,
        active_alerts=[active_alert],
    )

    assert summary.total == 1
    assert summary.alert_refs[0].source == "test"
    assert [ref.id for ref in summary.alert_refs[0].affected_locations] == [active_location.id]
    assert summary.affected_location_count == 1


def test_saved_summary_counts_categories_and_selects_highest_across_locations() -> None:
    location = _location()
    provider = FakeProvider(
        zone_payloads={
            "MIC077": [
                _feature("watch", event="Tornado Watch", severity="Severe", affected_zones=["MIC077"]),
                _feature("advisory", event="Winter Weather Advisory", severity="Moderate", affected_zones=["MIC077"]),
                _feature("other", event="Special Weather Statement", severity="Minor", affected_zones=["MIC077"]),
                _feature("warning", event="Tornado Warning", severity="Extreme", affected_zones=["MIC077"]),
            ]
        }
    )

    summary = _service(provider, FakeTestAlertLoader()).get_saved_summary([location])

    assert summary.total == 4
    assert summary.warning_count == 1
    assert summary.watch_count == 1
    assert summary.advisory_count == 1
    assert summary.other_count == 1
    assert summary.highest_alert is not None
    assert summary.highest_alert.id == "warning"
    assert summary.highest_alert.affected_location_count == 1


def test_saved_summary_preserves_test_source_and_matches_zip_code_parameter() -> None:
    location = _location(zip_code="49002")
    test_feature = _feature(
        "test-zip-warning",
        event="TEST: Tornado Warning",
        parameters={"zipCode": ["49002"]},
    )

    summary = _service(FakeProvider(), FakeTestAlertLoader([test_feature])).get_saved_summary([location])

    assert summary.total == 1
    assert summary.highest_alert is not None
    assert summary.highest_alert.source == "test"
    assert summary.alert_refs[0].source == "test"
    assert summary.alert_refs[0].affected_locations[0].match_type == "zip_code"


def test_saved_summary_counts_zip_targeted_test_alert_for_saved_zip() -> None:
    locations = [_location(id=1, zip_code="49002"), _location(id=5, zip_code="10001", county_zone="NYC061")]
    test_feature = _feature(
        "test-zip-10001",
        event="TEST: Tornado Warning",
        targets={"zip_codes": ["10001"]},
    )

    summary = _service(FakeProvider(), FakeTestAlertLoader([test_feature])).get_saved_summary(locations)

    assert summary.total == 1
    assert summary.alert_refs[0].source == "test"
    assert [ref.id for ref in summary.alert_refs[0].affected_locations] == [5]
    assert summary.alert_refs[0].affected_locations[0].match_type == "zip_code"


def test_saved_summary_location_id_target_matches_only_that_saved_location() -> None:
    locations = [_location(id=1, zip_code="49002"), _location(id=4, zip_code="49005")]
    test_feature = _feature(
        "test-location-id",
        event="TEST: Tornado Warning",
        targets={"location_ids": [4]},
    )

    summary = _service(FakeProvider(), FakeTestAlertLoader([test_feature])).get_saved_summary(locations)

    assert summary.total == 1
    assert [ref.id for ref in summary.alert_refs[0].affected_locations] == [4]
    assert summary.alert_refs[0].affected_locations[0].match_type == "location_id"


def test_saved_summary_county_fips_target_matches_locations_in_county() -> None:
    locations = [
        _location(id=1, county_fips="26077"),
        _location(id=2, county_fips="26077", zip_code="49007"),
        _location(id=3, county_fips="26025", county_zone="MIC025", zip_code="49015"),
    ]
    test_feature = _feature("test-county-fips", targets={"county_fips": ["26077"]})

    summary = _service(FakeProvider(), FakeTestAlertLoader([test_feature])).get_saved_summary(locations)

    assert summary.total == 1
    assert [ref.id for ref in summary.alert_refs[0].affected_locations] == [1, 2]
    assert {ref.match_type for ref in summary.alert_refs[0].affected_locations} == {"county_fips"}


def test_saved_summary_zone_targets_match_saved_location_zones() -> None:
    locations = [
        _location(id=1, county_zone="MIC077", forecast_zone="MIZ072"),
        _location(id=2, county_zone="MIC025", forecast_zone="MIZ078", zip_code="49015"),
    ]
    county_feature = _feature("test-county-zone", targets={"county_zones": ["MIC077"]})
    forecast_feature = _feature("test-forecast-zone", targets={"forecast_zones": ["MIZ078"]})

    summary = _service(
        FakeProvider(),
        FakeTestAlertLoader([county_feature, forecast_feature]),
    ).get_saved_summary(locations)

    refs_by_id = {ref.id: ref for ref in summary.alert_refs}
    assert [ref.id for ref in refs_by_id["test-county-zone"].affected_locations] == [1]
    assert refs_by_id["test-county-zone"].affected_locations[0].match_type == "county_zone"
    assert [ref.id for ref in refs_by_id["test-forecast-zone"].affected_locations] == [2]
    assert refs_by_id["test-forecast-zone"].affected_locations[0].match_type == "forecast_zone"


def test_saved_summary_same_and_ugc_targets_match_saved_locations() -> None:
    locations = [
        _location(id=1, county_fips="26077", county_zone="MIC077", forecast_zone="MIZ072"),
        _location(id=2, county_fips="26025", county_zone="MIC025", forecast_zone="MIZ078", zip_code="49015"),
    ]
    same_feature = _feature("test-same", targets={"same": ["026077"]})
    ugc_feature = _feature("test-ugc", targets={"ugc": ["MIZ078"]})

    summary = _service(
        FakeProvider(),
        FakeTestAlertLoader([same_feature, ugc_feature]),
    ).get_saved_summary(locations)

    refs_by_id = {ref.id: ref for ref in summary.alert_refs}
    assert [ref.id for ref in refs_by_id["test-same"].affected_locations] == [1]
    assert refs_by_id["test-same"].affected_locations[0].match_type == "same"
    assert [ref.id for ref in refs_by_id["test-ugc"].affected_locations] == [2]
    assert refs_by_id["test-ugc"].affected_locations[0].match_type == "ugc"


def test_saved_summary_blank_test_alert_does_not_match_every_saved_location() -> None:
    locations = [_location(id=1, zip_code="49002"), _location(id=2, zip_code="49015", county_zone="MIC025")]
    blank_test_feature = _feature("blank-test-warning", event="TEST: Tornado Warning")

    summary = _service(FakeProvider(), FakeTestAlertLoader([blank_test_feature])).get_saved_summary(locations)

    assert summary.total == 0
    assert summary.affected_location_count == 0


def test_saved_summary_no_target_test_zone_alert_still_matches_saved_zone() -> None:
    location = _location(county_zone="MIC077", forecast_zone="MIZ072")
    zone_feature = _feature(
        "test-zone-no-target",
        event="TEST: Winter Storm Warning",
        affected_zones=["https://api.weather.gov/zones/forecast/MIZ072"],
        geocode={"UGC": ["MIZ072"]},
    )

    summary = _service(FakeProvider(), FakeTestAlertLoader([zone_feature])).get_saved_summary([location])

    assert summary.total == 1
    assert summary.alert_refs[0].id == "test-zone-no-target"
    assert summary.alert_refs[0].affected_locations[0].match_type == "zone"


def test_saved_summary_returns_partial_with_test_alerts_when_nws_zone_fails() -> None:
    location = _location(zip_code="49002")
    test_feature = _feature(
        "test-zip-warning",
        event="TEST: Tornado Warning",
        parameters={"zipCode": ["49002"]},
    )
    provider = FakeProvider(failing_zones={"MIC077"})

    summary = _service(provider, FakeTestAlertLoader([test_feature])).get_saved_summary([location])

    assert summary.total == 1
    assert summary.partial is True
    assert summary.errors
    assert summary.alert_refs[0].source == "test"


def test_saved_summary_uses_current_fallback_for_locations_without_zone_metadata() -> None:
    location = _location(county_zone=None, forecast_zone=None, fire_weather_zone=None)
    provider = FakeProvider(
        fallback_payloads={
            location.id: [
                _feature(
                    "fallback-same",
                    event="Severe Thunderstorm Warning",
                    geocode={"SAME": ["026077"]},
                )
            ]
        }
    )

    summary = _service(provider, FakeTestAlertLoader()).get_saved_summary([location])

    assert provider.fallback_calls == [location.id]
    assert summary.total == 1
    assert summary.alert_refs[0].affected_locations[0].match_type == "same"


def test_saved_summary_cache_uses_location_and_test_alert_file_fingerprint() -> None:
    location = _location()
    provider = FakeProvider(zone_payloads={"MIC077": [_feature("warning", affected_zones=["MIC077"])]})
    loader = FakeTestAlertLoader()
    service = _service(provider, loader)

    first = service.get_saved_summary([location])
    second = service.get_saved_summary([location])
    loader.mtime = 456.0
    third = service.get_saved_summary([location])

    assert first.total == second.total == third.total == 1
    assert provider.zone_calls == ["MIC077", "MIZ072", "MIC077", "MIZ072"]


def test_saved_summary_unit_tests_do_not_modify_canonical_test_alert_fixture() -> None:
    fixture_path = Path("test/alerts_test.json")
    before = fixture_path.read_bytes()
    provider = FakeProvider()

    _service(provider, FakeTestAlertLoader()).get_saved_summary([_location()])

    assert fixture_path.read_bytes() == before
