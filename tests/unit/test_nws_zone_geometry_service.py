from types import SimpleNamespace

from app.services.nws_zone_geometry_service import (
    NwsZoneGeometryFetchError,
    NwsZoneGeometryService,
    combine_zone_geometries,
    extract_zone_geometry,
)


def _polygon(offset: int = 0) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [-85.7 + offset, 42.1],
                [-85.4 + offset, 42.1],
                [-85.4 + offset, 42.3],
                [-85.7 + offset, 42.1],
            ]
        ],
    }


def _multipolygon() -> dict:
    return {
        "type": "MultiPolygon",
        "coordinates": [
            _polygon(0)["coordinates"],
            _polygon(1)["coordinates"],
        ],
    }


class FakeZoneGeometryService(NwsZoneGeometryService):
    def __init__(self, payloads: dict[str, dict] | None = None, failures: set[str] | None = None) -> None:
        super().__init__(
            SimpleNamespace(
                nws_active_alerts_url="https://api.weather.gov/alerts/active",
                nws_user_agent="Molecast test",
            ),
            ttl_seconds=60,
        )
        self.payloads = payloads or {}
        self.failures = failures or set()
        self.fetches: list[str] = []

    def _fetch_zone_payload(self, zone_url: str) -> dict:
        self.fetches.append(zone_url)
        if zone_url in self.failures:
            raise NwsZoneGeometryFetchError("zone failed")
        return self.payloads.get(zone_url, {"geometry": None})


def test_fetch_parse_polygon_zone_geometry() -> None:
    zone_url = "https://api.weather.gov/zones/forecast/MIZ072"
    service = FakeZoneGeometryService({zone_url: {"type": "Feature", "geometry": _polygon()}})

    geometry = service.resolve_zone(zone_url)

    assert geometry == _polygon()
    assert service.fetches == [zone_url]


def test_fetch_parse_multipolygon_zone_geometry() -> None:
    zone_url = "https://api.weather.gov/zones/forecast/MIZ072"
    service = FakeZoneGeometryService({zone_url: {"type": "Feature", "geometry": _multipolygon()}})

    geometry = service.resolve_zone(zone_url)

    assert geometry == _multipolygon()


def test_missing_geometry_returns_none_safely() -> None:
    assert extract_zone_geometry({"type": "Feature", "geometry": None}) is None
    assert extract_zone_geometry({"type": "Feature", "geometry": {"type": "LineString", "coordinates": []}}) is None


def test_failed_fetch_does_not_crash() -> None:
    zone_url = "https://api.weather.gov/zones/forecast/MIZ072"
    service = FakeZoneGeometryService(failures={zone_url})

    assert service.resolve_zone(zone_url) is None


def test_canonical_zone_id_builds_zone_url_and_uses_cache() -> None:
    zone_url = "https://api.weather.gov/zones/forecast/MIZ072"
    service = FakeZoneGeometryService({zone_url: {"type": "Feature", "geometry": _polygon()}})

    assert service.resolve_zone("MIZ072") == _polygon()
    assert service.resolve_zone("MIZ072") == _polygon()
    assert service.fetches == [zone_url]


def test_combine_zone_geometries_keeps_single_polygon() -> None:
    assert combine_zone_geometries([_polygon()]) == _polygon()


def test_combine_zone_geometries_flattens_to_multipolygon() -> None:
    combined = combine_zone_geometries([_polygon(), _multipolygon()])

    assert combined is not None
    assert combined["type"] == "MultiPolygon"
    assert len(combined["coordinates"]) == 3
