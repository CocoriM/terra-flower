from typing import Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    id: str
    trefle_plant_id: int
    plant_common_name: Optional[str]
    plant_scientific_name: str
    plant_type: Optional[str]
    image_url: str
    thumbnail_url: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    location_text: Optional[str]
    ai_predicted_name: Optional[str]
    ai_confidence: Optional[float]
    ai_status: str
    moderation_status: str
    moderation_reason: Optional[str]
    submitted_at: str

    model_config = {"from_attributes": True}


class ModerationAction(BaseModel):
    reason: Optional[str] = None
