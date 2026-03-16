import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Double, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ApprovedGalleryItem(Base):
    __tablename__ = "approved_gallery_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("user_uploads.id", ondelete="CASCADE"))
    trefle_plant_id = Column(Integer, nullable=False)
    latitude = Column(Double)
    longitude = Column(Double)
    approved_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_gallery_plant", "trefle_plant_id"),
    )
