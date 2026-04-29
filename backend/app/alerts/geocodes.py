import re
from dataclasses import dataclass, field
from typing import Any


SAME_PATTERN = re.compile(r"^\d{6}$")
UGC_PATTERN = re.compile(r"^([A-Z]{2})([CZ])(\d{3}|ALL)$")


@dataclass(frozen=True)
class SameCode:
    original: str
    valid: bool
    state_fips: str | None
    county_fips: str | None
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UgcCode:
    original: str
    valid: bool
    prefix: str | None
    type: str | None
    code: str | None
    kind: str | None
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedGeocodes:
    same: list[SameCode]
    ugc: list[UgcCode]
    raw: dict[str, Any]


def parse_same(value: str) -> SameCode:
    original = str(value)
    errors: list[str] = []

    if not SAME_PATTERN.fullmatch(original):
        errors.append("SAME code must be exactly six digits.")
        return SameCode(
            original=original,
            valid=False,
            state_fips=None,
            county_fips=None,
            errors=errors,
        )

    return SameCode(
        original=original,
        valid=True,
        state_fips=original[1:3],
        county_fips=original[3:6],
        errors=[],
    )


def parse_ugc(value: str) -> UgcCode:
    original = str(value)
    normalized = original.strip().upper()
    errors: list[str] = []

    match = UGC_PATTERN.fullmatch(normalized)
    if match is None:
        errors.append("UGC code must match prefix + C/Z + three digits or ALL.")
        return UgcCode(
            original=original,
            valid=False,
            prefix=None,
            type=None,
            code=None,
            kind=None,
            errors=errors,
        )

    prefix, ugc_type, code = match.groups()
    return UgcCode(
        original=original,
        valid=True,
        prefix=prefix,
        type=ugc_type,
        code=code,
        kind="county" if ugc_type == "C" else "zone",
        errors=[],
    )


def normalize_geocodes(raw_geocode: dict[str, Any]) -> NormalizedGeocodes:
    raw = dict(raw_geocode) if isinstance(raw_geocode, dict) else {}
    return NormalizedGeocodes(
        same=[parse_same(value) for value in _as_list(raw.get("SAME"))],
        ugc=[parse_ugc(value) for value in _as_list(raw.get("UGC"))],
        raw=raw,
    )


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

