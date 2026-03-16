import httpx

from app.config import settings

PLANTNET_URL = "https://my-api.plantnet.org/v2/identify/all"


class PlantNetService:
    async def identify(self, image_bytes: bytes) -> dict:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    PLANTNET_URL,
                    params={"api-key": settings.PLANTNET_API_KEY},
                    files={"images": ("image.jpg", image_bytes, "image/jpeg")},
                    data={"organs": "auto"},
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            if not results:
                return {"predicted_name": None, "confidence": 0, "top_results": []}

            top = results[0]
            return {
                "predicted_name": top["species"]["scientificNameWithoutAuthor"],
                "confidence": top["score"],
                "top_results": [
                    {
                        "name": r["species"]["scientificNameWithoutAuthor"],
                        "common_names": r["species"].get("commonNames", []),
                        "score": r["score"],
                    }
                    for r in results[:5]
                ],
            }
        except Exception as e:
            return {"predicted_name": None, "confidence": 0, "top_results": [], "error": str(e)}

    def decide_status(self, confidence: float, predicted_name, expected_name: str) -> str:
        auto_approve = settings.PLANTNET_AUTO_APPROVE_THRESHOLD
        manual_review = settings.PLANTNET_MANUAL_REVIEW_THRESHOLD

        if confidence >= auto_approve and predicted_name and predicted_name.lower() == expected_name.lower():
            return "approved_auto"
        if confidence >= manual_review:
            return "needs_review"
        if confidence < manual_review:
            return "rejected_auto"
        return "needs_review"


plantnet_service = PlantNetService()
