from typing import List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.plant import Plant

PLANTNET_BASE = "https://my-api.plantnet.org/v2"


def get_plantnet_project(lat: Optional[float], lng: Optional[float]) -> str:
    """Determine PlantNet flora project from coordinates."""
    if lat is None or lng is None:
        return "all"
    # North America
    if 15 <= lat <= 72 and -170 <= lng <= -50:
        return "namerica"
    # South America
    if -56 <= lat < 15 and -82 <= lng <= -34:
        return "south-america"
    # Western Europe
    if 36 <= lat <= 71 and -12 <= lng <= 25:
        return "weurope"
    # Eastern Mediterranean
    if 28 <= lat <= 45 and 25 <= lng <= 45:
        return "eastern-mediterranean"
    # North Africa
    if 15 <= lat <= 37 and -18 <= lng <= 35:
        return "north-africa"
    # Tropical Africa
    if -35 <= lat < 15 and -18 <= lng <= 52:
        return "tropical-africa"
    # Southern Africa
    if -35 <= lat <= -15 and 10 <= lng <= 41:
        return "southern-africa"
    # Indian subcontinent
    if 5 <= lat <= 37 and 60 <= lng <= 98:
        return "indian-subcontinent"
    # Southeast Asia
    if -11 <= lat <= 28 and 93 <= lng <= 153:
        return "southeast-asia"
    # East Asia
    if 20 <= lat <= 54 and 100 <= lng <= 150:
        return "east-asia"
    # Australia & NZ
    if -48 <= lat <= -10 and 110 <= lng <= 180:
        return "australia"
    # Fallback
    return "all"


class PlantNetService:
    async def identify(
        self,
        image_bytes: bytes,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> dict:
        """Send image to PlantNet and return identification results."""
        project = get_plantnet_project(lat, lng)
        url = f"{PLANTNET_BASE}/identify/{project}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    url,
                    params={
                        "api-key": settings.PLANTNET_API_KEY,
                        "lang": "en",
                        "nb-results": 5,
                    },
                    files={"images": ("image.jpg", image_bytes, "image/jpeg")},
                    data={"organs": "auto"},
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            if not results:
                return {
                    "best_match_name": None,
                    "best_match_score": 0,
                    "top_results": [],
                    "project_used": project,
                }

            top = results[0]
            return {
                "best_match_name": top["species"]["scientificNameWithoutAuthor"],
                "best_match_score": top["score"],
                "top_results": [
                    {
                        "scientific_name": r["species"]["scientificNameWithoutAuthor"],
                        "common_names": r["species"].get("commonNames", []),
                        "score": r["score"],
                        "family": r["species"].get("family", {}).get(
                            "scientificNameWithoutAuthor", ""
                        ),
                    }
                    for r in results[:5]
                ],
                "project_used": project,
            }
        except Exception as e:
            return {
                "best_match_name": None,
                "best_match_score": 0,
                "top_results": [],
                "project_used": project,
                "error": str(e),
            }

    async def match_with_database(
        self, ai_results: List[dict], db: AsyncSession
    ) -> List[dict]:
        """Match AI results against our plants table. Returns enriched results."""
        matched = []
        for r in ai_results:
            scientific_name = r["scientific_name"]
            result = await db.execute(
                select(Plant).where(Plant.scientific_name == scientific_name)
            )
            plant = result.scalar_one_or_none()

            matched.append({
                "scientific_name": scientific_name,
                "common_name": r["common_names"][0] if r.get("common_names") else scientific_name,
                "confidence": r["score"],
                "matched_plant_id": str(plant.id) if plant else None,
                "matched_plant_image": plant.hero_image_url if plant else None,
            })
        return matched

    def decide_status(self, score: float, has_db_match: bool) -> str:
        """Decide AI status based on confidence and DB match."""
        auto_approve = settings.PLANTNET_AUTO_APPROVE_THRESHOLD
        review = settings.PLANTNET_REVIEW_THRESHOLD

        if score >= auto_approve and has_db_match:
            return "approved_auto"
        if score >= review:
            return "needs_review"
        return "not_identified"


plantnet_service = PlantNetService()
