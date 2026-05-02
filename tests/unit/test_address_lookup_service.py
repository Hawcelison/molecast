from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.geocoders.base import (
    AddressGeocodeCandidate,
    AddressGeocodeRequest,
    AddressGeocodeResponse,
    AddressGeocoderValidationError,
)
from app.services import location_service
from app.services.address_lookup_service import AddressLookupService


class FakeGeocoder:
    provider_name = "fake"
    attribution = "Fake attribution"

    def __init__(self, count: int = 1) -> None:
        self.count = count
        self.calls: list[AddressGeocodeRequest] = []

    def geocode(self, request: AddressGeocodeRequest) -> AddressGeocodeResponse:
        self.calls.append(request)
        candidates = [
            AddressGeocodeCandidate(
                ref=f"fake:{index}",
                matched_address=f"{index} MAIN ST",
                display_label=f"City {index}, MI",
                latitude=42.0 + index,
                longitude=-85.0 - index,
                city=f"City {index}",
                state="MI",
                zip_code="49002",
                source="fake",
                accuracy="address_range_interpolated",
                match_quality="matched",
                score=None,
                warnings=[],
            )
            for index in range(self.count)
        ]
        return AddressGeocodeResponse(
            query=request.address or request.street or "",
            provider=self.provider_name,
            count=len(candidates),
            candidates=candidates,
            attribution=self.attribution,
        )


def _settings(provider: str = "fake"):
    return SimpleNamespace(geocoder_provider=provider)


def test_service_selects_configured_provider_and_normalizes_request() -> None:
    provider = FakeGeocoder()
    service = AddressLookupService(_settings(), providers={"fake": provider})

    response = service.lookup(
        AddressGeocodeRequest(
            street="123 Main St",
            city="Portage",
            state="mi",
            zip_code="49002",
            limit=5,
        )
    )

    assert response.provider == "fake"
    assert response.attribution == "Fake attribution"
    assert provider.calls == [
        AddressGeocodeRequest(
            address=None,
            street="123 Main St",
            city="Portage",
            state="MI",
            zip_code="49002",
            limit=5,
        )
    ]


def test_service_enforces_default_and_max_candidate_limit() -> None:
    provider = FakeGeocoder(count=12)
    service = AddressLookupService(_settings(), providers={"fake": provider})

    default_response = service.lookup(AddressGeocodeRequest(address="123 Main St, Portage, MI"))
    capped_response = service.lookup(
        AddressGeocodeRequest(address="123 Main St, Portage, MI", limit=999)
    )

    assert default_response.count == 5
    assert len(default_response.candidates) == 5
    assert capped_response.count == 10
    assert len(capped_response.candidates) == 10
    assert provider.calls[0].limit == 5
    assert provider.calls[1].limit == 10


def test_service_rejects_unknown_provider() -> None:
    service = AddressLookupService(_settings("unknown"), providers={"fake": FakeGeocoder()})

    with pytest.raises(AddressGeocoderValidationError):
        service.lookup(AddressGeocodeRequest(address="123 Main St, Portage, MI"))


def test_service_rejects_invalid_request_before_provider_call() -> None:
    provider = FakeGeocoder()
    service = AddressLookupService(_settings(), providers={"fake": provider})

    with pytest.raises(AddressGeocoderValidationError):
        service.lookup(AddressGeocodeRequest(address="Portage MI"))

    assert provider.calls == []


def test_service_does_not_use_active_location_persistence(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("active location persistence should not be used")

    monkeypatch.setattr(location_service, "set_active_location", fail_if_called)
    monkeypatch.setattr(location_service, "set_active_location_from_payload", fail_if_called)
    provider = FakeGeocoder()
    service = AddressLookupService(_settings(), providers={"fake": provider})

    response = service.lookup(AddressGeocodeRequest(address="123 Main St, Portage, MI"))

    assert response.count == 1
    assert provider.calls
