import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Double, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ApprovedGalleryItem(Base):
    __tablename__ = "approved_gallery_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("user_uploads.id", ondelete="CASCADE"))
    plant_id = Column(UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"))
    latitude = Column(Double)
    longitude = Column(Double)
    elevation_meters = Column(Double)
    approved_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_gallery_plant", "plant_id"),
    )
