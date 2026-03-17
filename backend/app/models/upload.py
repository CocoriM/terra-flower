import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Double, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class UserUpload(Base):
    __tablename__ = "user_uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    # image
    image_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text)
    image_hash = Column(String(64))
    # location
    latitude = Column(Double)
    longitude = Column(Double)
    elevation_meters = Column(Double)
    location_text = Column(String(500))
    country = Column(String(100))
    continent = Column(String(50))
    # AI identification result
    ai_top_results = Column(JSONB)
    ai_best_match_name = Column(String(255))
    ai_best_match_score = Column(Double)
    ai_project_used = Column(String(50))
    # user confirmation
    confirmed_plant_id = Column(UUID(as_uuid=True), ForeignKey("plants.id"))
    user_confirmed = Column(Boolean, default=False)
    # moderation
    ai_status = Column(String(30), default="pending")
    moderation_status = Column(String(30), default="pending")
    moderation_reason = Column(Text)
    moderator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    # timestamps
    captured_at = Column(DateTime)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_uploads_plant", "confirmed_plant_id"),
        Index("idx_uploads_status", "moderation_status"),
        Index("idx_uploads_user", "user_id"),
    )
