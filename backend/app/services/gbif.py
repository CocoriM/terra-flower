import json

import httpx

GBIF_BASE = "https://api.gbif.org/v1"
CACHE_TTL = 21600  # 6 hours


class GBIFService:
    async def get_occurrences(self, redis, scientific_name: str, limit: int = 300) -> dict:
        cache_key = f"gbif:occurrences:{scientific_name}:{limit}"

        if redis:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

        async with httpx.AsyncClient(timeout=10.0) as client:
            match_resp = await client.get(f"{GBIF_BASE}/species/match", params={"name": scientific_name})
            match_resp.raise_for_status()
            match_data = match_resp.json()
            usage_key = match_data.get("usageKey")

            if not usage_key:
                return {"occurrences": [], "total_fetched": 0}

            occ_resp = await client.get(
                f"{GBIF_BASE}/occurrence/search",
                params={
                    "taxonKey": usage_key,
                    "hasCoordinate": "true",
                    "limit": limit,
                    "basisOfRecord": "HUMAN_OBSERVATION",
                },
            )
            occ_resp.raise_for_status()
            occ_data = occ_resp.json()

        occurrences = []
        for r in occ_data.get("results", []):
            lat = r.get("decimalLatitude")
            lng = r.get("decimalLongitude")
            if lat is not None and lng is not None:
                occurrences.append({
                    "lat": lat,
                    "lng": lng,
                    "country": r.get("country"),
                    "year": r.get("year"),
                })

        result = {"occurrences": occurrences, "total_fetched": len(occurrences)}

        if redis:
            await redis.setex(cache_key, CACHE_TTL, json.dumps(result))

        return result


gbif_service = GBIFService()
