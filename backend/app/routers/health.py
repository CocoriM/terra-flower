import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    status = {"status": "ok"}

    try:
        await db.execute(text("SELECT 1"))
        status["database"] = "connected"
    except Exception:
        status["database"] = "disconnected"
        status["status"] = "degraded"

    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        status["redis"] = "connected"
    except Exception:
        status["redis"] = "disconnected"
        status["status"] = "degraded"

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            status["plantnet_api"] = "reachable" if settings.PLANTNET_API_KEY else "not configured"
        except Exception:
            status["plantnet_api"] = "unreachable"

        try:
            status["cesium_ion"] = "configured" if settings.CESIUM_ION_TOKEN else "not configured"
        except Exception:
            status["cesium_ion"] = "unreachable"

    return status
