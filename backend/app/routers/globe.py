import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.plant import Plant, PlantDistributionPoint

router = APIRouter()


@router.get("/markers")
async def get_globe_markers(
    type: str = Query("all", pattern="^(all|flower|tree|grass)$"),
    continent: str = Query("", max_length=100),
    db: AsyncSession = Depends(get_db),
):
    """Return one representative marker per plant (centroid of distribution points)."""
    query = (
        select(
            Plant.id,
            Plant.common_name,
            Plant.plant_type,
            Plant.hero_image_url,
            func.avg(PlantDistributionPoint.latitude).label("lat"),
            func.avg(PlantDistributionPoint.longitude).label("lng"),
            func.coalesce(func.avg(PlantDistributionPoint.elevation_meters), 0).label("elevation"),
            func.count(PlantDistributionPoint.id).label("occurrence_count"),
            Plant.bloom_season,
        )
        .join(PlantDistributionPoint, PlantDistributionPoint.plant_id == Plant.id)
        .group_by(Plant.id, Plant.common_name, Plant.plant_type, Plant.hero_image_url, Plant.bloom_season)
    )

    if type != "all":
        query = query.where(Plant.plant_type == type)
    if continent:
        query = query.where(PlantDistributionPoint.continent == continent)

    result = await db.execute(query)
    rows = result.all()

    def parse_bloom(raw: str) -> list:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    markers = [
        {
            "plant_id": str(row.id),
            "common_name": row.common_name,
            "plant_type": row.plant_type,
            "lat": round(row.lat, 5),
            "lng": round(row.lng, 5),
            "elevation": round(row.elevation, 1),
            "occurrence_count": row.occurrence_count,
            "hero_image_url": row.hero_image_url,
            "bloom_months": parse_bloom(row.bloom_season),
        }
        for row in rows
    ]

    return {"markers": markers}
