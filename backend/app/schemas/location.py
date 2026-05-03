from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _trim_zip_code(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return value.strip()


class LocationBase(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=2, max_length=2)
    county: str = Field(min_length=1, max_length=80)
    county_fips: str | None = Field(default=None, min_length=1, max_length=10)
    zip_code: str = Field(pattern=r"^$|^\d{5}(-\d{4})?$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    default_zoom: int = Field(default=9, ge=0, le=22)
    source_method: str | None = Field(default="manual", min_length=1, max_length=30)

    @field_validator("zip_code", mode="before")
    @classmethod
    def trim_zip_code(cls, value: str) -> str:
        return _trim_zip_code(value) or ""

    @model_validator(mode="after")
    def normalize_location_base(self):
        self.state = self.state.upper()
        if self.source_method:
            self.source_method = self.source_method.strip().lower()
        return self


class LocationCreate(LocationBase):
    is_primary: bool = False
    activate: bool = False


class LocationUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    city: str | None = Field(default=None, min_length=1, max_length=80)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    county: str | None = Field(default=None, min_length=1, max_length=80)
    county_fips: str | None = Field(default=None, min_length=1, max_length=10)
    zip_code: str | None = Field(default=None, pattern=r"^$|^\d{5}(-\d{4})?$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    default_zoom: int | None = Field(default=None, ge=0, le=22)
    source_method: str | None = Field(default=None, min_length=1, max_length=30)
    is_primary: bool | None = None

    @field_validator("zip_code", mode="before")
    @classmethod
    def trim_zip_code(cls, value: str | None) -> str | None:
        return _trim_zip_code(value)

    @model_validator(mode="after")
    def normalize_location_update(self):
        if self.state:
            self.state = self.state.upper()
        if self.source_method:
            self.source_method = self.source_method.strip().lower()
        return self


class ActiveLocationUpdate(BaseModel):
    location_id: int = Field(gt=0)


class ActiveLocationDirectUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: str | None = Field(default=None, min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    zip_code: str | None = Field(default=None, pattern=r"^\d{5}(-\d{4})?$")
    city: str | None = Field(default=None, min_length=1, max_length=80)
    county: str | None = Field(default=None, min_length=1, max_length=80)
    county_fips: str | None = Field(default=None, min_length=1, max_length=10)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    default_zoom: int | None = Field(default=None, ge=0, le=22)
    source_method: str | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("zip_code", mode="before")
    @classmethod
    def trim_zip_code(cls, value: str | None) -> str | None:
        return _trim_zip_code(value)

    @model_validator(mode="after")
    def normalize_state(self):
        if self.state:
            self.state = self.state.upper()
        if self.source_method:
            self.source_method = self.source_method.strip().lower()
        return self


class LocationRead(LocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nws_office: str | None = None
    nws_grid_x: int | None = None
    nws_grid_y: int | None = None
    forecast_zone: str | None = None
    county_zone: str | None = None
    fire_weather_zone: str | None = None
    nws_points_updated_at: datetime | None = None
    source_method: str | None = None
    last_used_at: datetime | None = None
    is_primary: bool
    using_default: bool = False
    created_at: datetime
    updated_at: datetime


class LocationStatus(BaseModel):
    active_location: LocationRead
    using_default: bool
    nws_metadata_status: str
    warning: str | None = None


class LocationDeleteResponse(BaseModel):
    deleted: bool
    active_location: LocationRead


class ZipLookupResponse(BaseModel):
    zip: str
    zip_code: str
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
