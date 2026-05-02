from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LocationSearchSuggestion(BaseModel):
    ref: str
    kind: Literal["zip", "city", "address"]
    label: str
    zip: str | None = None
    city: str
    state: str
    county: str | None = None
    latitude: float
    longitude: float
    default_zoom: int = Field(ge=0, le=22)
    accuracy: Literal["zip_centroid", "city_representative", "address_range_interpolated"]
    source: Literal["local", "census"] = "local"


class LocationSearchResponse(BaseModel):
    query: str
    count: int
    results: list[LocationSearchSuggestion]


class NwsPointPreviewRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class NwsPointPreviewResponse(BaseModel):
    latitude: float
    longitude: float
    nws_office: str | None = None
    nws_office_code: str | None = None
    nws_office_name: str | None = None
    nws_grid_x: int | None = None
    nws_grid_y: int | None = None
    forecast_zone: str | None = None
    county_zone: str | None = None
    fire_weather_zone: str | None = None
    timezone: str | None = None
    status: Literal["ok"] = "ok"
    updated_at: datetime
