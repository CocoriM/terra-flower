"""
Step 3: Fetch reference images from Wikipedia thumbnails and Wikimedia Commons.

For species that got a Wikipedia thumbnail in step 2, use that directly.
For others, search Wikimedia Commons for CC-licensed images.

Output: backend/data/processed/images.json

Flags:
  --limit N    Only process first N species
  --resume     Skip species already in the output file
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional

import httpx

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
INPUT_SPECIES = DATA_DIR / "species_list.json"
INPUT_DESC_EN = DATA_DIR / "descriptions_en.json"
OUTPUT_FILE = DATA_DIR / "images.json"
CONCURRENCY = 20
SAVE_EVERY = 500

CC_LICENSES = {"cc0", "cc-by", "cc-by-sa", "cc-by-2.0", "cc-by-3.0", "cc-by-4.0",
               "cc-by-sa-2.0", "cc-by-sa-3.0", "cc-by-sa-4.0", "public domain"}


def format_eta(elapsed: float, done: int, total: int) -> str:
    if done == 0:
        return "calculating..."
    rate = done / elapsed
    remaining = (total - done) / rate
    mins, secs = divmod(int(remaining), 60)
    return f"{mins}m{secs:02d}s"


def is_cc_license(license_str: str) -> bool:
    if not license_str:
        return False
    return license_str.lower().strip() in CC_LICENSES


async def search_wikimedia_commons(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, scientific_name: str
) -> Optional[Dict]:
    """Search Wikimedia Commons for CC-licensed images of a species."""
    async with sem:
        try:
            resp = await client.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": scientific_name,
                    "gsrlimit": 3,
                    "prop": "imageinfo",
                    "iiprop": "url|extmetadata",
                    "format": "json",
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})

            for page in pages.values():
                imageinfo = page.get("imageinfo", [])
                if not imageinfo:
                    continue
                info = imageinfo[0]
                metadata = info.get("extmetadata", {})
                license_short = metadata.get("LicenseShortName", {}).get("value", "")
                artist = metadata.get("Artist", {}).get("value", "")
                image_url = info.get("url", "")

                if not image_url:
                    continue
                if not any(image_url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    continue
                if is_cc_license(license_short):
                    return {
                        "image_url": image_url,
                        "attribution": artist[:500] if artist else None,
                        "license": license_short,
                        "source": "wikimedia",
                    }
        except Exception:
            pass
    return None


async def fetch_one_image(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    scientific_name: str,
    wiki_thumb_url: Optional[str],
) -> Optional[Dict]:
    """Get image for one species: Wikipedia thumb or Wikimedia Commons search."""
    if wiki_thumb_url:
        return {
            "image_url": wiki_thumb_url,
            "attribution": "Wikipedia",
            "license": "various",
            "source": "wikipedia",
        }
    return await search_wikimedia_commons(client, sem, scientific_name)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Only process first N species")
    parser.add_argument("--resume", action="store_true", help="Skip species already fetched")
    args = parser.parse_args()

    if not INPUT_SPECIES.exists():
        print("ERROR: {} not found. Run 01_fetch_species.py first.".format(INPUT_SPECIES))
        return

    with open(INPUT_SPECIES, encoding="utf-8") as f:
        species_list = json.load(f)

    descriptions_en = {}  # type: Dict[str, Dict]
    if INPUT_DESC_EN.exists():
        with open(INPUT_DESC_EN, encoding="utf-8") as f:
            descriptions_en = json.load(f)

    if args.limit:
        species_list = species_list[:args.limit]

    # Resume support
    images = {}  # type: Dict[str, Dict]
    existing_keys = set()  # type: set
    if args.resume and OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            images = json.load(f)
        existing_keys = set(images.keys())
        print("Resuming: {} species already have images".format(len(existing_keys)))

    to_fetch = [sp for sp in species_list if sp["scientific_name"] not in existing_keys]
    total = len(to_fetch)
    if total == 0:
        print("Nothing to fetch.")
        return

    print("Loaded {} species, {} with Wikipedia data".format(len(species_list), len(descriptions_en)))
    print("Fetching images for {} species (concurrency={})...".format(total, CONCURRENCY))

    sem = asyncio.Semaphore(CONCURRENCY)
    done = 0
    wiki_thumbs = 0
    commons_hits = 0
    t0 = time.time()

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=CONCURRENCY + 5),
        headers={"User-Agent": "TerraFlora/1.0 (https://github.com/CocoriM/terra-flower; contact@terraflora.app)"},
    ) as client:
        for batch_start in range(0, total, SAVE_EVERY):
            batch = to_fetch[batch_start:batch_start + SAVE_EVERY]
            tasks = []
            for sp in batch:
                sn = sp["scientific_name"]
                thumb_url = descriptions_en.get(sn, {}).get("thumbnail_url")
                tasks.append(fetch_one_image(client, sem, sn, thumb_url))

            results = await asyncio.gather(*tasks)

            for sp, result in zip(batch, results):
                if result:
                    images[sp["scientific_name"]] = result
                    if result["source"] == "wikipedia":
                        wiki_thumbs += 1
                    else:
                        commons_hits += 1
            done += len(batch)

            elapsed = time.time() - t0
            eta = format_eta(elapsed, done, total)
            print(
                "  {}/{} done ({} wiki, {} commons) | ETA: {}".format(
                    done, total, wiki_thumbs, commons_hits, eta
                )
            )
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(images, f, ensure_ascii=False, indent=2)

    total_found = len(images)
    print("\nTotal images: {}/{} ({:.1f}%)".format(
        total_found, len(species_list), total_found / len(species_list) * 100
    ))
    print("  Wikipedia: {}, Commons: {}".format(wiki_thumbs, commons_hits))


if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    elapsed = time.time() - start
    print("Done in {:.0f}s ({:.1f} min)".format(elapsed, elapsed / 60))
