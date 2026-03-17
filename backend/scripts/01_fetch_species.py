"""
Step 1: Fetch top observed plant species from GBIF.

Uses the GBIF occurrence search facet to find the most frequently observed
plant species, then fetches full taxonomy and vernacular names for each.

Output: backend/data/processed/species_list.json

Flags:
  --limit N    Only fetch first N species (for testing)
  --resume     Skip species already in the output file
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import httpx

GBIF_BASE = "https://api.gbif.org/v1"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "species_list.json"
TARGET_SPECIES = 10000
CONCURRENCY = 20
SAVE_EVERY = 500


def format_eta(elapsed: float, done: int, total: int) -> str:
    if done == 0:
        return "calculating..."
    rate = done / elapsed
    remaining = (total - done) / rate
    mins, secs = divmod(int(remaining), 60)
    return f"{mins}m{secs:02d}s"


async def fetch_top_species_keys(client: httpx.AsyncClient, limit: int) -> List[Dict]:
    """Fetch top observed plant species using GBIF faceted search.

    Uses kingdomKey=6 (Plantae) which is the reliable numeric filter.
    The text-based 'kingdom=Plantae' param does NOT filter the facet results.
    """
    print(f"Fetching top {limit} most observed plant species from GBIF...")
    resp = await client.get(
        f"{GBIF_BASE}/occurrence/search",
        params={
            "kingdomKey": 6,  # Plantae — numeric key is reliable
            "hasCoordinate": "true",
            "basisOfRecord": "HUMAN_OBSERVATION",
            "facet": "speciesKey",
            "facetLimit": limit,
            "limit": 0,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()

    facets = data.get("facets", [])
    if not facets:
        print("ERROR: No facets returned from GBIF")
        return []

    species_facet = facets[0]
    counts = species_facet.get("counts", [])
    print(f"Got {len(counts)} species keys from facet search")

    return [{"species_key": int(c["name"]), "occurrence_count": c["count"]} for c in counts]


async def fetch_one_species(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    species_key: int,
    occurrence_count: int,
) -> Optional[Dict]:
    """Fetch taxonomy + vernacular names for a single species."""
    async with sem:
        # Fetch taxonomy
        try:
            resp = await client.get(f"{GBIF_BASE}/species/{species_key}", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()

            # Reject non-Plantae species that slipped through
            kingdom = data.get("kingdom", "")
            if kingdom and kingdom != "Plantae":
                return None

            detail = {
                "species_key": species_key,
                "scientific_name": data.get("canonicalName") or data.get("scientificName", ""),
                "scientific_name_full": data.get("scientificName", ""),
                "kingdom": kingdom,
                "family": data.get("family", ""),
                "genus": data.get("genus", ""),
                "order": data.get("order", ""),
                "class": data.get("class", ""),
                "rank": data.get("rank", ""),
                "occurrence_count": occurrence_count,
            }
        except Exception:
            return None

        # Fetch vernacular names
        names = {"common_name": None, "common_name_zh": None}
        try:
            resp = await client.get(
                f"{GBIF_BASE}/species/{species_key}/vernacularNames",
                params={"limit": 100},
                timeout=10.0,
            )
            resp.raise_for_status()
            for entry in resp.json().get("results", []):
                lang = entry.get("language", "")
                name = entry.get("vernacularName", "")
                if not name:
                    continue
                if lang == "eng" and not names["common_name"]:
                    names["common_name"] = name
                elif lang == "zho" and not names["common_name_zh"]:
                    names["common_name_zh"] = name
                if names["common_name"] and names["common_name_zh"]:
                    break
        except Exception:
            pass

        detail["common_name"] = names["common_name"] or detail["scientific_name"]
        detail["common_name_zh"] = names["common_name_zh"]
        return detail


def save(species_list: List[Dict]) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(species_list, f, ensure_ascii=False, indent=2)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Only fetch first N species")
    parser.add_argument("--resume", action="store_true", help="Skip species already fetched")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    target = args.limit or TARGET_SPECIES

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=CONCURRENCY + 5)) as client:
        species_entries = await fetch_top_species_keys(client, target)
        if not species_entries:
            print("No species found. Exiting.")
            return

        # Resume support
        existing_keys = set()
        species_list = []  # type: List[Dict]
        if args.resume and OUTPUT_FILE.exists():
            with open(OUTPUT_FILE, encoding="utf-8") as f:
                species_list = json.load(f)
            existing_keys = {sp["species_key"] for sp in species_list}
            print(f"Resuming: {len(existing_keys)} species already fetched, skipping them")

        to_fetch = [e for e in species_entries if e["species_key"] not in existing_keys]
        total = len(to_fetch)
        if total == 0:
            print("Nothing to fetch. All species already in output file.")
            return

        print(f"Fetching {total} species (concurrency={CONCURRENCY})...")
        sem = asyncio.Semaphore(CONCURRENCY)
        done = 0
        t0 = time.time()

        # Process in batches for incremental saves
        for batch_start in range(0, total, SAVE_EVERY):
            batch = to_fetch[batch_start:batch_start + SAVE_EVERY]
            tasks = [
                fetch_one_species(client, sem, e["species_key"], e["occurrence_count"])
                for e in batch
            ]
            results = await asyncio.gather(*tasks)

            for r in results:
                if r:
                    species_list.append(r)
            done += len(batch)

            elapsed = time.time() - t0
            eta = format_eta(elapsed, done, total)
            print(
                f"  Progress: {done}/{total} fetched, "
                f"{len(species_list)} valid | "
                f"ETA: {eta}"
            )
            save(species_list)

    print(f"\nTotal: {len(species_list)} species saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    elapsed = time.time() - start
    print(f"Done in {elapsed:.0f}s ({elapsed / 60:.1f} min)")
