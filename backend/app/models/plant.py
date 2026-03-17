import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Double, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Plant(Base):
    __tablename__ = "plants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    common_name = Column(Text, nullable=False)
    common_name_zh = Column(Text)
    scientific_name = Column(Text, nullable=False, unique=True)
    family = Column(Text)
    genus = Column(Text)
    plant_type = Column(String(20), nullable=False)
    description = Column(Text)
    habitat = Column(Text)
    bloom_season = Column(Text)
    hero_image_url = Column(Text)
    hero_image_attribution = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_plants_type", "plant_type"),
        Index("idx_plants_scientific", "scientific_name"),
    )


class PlantDistributionPoint(Base):
    __tablename__ = "plant_distribution_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plant_id = Column(UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"))
    latitude = Column(Double, nullable=False)
    longitude = Column(Double, nullable=False)
    elevation_meters = Column(Double)
    country = Column(String(100))
    region = Column(String(200))
    continent = Column(String(50))
    source = Column(String(50), default="gbif")
    source_record_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_distribution_plant", "plant_id"),
        Index("idx_distribution_location", "continent", "country"),
    )


class PlantImage(Base):
    __tablename__ = "plant_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plant_id = Column(UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"))
    image_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text)
    image_type = Column(String(20), default="reference")
    attribution = Column(Text)
    source = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_plant_images_plant", "plant_id"),
    )
