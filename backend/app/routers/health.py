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
            resp = await client.get(f"https://trefle.io/api/v1/plants?token={settings.TREFLE_API_KEY}&per_page=1")
            status["trefle_api"] = "reachable" if resp.status_code == 200 else "unreachable"
        except Exception:
            status["trefle_api"] = "unreachable"

        try:
            resp = await client.get("https://api.gbif.org/v1/species/match?name=Quercus")
            status["gbif_api"] = "reachable" if resp.status_code == 200 else "unreachable"
        except Exception:
            status["gbif_api"] = "unreachable"

        try:
            status["plantnet_api"] = "reachable" if settings.PLANTNET_API_KEY else "not configured"
        except Exception:
            status["plantnet_api"] = "unreachable"

    return status
