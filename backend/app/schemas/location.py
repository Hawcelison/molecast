from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LocationBase(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=2, max_length=2)
    county: str = Field(min_length=1, max_length=80)
    zip_code: str = Field(pattern=r"^\d{5}(-\d{4})?$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationCreate(LocationBase):
    is_primary: bool = False


class ActiveLocationUpdate(BaseModel):
    location_id: int = Field(gt=0)


class LocationRead(LocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_primary: bool
    created_at: datetime
    updated_at: datetime


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
