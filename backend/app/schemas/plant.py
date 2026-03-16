from typing import List, Optional

from pydantic import BaseModel


class PlantSummary(BaseModel):
    trefle_id: int
    common_name: Optional[str]
    scientific_name: str
    plant_type: str
    family: Optional[str]
    image_url: Optional[str]
    native_regions: List[str]


class PlantListResponse(BaseModel):
    plants: List[PlantSummary]
    page: int
    per_page: int
    total: int


class OccurrencePoint(BaseModel):
    lat: float
    lng: float
    country: Optional[str]
    year: Optional[int]


class OccurrenceResponse(BaseModel):
    trefle_id: int
    scientific_name: str
    occurrences: List[OccurrencePoint]
    total_fetched: int
