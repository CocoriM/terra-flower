from typing import List, Optional

from pydantic import BaseModel


class PlantSummary(BaseModel):
    id: str
    common_name: str
    common_name_zh: Optional[str] = None
    scientific_name: str
    plant_type: str
    family: Optional[str] = None
    hero_image_url: Optional[str] = None
    distribution_count: int = 0


class PlantListResponse(BaseModel):
    plants: List[PlantSummary]
    page: int
    per_page: int
    total: int


class PlantDetail(BaseModel):
    id: str
    common_name: str
    common_name_zh: Optional[str] = None
    scientific_name: str
    plant_type: str
    family: Optional[str] = None
    genus: Optional[str] = None
    description: Optional[str] = None
    habitat: Optional[str] = None
    bloom_season: Optional[str] = None
    hero_image_url: Optional[str] = None
    hero_image_attribution: Optional[str] = None
    distribution_count: int = 0
    images: List["PlantImageOut"] = []


class PlantImageOut(BaseModel):
    id: str
    image_url: str
    thumbnail_url: Optional[str] = None
    image_type: str
    attribution: Optional[str] = None
    source: Optional[str] = None


class DistributionPoint(BaseModel):
    lat: float
    lng: float
    elevation: Optional[float] = None
    country: Optional[str] = None


class DistributionResponse(BaseModel):
    plant_id: str
    distributions: List[DistributionPoint]


class GlobeMarker(BaseModel):
    plant_id: str
    common_name: str
    plant_type: str
    lat: float
    lng: float
    elevation: float = 0
    occurrence_count: int


class GlobeMarkersResponse(BaseModel):
    markers: List[GlobeMarker]


class GalleryItem(BaseModel):
    id: str
    image_url: str
    thumbnail_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    submitted_at: Optional[str] = None


class GalleryResponse(BaseModel):
    items: List[GalleryItem]
    page: int
    per_page: int
