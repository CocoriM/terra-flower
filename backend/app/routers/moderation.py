from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_moderator
from app.models.gallery import ApprovedGalleryItem
from app.models.upload import UserUpload
from app.models.user import User
from app.schemas.upload import ModerationAction

router = APIRouter()


@router.get("/pending")
async def get_pending(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    user: User = Depends(require_moderator),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page
    result = await db.execute(
        select(UserUpload)
        .where(UserUpload.moderation_status == "pending", UserUpload.ai_status != "pending")
        .order_by(UserUpload.submitted_at.asc())
        .offset(offset)
        .limit(per_page)
    )
    uploads = result.scalars().all()

    return {
        "uploads": [
            {
                "id": str(u.id),
                "trefle_plant_id": u.trefle_plant_id,
                "plant_common_name": u.plant_common_name,
                "plant_scientific_name": u.plant_scientific_name,
                "plant_type": u.plant_type,
                "image_url": u.image_url,
                "thumbnail_url": u.thumbnail_url,
                "ai_predicted_name": u.ai_predicted_name,
                "ai_confidence": u.ai_confidence,
                "ai_status": u.ai_status,
                "moderation_status": u.moderation_status,
                "submitted_at": u.submitted_at.isoformat() if u.submitted_at else None,
            }
            for u in uploads
        ],
        "page": page,
        "per_page": per_page,
    }


@router.post("/{upload_id}/approve")
async def approve_upload(
    upload_id: str,
    body: ModerationAction,
    user: User = Depends(require_moderator),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserUpload).where(UserUpload.id == upload_id))
    upload = result.scalar_one_or_none()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload.moderation_status = "approved"
    upload.moderation_reason = body.reason
    upload.moderator_id = user.id
    upload.reviewed_at = datetime.utcnow()

    gallery_item = ApprovedGalleryItem(
        upload_id=upload.id,
        trefle_plant_id=upload.trefle_plant_id,
        latitude=upload.latitude,
        longitude=upload.longitude,
    )
    db.add(gallery_item)
    await db.commit()

    return {"detail": "Upload approved"}


@router.post("/{upload_id}/reject")
async def reject_upload(
    upload_id: str,
    body: ModerationAction,
    user: User = Depends(require_moderator),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserUpload).where(UserUpload.id == upload_id))
    upload = result.scalar_one_or_none()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if not body.reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    upload.moderation_status = "rejected"
    upload.moderation_reason = body.reason
    upload.moderator_id = user.id
    upload.reviewed_at = datetime.utcnow()
    await db.commit()

    return {"detail": "Upload rejected"}
