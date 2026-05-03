import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from app.config import settings
from app.repositories.location_lookup_repository import LocationLookupRepository


ZIP_CODE_PATTERN = re.compile(r"^\d{5}(-\d{4})?$")


class InvalidZipCodeError(ValueError):
    pass


class ZipCodeLookupResult(BaseModel):
    zip_code: str = Field(pattern=r"^\d{5}$")
    city: str | None = None
    state: str | None = None
    county: str | None = None
    county_fips: str | None = None
    latitude: float
    longitude: float
    default_zoom: int = Field(default=9, ge=0, le=22)
    source: str | None = None
    source_year: str | None = None
    source_version: str | None = None
    dataset_version: str | None = None
    imported_at: str | None = None
    location_type: str | None = None
    is_zcta: bool = False
    confidence: str | None = None


class ZipCodeProvider(Protocol):
    def lookup(self, zip_code: str) -> ZipCodeLookupResult | None:
        pass


class SQLiteZipCodeProvider:
    def __init__(self, db_path: Path) -> None:
        self.repository = LocationLookupRepository(db_path)

    def lookup(self, zip_code: str) -> ZipCodeLookupResult | None:
        record = self.repository.lookup_zip(to_zip_lookup_key(zip_code))
        if record is None:
            return None

        return ZipCodeLookupResult(
            zip_code=record.zip_code,
            city=record.primary_city,
            state=record.state,
            county=record.county,
            county_fips=record.county_fips,
            latitude=record.latitude,
            longitude=record.longitude,
            default_zoom=record.default_zoom,
            source=record.source,
            source_year=record.source_year,
            source_version=record.source_version,
            dataset_version=record.dataset_version,
            imported_at=record.imported_at,
            location_type=record.location_type,
            is_zcta=record.is_zcta,
            confidence=record.confidence,
        )


class ZipLookupService:
    def __init__(self, provider: ZipCodeProvider) -> None:
        self.provider = provider

    def lookup(self, zip_code: str) -> ZipCodeLookupResult | None:
        return self.provider.lookup(zip_code)


def validate_zip_code(zip_code: str) -> str:
    normalized_zip_code = zip_code.strip()
    if not ZIP_CODE_PATTERN.fullmatch(normalized_zip_code):
        raise InvalidZipCodeError("ZIP code must be 5 digits or ZIP+4 format.")
    return normalized_zip_code


def to_zip_lookup_key(zip_code: str) -> str:
    return validate_zip_code(zip_code)[:5]


@lru_cache
def get_zip_lookup_service() -> ZipLookupService:
    db_path = settings.app_dir / "data" / "location_lookup.sqlite3"
    return ZipLookupService(SQLiteZipCodeProvider(db_path))
