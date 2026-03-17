import hashlib
import io
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.gallery import ApprovedGalleryItem
from app.models.plant import Plant
from app.models.upload import UserUpload
from app.models.user import User
from app.services.plantnet import plantnet_service
from app.services.storage import delete_file, upload_file

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB
MAX_COMPRESSED = 2 * 1024 * 1024  # 2MB


class ConfirmRequest(BaseModel):
    confirmed_plant_id: str


@router.post("")
async def create_upload(
    image: UploadFile = File(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
    location_text: str = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reverse identification: user uploads image, AI identifies the plant."""
    # Step 1: Validate MIME
    if image.content_type not in ALLOWED_MIMES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are accepted")

    # Step 2: Check file size
    image_bytes = await image.read()
    if len(image_bytes) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File must be 10MB or smaller")

    # Step 3: Rate limit
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    one_day_ago = datetime.utcnow() - timedelta(days=1)

    hourly_count = await db.scalar(
        select(func.count()).select_from(UserUpload).where(
            UserUpload.user_id == user.id,
            UserUpload.submitted_at >= one_hour_ago,
        )
    )
    if hourly_count >= 10:
        raise HTTPException(status_code=429, detail="Upload limit reached. Try again later.")

    daily_count = await db.scalar(
        select(func.count()).select_from(UserUpload).where(
            UserUpload.user_id == user.id,
            UserUpload.submitted_at >= one_day_ago,
        )
    )
    if daily_count >= 30:
        raise HTTPException(status_code=429, detail="Upload limit reached. Try again later.")

    # Step 4: Duplicate check
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    existing = await db.execute(
        select(UserUpload).where(UserUpload.image_hash == image_hash)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This image has already been uploaded")

    # Step 5: Compress if needed
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")

    compressed_bytes = image_bytes
    if len(image_bytes) > MAX_COMPRESSED:
        buf = io.BytesIO()
        quality = 85
        img.save(buf, format="JPEG", quality=quality)
        while buf.tell() > MAX_COMPRESSED and quality > 20:
            buf = io.BytesIO()
            quality -= 10
            img.save(buf, format="JPEG", quality=quality)
        compressed_bytes = buf.getvalue()

    # Step 6: Generate thumbnail
    thumb = img.copy()
    thumb.thumbnail((400, 400))
    thumb_buf = io.BytesIO()
    thumb.save(thumb_buf, format="JPEG", quality=80)
    thumb_bytes = thumb_buf.getvalue()

    # Step 7: Upload to S3
    upload_uuid = uuid.uuid4()
    upload_key = str(upload_uuid)
    try:
        image_url = upload_file(compressed_bytes, f"originals/{upload_key}.jpg", "image/jpeg")
        thumbnail_url = upload_file(thumb_bytes, f"thumbnails/{upload_key}_thumb.jpg", "image/jpeg")
    except Exception:
        logger.exception("Image storage upload failed")
        raise HTTPException(status_code=500, detail="Failed to upload image to storage")

    # Step 8: Call PlantNet with regional project
    ai_result = await plantnet_service.identify(compressed_bytes, latitude, longitude)

    # Step 9: Match AI results against our plant database
    ai_top_results = ai_result.get("top_results", [])
    matched_results = await plantnet_service.match_with_database(ai_top_results, db)

    # Step 10: Create DB record
    upload_record = UserUpload(
        id=upload_uuid,
        user_id=user.id,
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        image_hash=image_hash,
        latitude=latitude,
        longitude=longitude,
        location_text=location_text,
        ai_top_results=matched_results,
        ai_best_match_name=ai_result.get("best_match_name"),
        ai_best_match_score=ai_result.get("best_match_score", 0),
        ai_project_used=ai_result.get("project_used"),
        ai_status="pending",
        moderation_status="pending",
    )
    db.add(upload_record)
    await db.commit()
    await db.refresh(upload_record)

    # Step 11: Return upload with AI suggestions
    return {
        "id": str(upload_record.id),
        "image_url": upload_record.image_url,
        "thumbnail_url": upload_record.thumbnail_url,
        "latitude": upload_record.latitude,
        "longitude": upload_record.longitude,
        "ai_best_match_name": upload_record.ai_best_match_name,
        "ai_best_match_score": upload_record.ai_best_match_score,
        "ai_top_results": matched_results,
        "ai_status": upload_record.ai_status,
        "moderation_status": upload_record.moderation_status,
        "submitted_at": upload_record.submitted_at.isoformat() if upload_record.submitted_at else None,
    }


@router.post("/{upload_id}/confirm")
async def confirm_upload(
    upload_id: str,
    body: ConfirmRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User confirms which species the AI identified correctly."""
    result = await db.execute(
        select(UserUpload).where(UserUpload.id == upload_id, UserUpload.user_id == user.id)
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if upload.user_confirmed:
        raise HTTPException(status_code=400, detail="Already confirmed")

    # Verify the plant exists in our DB
    plant_result = await db.execute(
        select(Plant).where(Plant.id == body.confirmed_plant_id)
    )
    plant = plant_result.scalar_one_or_none()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found in database")

    # Update upload with confirmation
    upload.confirmed_plant_id = plant.id
    upload.user_confirmed = True

    # Apply decision rules
    score = upload.ai_best_match_score or 0
    ai_status = plantnet_service.decide_status(score, has_db_match=True)
    upload.ai_status = ai_status

    if ai_status == "approved_auto":
        upload.moderation_status = "approved"
        gallery_item = ApprovedGalleryItem(
            upload_id=upload.id,
            plant_id=plant.id,
            latitude=upload.latitude,
            longitude=upload.longitude,
            elevation_meters=upload.elevation_meters,
        )
        db.add(gallery_item)

    await db.commit()
    await db.refresh(upload)

    return {
        "id": str(upload.id),
        "confirmed_plant_id": str(upload.confirmed_plant_id),
        "user_confirmed": upload.user_confirmed,
        "ai_status": upload.ai_status,
        "moderation_status": upload.moderation_status,
    }


@router.get("/me")
async def get_my_uploads(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page
    result = await db.execute(
        select(UserUpload)
        .where(UserUpload.user_id == user.id)
        .order_by(UserUpload.submitted_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    uploads = result.scalars().all()

    return {
        "uploads": [
            {
                "id": str(u.id),
                "image_url": u.image_url,
                "thumbnail_url": u.thumbnail_url,
                "latitude": u.latitude,
                "longitude": u.longitude,
                "ai_best_match_name": u.ai_best_match_name,
                "ai_best_match_score": u.ai_best_match_score,
                "ai_top_results": u.ai_top_results or [],
                "confirmed_plant_id": str(u.confirmed_plant_id) if u.confirmed_plant_id else None,
                "user_confirmed": u.user_confirmed,
                "ai_status": u.ai_status,
                "moderation_status": u.moderation_status,
                "submitted_at": u.submitted_at.isoformat() if u.submitted_at else None,
            }
            for u in uploads
        ],
        "page": page,
        "per_page": per_page,
    }


@router.delete("/{upload_id}")
async def delete_upload(
    upload_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserUpload).where(UserUpload.id == upload_id, UserUpload.user_id == user.id)
    )
    upload = result.scalar_one_or_none()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    if upload.moderation_status != "pending":
        raise HTTPException(status_code=400, detail="Can only delete pending uploads")

    try:
        upload_uuid = str(upload.id)
        delete_file(f"originals/{upload_uuid}.jpg")
        delete_file(f"thumbnails/{upload_uuid}_thumb.jpg")
    except Exception:
        pass

    await db.delete(upload)
    await db.commit()
    return {"detail": "Upload deleted"}
