from typing import List, Optional

from pydantic import BaseModel


class AIResultItem(BaseModel):
    scientific_name: str
    common_name: Optional[str] = None
    confidence: float
    matched_plant_id: Optional[str] = None
    matched_plant_image: Optional[str] = None


class UploadResponse(BaseModel):
    id: str
    image_url: str
    thumbnail_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    elevation_meters: Optional[float] = None
    location_text: Optional[str] = None
    ai_best_match_name: Optional[str] = None
    ai_best_match_score: Optional[float] = None
    ai_top_results: Optional[List[AIResultItem]] = None
    ai_project_used: Optional[str] = None
    confirmed_plant_id: Optional[str] = None
    user_confirmed: bool = False
    ai_status: str
    moderation_status: str
    moderation_reason: Optional[str] = None
    submitted_at: str

    model_config = {"from_attributes": True}


class ConfirmRequest(BaseModel):
    confirmed_plant_id: str


class ModerationAction(BaseModel):
    reason: Optional[str] = None
