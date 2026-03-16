from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_redis
from app.models.gallery import ApprovedGalleryItem
from app.models.upload import UserUpload
from app.services.gbif import gbif_service
from app.services.trefle import trefle_service

router = APIRouter()


@router.get("")
async def list_plants(
    type: str = Query("all", regex="^(all|flower|tree|grass)$"),
    search: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    redis=Depends(get_redis),
):
    try:
        return await trefle_service.list_plants(redis, type, search, page, per_page)
    except Exception:
        raise HTTPException(status_code=503, detail="Plant data temporarily unavailable")


@router.get("/{trefle_id}")
async def get_plant(trefle_id: int, redis=Depends(get_redis)):
    try:
        result = await trefle_service.get_plant(redis, trefle_id)
        if not result:
            raise HTTPException(status_code=404, detail="Plant not found")
        return result
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Plant data temporarily unavailable")


@router.get("/{trefle_id}/occurrences")
async def get_occurrences(
    trefle_id: int,
    limit: int = Query(300, ge=1, le=500),
    scientific_name: str = Query(None, max_length=255),
    redis=Depends(get_redis),
):
    try:
        if not scientific_name:
            plant = await trefle_service.get_plant(redis, trefle_id)
            if not plant:
                raise HTTPException(status_code=404, detail="Plant not found")
            scientific_name = plant["scientific_name"]

        occ_data = await gbif_service.get_occurrences(redis, scientific_name, limit)

        return {
            "trefle_id": trefle_id,
            "scientific_name": scientific_name,
            "occurrences": occ_data["occurrences"],
            "total_fetched": occ_data["total_fetched"],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Occurrence data temporarily unavailable")


@router.get("/{trefle_id}/gallery")
async def get_gallery(
    trefle_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page
    result = await db.execute(
        select(UserUpload)
        .join(ApprovedGalleryItem, ApprovedGalleryItem.upload_id == UserUpload.id)
        .where(ApprovedGalleryItem.trefle_plant_id == trefle_id)
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
                "plant_common_name": u.plant_common_name,
                "latitude": u.latitude,
                "longitude": u.longitude,
                "submitted_at": u.submitted_at.isoformat() if u.submitted_at else None,
            }
            for u in uploads
        ],
        "page": page,
        "per_page": per_page,
    }
