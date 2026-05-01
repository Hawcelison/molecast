import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError

from app.config import settings


ZIP_CODE_PATTERN = re.compile(r"^\d{5}(-\d{4})?$")


class InvalidZipCodeError(ValueError):
    pass


class ZipCodeLookupResult(BaseModel):
    zip_code: str = Field(pattern=r"^\d{5}$")
    city: str
    state: str
    county: str
    latitude: float
    longitude: float
    default_zoom: int = Field(default=9, ge=0, le=22)


class ZipCodeProvider(Protocol):
    def lookup(self, zip_code: str) -> ZipCodeLookupResult | None:
        pass


class JsonZipCodeProvider:
    def __init__(self, data_file: Path) -> None:
        self.data_file = data_file
        self._zip_codes = self._load_zip_codes()

    def lookup(self, zip_code: str) -> ZipCodeLookupResult | None:
        return self._zip_codes.get(to_zip_lookup_key(zip_code))

    def _load_zip_codes(self) -> dict[str, ZipCodeLookupResult]:
        if not self.data_file.exists():
            return {}

        with self.data_file.open(encoding="utf-8") as zip_code_file:
            raw_records = json.load(zip_code_file)

        zip_codes: dict[str, ZipCodeLookupResult] = {}
        for raw_record in raw_records:
            try:
                record = ZipCodeLookupResult.model_validate(raw_record)
            except ValidationError:
                continue
            zip_codes[record.zip_code] = record
        return zip_codes


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
    data_file = settings.app_dir / "data" / "zip_codes.json"
    return ZipLookupService(JsonZipCodeProvider(data_file))
