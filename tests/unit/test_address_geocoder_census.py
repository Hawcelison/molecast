from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from app.geocoders import census as census_module
from app.geocoders.base import (
    AddressGeocodeRequest,
    AddressGeocoderBadResponse,
    AddressGeocoderTimeout,
    AddressGeocoderUnavailable,
    AddressGeocoderValidationError,
)
from app.geocoders.census import CENSUS_ATTRIBUTION, CensusAddressGeocoder


def _settings():
    return SimpleNamespace(
        census_geocoder_base_url="https://geocoding.geo.census.gov/geocoder",
        census_geocoder_benchmark="Public_AR_Current",
        geocoder_timeout_seconds=5,
        geocoder_user_agent="Molecast test",
    )


class FakeResponse:
    def __init__(self, payload: dict | bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def _census_payload(matches: list[dict]) -> dict:
    return {
        "result": {
            "addressMatches": matches,
        }
    }


def _match(
    *,
    matched_address: str = "4600 SILVER HILL RD, WASHINGTON, DC, 20233",
    longitude: float = -76.927487,
    latitude: float = 38.846016,
    tiger_line_id: str = "76355984",
    side: str = "L",
    city: str = "WASHINGTON",
    state: str = "DC",
    zip_code: str = "20233",
) -> dict:
    return {
        "matchedAddress": matched_address,
        "coordinates": {
            "x": longitude,
            "y": latitude,
        },
        "addressComponents": {
            "city": city,
            "state": state,
            "zip": zip_code,
        },
        "tigerLine": {
            "tigerLineId": tiger_line_id,
            "side": side,
        },
    }


def test_one_line_successful_census_response_parsed_correctly(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["user_agent"] = request.get_header("User-agent")
        return FakeResponse(_census_payload([_match()]))

    monkeypatch.setattr(census_module, "urlopen", fake_urlopen)
    provider = CensusAddressGeocoder(_settings())

    response = provider.geocode(
        AddressGeocodeRequest(address="4600 Silver Hill Rd, Washington, DC 20233")
    )

    parsed_url = urlparse(captured["url"])
    query = parse_qs(parsed_url.query)
    assert parsed_url.path.endswith("/locations/onelineaddress")
    assert query["address"] == ["4600 Silver Hill Rd, Washington, DC 20233"]
    assert query["benchmark"] == ["Public_AR_Current"]
    assert query["format"] == ["json"]
    assert query["returntype"] == ["locations"]
    assert captured["timeout"] == 5
    assert captured["user_agent"] == "Molecast test"
    assert response.provider == "census"
    assert response.attribution == CENSUS_ATTRIBUTION
    assert response.count == 1

    candidate = response.candidates[0]
    assert candidate.ref == "census:76355984:L:0"
    assert candidate.matched_address == "4600 SILVER HILL RD, WASHINGTON, DC, 20233"
    assert candidate.display_label == "WASHINGTON, DC 20233"
    assert candidate.latitude == 38.846016
    assert candidate.longitude == -76.927487
    assert candidate.city == "WASHINGTON"
    assert candidate.state == "DC"
    assert candidate.zip_code == "20233"
    assert candidate.source == "census"
    assert candidate.accuracy == "address_range_interpolated"
    assert candidate.match_quality == "matched"
    assert candidate.score is None
    assert candidate.warnings == ["Address point may be approximate."]


def test_parsed_address_successful_response_uses_address_search(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse(_census_payload([_match(city="PORTAGE", state="MI", zip_code="49002")]))

    monkeypatch.setattr(census_module, "urlopen", fake_urlopen)
    provider = CensusAddressGeocoder(_settings())

    response = provider.geocode(
        AddressGeocodeRequest(
            street="123 Main St",
            city="Portage",
            state="mi",
            zip_code="49002",
        )
    )

    parsed_url = urlparse(captured["url"])
    query = parse_qs(parsed_url.query)
    assert parsed_url.path.endswith("/locations/address")
    assert query["street"] == ["123 Main St"]
    assert query["city"] == ["Portage"]
    assert query["state"] == ["MI"]
    assert query["zip"] == ["49002"]
    assert response.query == "123 Main St, Portage MI 49002"
    assert response.candidates[0].display_label == "PORTAGE, MI 49002"


def test_no_match_returns_empty_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        census_module,
        "urlopen",
        lambda request, timeout: FakeResponse(_census_payload([])),
    )
    provider = CensusAddressGeocoder(_settings())

    response = provider.geocode(AddressGeocodeRequest(address="123 Main St, Portage, MI"))

    assert response.count == 0
    assert response.candidates == []


def test_multiple_candidates_are_preserved(monkeypatch) -> None:
    matches = [
        _match(tiger_line_id="1", matched_address="123 MAIN ST, A, MI, 49002"),
        _match(tiger_line_id="2", matched_address="123 MAIN ST, B, MI, 49002"),
    ]
    monkeypatch.setattr(
        census_module,
        "urlopen",
        lambda request, timeout: FakeResponse(_census_payload(matches)),
    )
    provider = CensusAddressGeocoder(_settings())

    response = provider.geocode(AddressGeocodeRequest(address="123 Main St, MI"))

    assert [candidate.ref for candidate in response.candidates] == [
        "census:1:L:0",
        "census:2:L:1",
    ]
    assert [candidate.matched_address for candidate in response.candidates] == [
        "123 MAIN ST, A, MI, 49002",
        "123 MAIN ST, B, MI, 49002",
    ]


def test_timeout_maps_to_geocoder_timeout(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(census_module, "urlopen", fake_urlopen)
    provider = CensusAddressGeocoder(_settings())

    with pytest.raises(AddressGeocoderTimeout):
        provider.geocode(AddressGeocodeRequest(address="123 Main St, Portage, MI"))


def test_http_error_maps_to_geocoder_unavailable(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 503, "unavailable", hdrs=None, fp=None)

    monkeypatch.setattr(census_module, "urlopen", fake_urlopen)
    provider = CensusAddressGeocoder(_settings())

    with pytest.raises(AddressGeocoderUnavailable):
        provider.geocode(AddressGeocodeRequest(address="123 Main St, Portage, MI"))


def test_bad_json_maps_to_bad_response(monkeypatch) -> None:
    monkeypatch.setattr(
        census_module,
        "urlopen",
        lambda request, timeout: FakeResponse(b"{not json"),
    )
    provider = CensusAddressGeocoder(_settings())

    with pytest.raises(AddressGeocoderBadResponse):
        provider.geocode(AddressGeocodeRequest(address="123 Main St, Portage, MI"))


def test_invalid_request_rejected_before_network_call(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise AssertionError("network should not be called")

    monkeypatch.setattr(census_module, "urlopen", fake_urlopen)
    provider = CensusAddressGeocoder(_settings())

    with pytest.raises(AddressGeocoderValidationError):
        provider.geocode(AddressGeocodeRequest(address="Portage MI"))
