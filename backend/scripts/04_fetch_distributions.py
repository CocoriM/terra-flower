"""
Step 4: Fetch distribution coordinates from GBIF occurrence API.

For each species, fetches up to 50 occurrence records with coordinates
and elevation data.

Output: backend/data/processed/distributions.json

Flags:
  --limit N    Only process first N species
  --resume     Skip species already in the output file
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List

import httpx

GBIF_BASE = "https://api.gbif.org/v1"
DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
INPUT_FILE = DATA_DIR / "species_list.json"
OUTPUT_FILE = DATA_DIR / "distributions.json"
POINTS_PER_SPECIES = 50
CONCURRENCY = 20
SAVE_EVERY = 500


def format_eta(elapsed: float, done: int, total: int) -> str:
    if done == 0:
        return "calculating..."
    rate = done / elapsed
    remaining = (total - done) / rate
    mins, secs = divmod(int(remaining), 60)
    return f"{mins}m{secs:02d}s"


async def fetch_occurrences(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, species_key: int
) -> List[Dict]:
    """Fetch occurrence records for a species."""
    async with sem:
        try:
            resp = await client.get(
                f"{GBIF_BASE}/occurrence/search",
                params={
                    "speciesKey": species_key,
                    "hasCoordinate": "true",
                    "basisOfRecord": "HUMAN_OBSERVATION",
                    "limit": POINTS_PER_SPECIES,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])

            points = []
            for r in results:
                lat = r.get("decimalLatitude")
                lng = r.get("decimalLongitude")
                if lat is None or lng is None:
                    continue
                points.append({
                    "lat": lat,
                    "lng": lng,
                    "elevation": r.get("elevation"),
                    "country": r.get("country"),
                    "continent": r.get("continent"),
                    "gbif_id": r.get("key"),
                })
            return points
        except Exception:
            return []


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Only process first N species")
    parser.add_argument("--resume", action="store_true", help="Skip species already fetched")
    args = parser.parse_args()

    if not INPUT_FILE.exists():
        print("ERROR: {} not found. Run 01_fetch_species.py first.".format(INPUT_FILE))
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        species_list = json.load(f)

    if args.limit:
        species_list = species_list[:args.limit]

    # Resume support
    distributions = {}  # type: Dict[str, List[Dict]]
    existing_keys = set()  # type: set
    if args.resume and OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            distributions = json.load(f)
        existing_keys = set(distributions.keys())
        print("Resuming: {} species already fetched".format(len(existing_keys)))

    to_fetch = [sp for sp in species_list if sp["scientific_name"] not in existing_keys]
    total = len(to_fetch)
    if total == 0:
        print("Nothing to fetch.")
        return

    print("Fetching distributions for {} species (concurrency={})...".format(total, CONCURRENCY))
    sem = asyncio.Semaphore(CONCURRENCY)
    done = 0
    new_points = 0
    t0 = time.time()

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=CONCURRENCY + 5)) as client:
        for batch_start in range(0, total, SAVE_EVERY):
            batch = to_fetch[batch_start:batch_start + SAVE_EVERY]
            tasks = [
                fetch_occurrences(client, sem, sp["species_key"])
                for sp in batch
            ]
            results = await asyncio.gather(*tasks)

            for sp, points in zip(batch, results):
                if points:
                    distributions[sp["scientific_name"]] = points
                    new_points += len(points)
            done += len(batch)

            elapsed = time.time() - t0
            eta = format_eta(elapsed, done, total)
            print(
                "  {}/{} done, {} with data, {} new points | ETA: {}".format(
                    done, total, len(distributions), new_points, eta
                )
            )
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(distributions, f, ensure_ascii=False, indent=2)

    total_pts = sum(len(v) for v in distributions.values())
    print("\nTotal: {} species with data, {} points".format(len(distributions), total_pts))


if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    elapsed = time.time() - start
    print("Done in {:.0f}s ({:.1f} min)".format(elapsed, elapsed / 60))
