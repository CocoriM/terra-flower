import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Double, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class UserUpload(Base):
    __tablename__ = "user_uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    trefle_plant_id = Column(Integer, nullable=False)
    plant_scientific_name = Column(String(255), nullable=False)
    plant_common_name = Column(String(255))
    plant_type = Column(String(20))
    image_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text)
    image_hash = Column(String(64))
    latitude = Column(Double)
    longitude = Column(Double)
    location_text = Column(String(500))
    country = Column(String(100))
    continent = Column(String(50))
    ai_predicted_name = Column(String(255))
    ai_confidence = Column(Double)
    ai_top_results = Column(JSONB)
    ai_status = Column(String(30), default="pending")
    moderation_status = Column(String(30), default="pending")
    moderation_reason = Column(Text)
    moderator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    captured_at = Column(DateTime)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_uploads_plant", "trefle_plant_id"),
        Index("idx_uploads_status", "moderation_status"),
        Index("idx_uploads_user", "user_id"),
    )
