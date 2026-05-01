from typing import Literal

from pydantic import BaseModel, Field


class LocationSearchSuggestion(BaseModel):
    ref: str
    kind: Literal["zip", "city"]
    label: str
    zip: str | None = None
    city: str
    state: str
    county: str | None = None
    latitude: float
    longitude: float
    default_zoom: int = Field(ge=0, le=22)
    accuracy: Literal["zip_centroid", "city_representative"]
    source: Literal["local"] = "local"


class LocationSearchResponse(BaseModel):
    query: str
    count: int
    results: list[LocationSearchSuggestion]
