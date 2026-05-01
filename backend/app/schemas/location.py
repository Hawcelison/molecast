from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LocationBase(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=2, max_length=2)
    county: str = Field(min_length=1, max_length=80)
    zip_code: str = Field(pattern=r"^$|^\d{5}(-\d{4})?$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    default_zoom: int = Field(default=9, ge=0, le=22)


class LocationCreate(LocationBase):
    is_primary: bool = False


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
    state: str | None = Field(default=None, min_length=2, max_length=2)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    default_zoom: int | None = Field(default=None, ge=0, le=22)

    @model_validator(mode="after")
    def normalize_state(self):
        if self.state:
            self.state = self.state.upper()
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
    zip_code: str
    city: str
    state: str
    county: str
    latitude: float
    longitude: float
    default_zoom: int = Field(default=9, ge=0, le=22)
