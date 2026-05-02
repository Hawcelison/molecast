from __future__ import annotations

from functools import lru_cache

from app.config import Settings, settings
from app.geocoders.base import (
    AddressGeocodeRequest,
    AddressGeocodeResponse,
    AddressGeocoder,
    AddressGeocoderValidationError,
    normalize_address_request,
    normalize_response_limit,
)
from app.geocoders.census import CensusAddressGeocoder


DEFAULT_ADDRESS_CANDIDATE_LIMIT = 5
MAX_ADDRESS_CANDIDATE_LIMIT = 10


class AddressLookupService:
    def __init__(
        self,
        app_settings: Settings = settings,
        providers: dict[str, AddressGeocoder] | None = None,
    ) -> None:
        self.settings = app_settings
        self.providers = providers or {
            CensusAddressGeocoder.provider_name: CensusAddressGeocoder(app_settings),
        }

    def lookup(self, request: AddressGeocodeRequest) -> AddressGeocodeResponse:
        normalized_request = normalize_address_request(
            request,
            default_limit=DEFAULT_ADDRESS_CANDIDATE_LIMIT,
            max_limit=MAX_ADDRESS_CANDIDATE_LIMIT,
        )
        provider = self._provider_for(self.settings.geocoder_provider)
        response = provider.geocode(
            AddressGeocodeRequest(
                address=normalized_request.address,
                street=normalized_request.street,
                city=normalized_request.city,
                state=normalized_request.state,
                zip_code=normalized_request.zip_code,
                limit=normalized_request.limit,
            )
        )
        return normalize_response_limit(response, limit=normalized_request.limit)

    def _provider_for(self, provider_name: str) -> AddressGeocoder:
        normalized_name = (provider_name or "").strip().lower()
        provider = self.providers.get(normalized_name)
        if provider is None:
            raise AddressGeocoderValidationError(
                f"Unsupported address geocoder provider: {provider_name}."
            )
        return provider


@lru_cache
def get_address_lookup_service() -> AddressLookupService:
    return AddressLookupService(settings)
