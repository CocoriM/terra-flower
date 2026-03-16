import json

import httpx

from app.config import settings

TREFLE_BASE = "https://trefle.io/api/v1"
CACHE_TTL = 86400  # 24 hours


class TrefleService:
    def classify_plant_type(self, item: dict) -> str:
        specs = item.get("specifications") or {}
        ligneous_type = specs.get("ligneous_type") or item.get("ligneous_type") or ""
        growth_habit = specs.get("growth_habit") or item.get("growth_habit") or ""
        flower = item.get("flower") or {}
        flower_color = flower.get("color")

        if ligneous_type == "tree" or "Tree" in growth_habit:
            return "tree"
        if "Graminoid" in growth_habit or "Grass" in growth_habit:
            return "grass"
        if flower_color or "Herb" in growth_habit or "Forb" in growth_habit:
            return "flower"
        return "flower"

    async def list_plants(self, redis, type_filter: str, search: str, page: int, per_page: int) -> dict:
        cache_key = f"trefle:list:{type_filter}:{search}:{page}:{per_page}"

        if redis:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

        params = {"token": settings.TREFLE_API_KEY, "page": page, "per_page": per_page}

        if search:
            url = f"{TREFLE_BASE}/plants/search"
            params["q"] = search
        else:
            url = f"{TREFLE_BASE}/plants"

        if type_filter == "tree":
            params["filter[ligneous_type]"] = "tree"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        plants = []
        for item in data.get("data", []):
            plant_type = self.classify_plant_type(item)
            if type_filter and type_filter != "all" and plant_type != type_filter:
                continue
            plants.append({
                "trefle_id": item.get("id"),
                "common_name": item.get("common_name"),
                "scientific_name": item.get("scientific_name"),
                "plant_type": plant_type,
                "family": item.get("family_common_name"),
                "image_url": item.get("image_url"),
                "native_regions": [],
            })

        meta = data.get("meta", {})
        result = {
            "plants": plants,
            "page": page,
            "per_page": per_page,
            "total": meta.get("total", len(plants)),
        }

        if redis:
            await redis.setex(cache_key, CACHE_TTL, json.dumps(result))

        return result

    async def get_plant(self, redis, trefle_id: int) -> dict:
        cache_key = f"trefle:plant:{trefle_id}"

        if redis:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

        url = f"{TREFLE_BASE}/plants/{trefle_id}"
        params = {"token": settings.TREFLE_API_KEY}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json().get("data", {})

        distributions = data.get("distributions", {})
        native_regions = [d.get("name", "") for d in distributions.get("native", [])]

        result = {
            "trefle_id": data.get("id"),
            "common_name": data.get("common_name"),
            "scientific_name": data.get("scientific_name"),
            "plant_type": self.classify_plant_type(data),
            "family": data.get("family_common_name"),
            "image_url": data.get("image_url"),
            "native_regions": native_regions,
            "description": data.get("observations") or data.get("bibliography") or "",
        }

        if redis:
            await redis.setex(cache_key, CACHE_TTL, json.dumps(result))

        return result


trefle_service = TrefleService()
