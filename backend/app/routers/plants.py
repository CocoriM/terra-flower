from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.gallery import ApprovedGalleryItem
from app.models.plant import Plant, PlantDistributionPoint, PlantImage
from app.models.upload import UserUpload

router = APIRouter()


@router.get("")
async def list_plants(
    type: str = Query("all", pattern="^(all|flower|tree|grass)$"),
    search: str = Query("", max_length=200),
    continent: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    # Count distribution points per plant via subquery
    dist_count_sub = (
        select(
            PlantDistributionPoint.plant_id,
            func.count().label("distribution_count"),
        )
        .group_by(PlantDistributionPoint.plant_id)
        .subquery()
    )

    query = select(Plant, func.coalesce(dist_count_sub.c.distribution_count, 0).label("distribution_count")).outerjoin(
        dist_count_sub, Plant.id == dist_count_sub.c.plant_id
    )

    if type != "all":
        query = query.where(Plant.plant_type == type)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            Plant.common_name.ilike(pattern)
            | Plant.scientific_name.ilike(pattern)
            | Plant.common_name_zh.ilike(pattern)
        )
    if continent:
        # Filter plants that have distribution points in the given continent
        plant_ids_in_continent = (
            select(PlantDistributionPoint.plant_id)
            .where(PlantDistributionPoint.continent == continent)
            .distinct()
        )
        query = query.where(Plant.id.in_(plant_ids_in_continent))

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginated results
    offset = (page - 1) * per_page
    query = query.order_by(Plant.common_name).offset(offset).limit(per_page)
    result = await db.execute(query)
    rows = result.all()

    plants = [
        {
            "id": str(plant.id),
            "common_name": plant.common_name,
            "common_name_zh": plant.common_name_zh,
            "scientific_name": plant.scientific_name,
            "plant_type": plant.plant_type,
            "family": plant.family,
            "hero_image_url": plant.hero_image_url,
            "distribution_count": dist_count,
        }
        for plant, dist_count in rows
    ]

    return {"plants": plants, "page": page, "per_page": per_page, "total": total}


@router.get("/{plant_id}")
async def get_plant(plant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plant).where(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    # Distribution count
    dist_count = (
        await db.execute(
            select(func.count()).where(PlantDistributionPoint.plant_id == plant.id)
        )
    ).scalar() or 0

    # Images
    img_result = await db.execute(
        select(PlantImage).where(PlantImage.plant_id == plant.id)
    )
    images = img_result.scalars().all()

    return {
        "id": str(plant.id),
        "common_name": plant.common_name,
        "common_name_zh": plant.common_name_zh,
        "scientific_name": plant.scientific_name,
        "plant_type": plant.plant_type,
        "family": plant.family,
        "genus": plant.genus,
        "description": plant.description,
        "habitat": plant.habitat,
        "bloom_season": plant.bloom_season,
        "hero_image_url": plant.hero_image_url,
        "hero_image_attribution": plant.hero_image_attribution,
        "distribution_count": dist_count,
        "images": [
            {
                "id": str(img.id),
                "image_url": img.image_url,
                "thumbnail_url": img.thumbnail_url,
                "image_type": img.image_type,
                "attribution": img.attribution,
                "source": img.source,
            }
            for img in images
        ],
    }


@router.get("/{plant_id}/distributions")
async def get_distributions(
    plant_id: str,
    limit: int = Query(300, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    # Verify plant exists
    plant_exists = (
        await db.execute(select(Plant.id).where(Plant.id == plant_id))
    ).scalar_one_or_none()
    if not plant_exists:
        raise HTTPException(status_code=404, detail="Plant not found")

    result = await db.execute(
        select(PlantDistributionPoint)
        .where(PlantDistributionPoint.plant_id == plant_id)
        .limit(limit)
    )
    points = result.scalars().all()

    return {
        "plant_id": plant_id,
        "distributions": [
            {
                "lat": p.latitude,
                "lng": p.longitude,
                "elevation": p.elevation_meters,
                "country": p.country,
            }
            for p in points
        ],
    }


@router.get("/{plant_id}/gallery")
async def get_gallery(
    plant_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page
    result = await db.execute(
        select(UserUpload)
        .join(ApprovedGalleryItem, ApprovedGalleryItem.upload_id == UserUpload.id)
        .where(ApprovedGalleryItem.plant_id == plant_id)
        .order_by(ApprovedGalleryItem.approved_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    uploads = result.scalars().all()

    return {
        "items": [
            {
                "id": str(u.id),
                "image_url": u.image_url,
                "thumbnail_url": u.thumbnail_url,
                "latitude": u.latitude,
                "longitude": u.longitude,
                "submitted_at": u.submitted_at.isoformat() if u.submitted_at else None,
            }
            for u in uploads
        ],
        "page": page,
        "per_page": per_page,
    }
