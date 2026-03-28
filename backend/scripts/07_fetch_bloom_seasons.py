"""
Step 7: Fetch bloom seasons for all plants.

Strategy:
  1. Query Wikidata SPARQL for bloom months by scientific name
     (properties: P8024 earliest bloom, P8025 latest bloom)
  2. Fallback: estimate from plant_type + hemisphere of distribution points

Flags:
  --limit N     Only process first N species
  --resume      Skip plants that already have bloom_season set
  --concurrency Number of parallel HTTP requests (default 5)
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import asyncpg
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# Wikidata month QIDs
WIKIDATA_MONTH_MAP = {
    "Q108": 1, "Q109": 2, "Q110": 3, "Q111": 4,
    "Q112": 5, "Q113": 6, "Q114": 7, "Q115": 8,
    "Q116": 9, "Q117": 10, "Q118": 11, "Q119": 12,
}


def get_asyncpg_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://terraflora:terraflora@localhost:5432/terraflora",
    )
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def offset_months(months: List[int], offset: int) -> List[int]:
    """Offset month numbers by a value, wrapping around 1-12."""
    return sorted(set(((m - 1 + offset) % 12) + 1 for m in months))


def estimate_bloom(plant_type: str, avg_lat: Optional[float]) -> List[int]:
    """Estimate bloom months from plant type and average latitude."""
    is_southern = avg_lat is not None and avg_lat < 0
    is_tropical = avg_lat is not None and abs(avg_lat) < 23.5

    if is_tropical:
        return list(range(1, 13))

    if plant_type == "grass":
        base = [5, 6, 7, 8]
    elif plant_type == "tree":
        base = [3, 4, 5]
    else:
        base = [3, 4, 5, 6, 7]

    if is_southern:
        return offset_months(base, 6)
    return base


def months_between(start: int, end: int) -> List[int]:
    """Return list of months from start to end inclusive, wrapping around."""
    if start <= end:
        return list(range(start, end + 1))
    # Wraps around December -> January
    return list(range(start, 13)) + list(range(1, end + 1))


async def query_wikidata_batch(
    client: httpx.AsyncClient,
    names: List[str],
) -> Dict[str, List[int]]:
    """Query Wikidata for bloom months of multiple plants at once.

    Uses P8024 (earliest bloom) and P8025 (latest bloom) or P3893
    (flowering period). Returns dict mapping scientific_name -> month list.
    """
    # Escape names for SPARQL VALUES clause
    values = " ".join('"{}"'.format(n.replace('"', '\\"')) for n in names)

    sparql = """
    SELECT ?name ?startMonth ?endMonth ?flowerMonth WHERE {{
      VALUES ?name {{ {values} }}
      ?taxon wdt:P225 ?name .
      OPTIONAL {{ ?taxon wdt:P8024 ?startMonth . }}
      OPTIONAL {{ ?taxon wdt:P8025 ?endMonth . }}
      OPTIONAL {{ ?taxon wdt:P3893 ?flowerMonth . }}
    }}
    """.format(values=values)

    try:
        resp = await client.get(
            WIKIDATA_SPARQL,
            params={"query": sparql, "format": "json"},
            headers={"User-Agent": "TerraFlora/1.0 (bloom-season-fetcher; contact: dev@terraflora.app)"},
            timeout=30.0,
        )
        if resp.status_code == 429:
            await asyncio.sleep(10)
            return {}
        if resp.status_code != 200:
            return {}

        data = resp.json()
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            return {}

        results: Dict[str, List[int]] = {}
        for b in bindings:
            name = b.get("name", {}).get("value", "")
            if not name:
                continue

            # Try start/end month range
            start_uri = b.get("startMonth", {}).get("value", "")
            end_uri = b.get("endMonth", {}).get("value", "")
            flower_uri = b.get("flowerMonth", {}).get("value", "")

            start_qid = start_uri.rsplit("/", 1)[-1] if "/" in start_uri else ""
            end_qid = end_uri.rsplit("/", 1)[-1] if "/" in end_uri else ""
            flower_qid = flower_uri.rsplit("/", 1)[-1] if "/" in flower_uri else ""

            if start_qid in WIKIDATA_MONTH_MAP and end_qid in WIKIDATA_MONTH_MAP:
                months = months_between(
                    WIKIDATA_MONTH_MAP[start_qid],
                    WIKIDATA_MONTH_MAP[end_qid],
                )
                existing = results.get(name, [])
                results[name] = sorted(set(existing + months))
            elif flower_qid in WIKIDATA_MONTH_MAP:
                existing = results.get(name, [])
                existing.append(WIKIDATA_MONTH_MAP[flower_qid])
                results[name] = sorted(set(existing))

        return results

    except (httpx.HTTPError, json.JSONDecodeError, KeyError):
        return {}


async def main(limit: int, resume: bool, concurrency: int) -> None:
    url = get_asyncpg_url()
    pool = await asyncpg.create_pool(url, min_size=2, max_size=concurrency + 1)
    print("Connected to database (pool size: {})".format(concurrency + 1))

    # Fetch all plants with average latitude
    where_clause = "WHERE p.bloom_season IS NULL OR p.bloom_season = ''" if resume else ""
    limit_clause = "LIMIT {}".format(limit) if limit > 0 else ""

    query = """
        SELECT p.id, p.scientific_name, p.plant_type,
               AVG(d.latitude) as avg_lat
        FROM plants p
        LEFT JOIN plant_distribution_points d ON d.plant_id = p.id
        {where}
        GROUP BY p.id, p.scientific_name, p.plant_type
        ORDER BY p.scientific_name
        {limit}
    """.format(where=where_clause, limit=limit_clause)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query)

    total = len(rows)
    print("Plants to process: {}".format(total))

    if total == 0:
        print("Nothing to do.")
        await pool.close()
        return

    plants = [
        {
            "id": r["id"],
            "scientific_name": r["scientific_name"],
            "plant_type": r["plant_type"],
            "avg_lat": float(r["avg_lat"]) if r["avg_lat"] is not None else None,
        }
        for r in rows
    ]

    wikidata_hits = 0
    estimate_hits = 0
    errors = 0
    start_time = time.time()

    # Process in batches: query Wikidata for batch, then save results
    batch_size = 20  # Wikidata batch size for SPARQL VALUES
    sem = asyncio.Semaphore(concurrency)

    async def save_one(plant: Dict, bloom: List[int]) -> None:
        async with sem:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE plants SET bloom_season = $1 WHERE id = $2",
                    json.dumps(bloom),
                    plant["id"],
                )

    async with httpx.AsyncClient() as client:
        for i in range(0, total, batch_size):
            batch = plants[i : i + batch_size]
            names = [p["scientific_name"] for p in batch]

            # Query Wikidata for the whole batch
            try:
                wiki_results = await query_wikidata_batch(client, names)
            except Exception as e:
                wiki_results = {}
                errors += 1
                print("  Wikidata batch error: {}".format(e))

            # For each plant, use Wikidata result or estimate
            save_tasks = []
            for plant in batch:
                sn = plant["scientific_name"]
                months = wiki_results.get(sn)
                if months and len(months) > 0:
                    wikidata_hits += 1
                else:
                    months = estimate_bloom(plant["plant_type"], plant.get("avg_lat"))
                    estimate_hits += 1
                save_tasks.append(save_one(plant, months))

            # Save all in parallel using pool
            results = await asyncio.gather(*save_tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    errors += 1
                    print("  DB save error: {}".format(r))

            done = min(i + batch_size, total)
            elapsed = time.time() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            print("[{}/{}] {:.1f}/s  (wikidata: {}, estimated: {}, errors: {})".format(
                done, total, rate, wikidata_hits, estimate_hits, errors
            ))

    await pool.close()
    elapsed = time.time() - start_time
    print("\nDone in {:.1f}s".format(elapsed))
    print("  Wikidata: {}".format(wikidata_hits))
    print("  Estimated: {}".format(estimate_hits))
    print("  Errors: {}".format(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch bloom seasons for plants")
    parser.add_argument("--limit", type=int, default=0, help="Max plants (0 = all)")
    parser.add_argument("--resume", action="store_true", help="Skip plants with existing bloom_season")
    parser.add_argument("--concurrency", type=int, default=5, help="Parallel requests")
    args = parser.parse_args()

    asyncio.run(main(args.limit, args.resume, args.concurrency))
