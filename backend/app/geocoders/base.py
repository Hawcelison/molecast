from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Mapping, Protocol


class AddressGeocoderError(RuntimeError):
    """Base error for address geocoder failures."""


class AddressGeocoderTimeout(AddressGeocoderError):
    """Raised when an address provider times out."""


class AddressGeocoderUnavailable(AddressGeocoderError):
    """Raised when an address provider cannot be reached or returns an HTTP error."""


class AddressGeocoderBadResponse(AddressGeocoderError):
    """Raised when an address provider response cannot be parsed safely."""


class AddressGeocoderValidationError(ValueError):
    """Raised when an address request is invalid before provider I/O."""


@dataclass(frozen=True)
class AddressGeocodeRequest:
    address: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    limit: int = 5


@dataclass(frozen=True)
class AddressGeocodeCandidate:
    ref: str
    matched_address: str
    display_label: str
    latitude: float
    longitude: float
    city: str | None
    state: str | None
    zip_code: str | None
    source: str
    accuracy: str
    match_quality: str
    score: float | None = None
    warnings: list[str] = field(default_factory=list)
    raw: Mapping[str, Any] | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class AddressGeocodeResponse:
    query: str
    provider: str
    count: int
    candidates: list[AddressGeocodeCandidate]
    attribution: str | None = None


class AddressGeocoder(Protocol):
    provider_name: str
    attribution: str | None

    def geocode(self, request: AddressGeocodeRequest) -> AddressGeocodeResponse:
        ...


AddressSearchType = Literal["onelineaddress", "address"]


@dataclass(frozen=True)
class NormalizedAddressGeocodeRequest:
    query: str
    search_type: AddressSearchType
    address: str | None
    street: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    limit: int


def normalize_address_request(
    request: AddressGeocodeRequest,
    *,
    default_limit: int = 5,
    max_limit: int = 10,
) -> NormalizedAddressGeocodeRequest:
    address = _clean(request.address)
    street = _clean(request.street)
    city = _clean(request.city)
    state = _clean(request.state)
    zip_code = normalize_zip_code(request.zip_code)
    limit = normalize_candidate_limit(request.limit, default_limit, max_limit)

    if address:
        if not has_structure_number_and_street_name(address):
            raise AddressGeocoderValidationError(
                "Address must include a structure number and street name."
            )
        return NormalizedAddressGeocodeRequest(
            query=address,
            search_type="onelineaddress",
            address=address,
            street=None,
            city=None,
            state=None,
            zip_code=None,
            limit=limit,
        )

    if not street:
        raise AddressGeocoderValidationError("Address or street is required.")
    if not has_structure_number_and_street_name(street):
        raise AddressGeocoderValidationError(
            "Street must include a structure number and street name."
        )

    normalized_state = state.upper() if state else None
    if normalized_state and not re.fullmatch(r"[A-Z]{2}", normalized_state):
        raise AddressGeocoderValidationError("State must be a two-letter abbreviation.")

    return NormalizedAddressGeocodeRequest(
        query=format_parsed_query(street, city, normalized_state, zip_code),
        search_type="address",
        address=None,
        street=street,
        city=city,
        state=normalized_state,
        zip_code=zip_code,
        limit=limit,
    )


def normalize_response_limit(
    response: AddressGeocodeResponse,
    *,
    limit: int,
) -> AddressGeocodeResponse:
    candidates = response.candidates[:limit]
    return replace(response, count=len(candidates), candidates=candidates)


def normalize_candidate_limit(limit: int | None, default_limit: int, max_limit: int) -> int:
    if limit is None:
        return default_limit
    try:
        parsed_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise AddressGeocoderValidationError("Candidate limit must be an integer.") from exc
    if parsed_limit < 1:
        return default_limit
    return min(parsed_limit, max_limit)


def normalize_zip_code(value: str | None) -> str | None:
    zip_code = _clean(value)
    if not zip_code:
        return None
    if not re.fullmatch(r"\d{5}(-\d{4})?", zip_code):
        raise AddressGeocoderValidationError("ZIP code must be 5 digits or ZIP+4.")
    return zip_code


def has_structure_number_and_street_name(value: str) -> bool:
    return bool(re.search(r"\d", value) and re.search(r"[A-Za-z]", value))


def format_parsed_query(
    street: str,
    city: str | None,
    state: str | None,
    zip_code: str | None,
) -> str:
    locality = " ".join(part for part in (city, state, zip_code) if part)
    return ", ".join(part for part in (street, locality) if part)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip())
    return cleaned or None
