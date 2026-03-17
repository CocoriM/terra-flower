"""
Step 2: Fetch descriptions from Wikipedia (English + Chinese).

For each species in species_list.json, queries Wikipedia REST API
for a summary extract.

Output: backend/data/processed/descriptions_en.json
        backend/data/processed/descriptions_zh.json

Flags:
  --limit N    Only process first N species
  --resume     Skip species already in the output files
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

import httpx

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
INPUT_FILE = DATA_DIR / "species_list.json"
OUTPUT_EN = DATA_DIR / "descriptions_en.json"
OUTPUT_ZH = DATA_DIR / "descriptions_zh.json"
CONCURRENCY = 5
SAVE_EVERY = 500
MAX_ERROR_LOG = 3  # print first N failures per language for debugging
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds, doubles each retry


def strip_author(name: str) -> str:
    """Strip taxonomic author from scientific name.

    GBIF scientificName includes author: 'Helianthus annuus L.'
    Wikipedia titles use canonical form: 'Helianthus annuus'
    Heuristic: keep only the first two words (genus + species).
    """
    parts = name.strip().split()
    if len(parts) >= 2:
        return "{} {}".format(parts[0], parts[1])
    return name.strip()


def format_eta(elapsed: float, done: int, total: int) -> str:
    if done == 0:
        return "calculating..."
    rate = done / elapsed
    remaining = (total - done) / rate
    mins, secs = divmod(int(remaining), 60)
    return f"{mins}m{secs:02d}s"


async def fetch_wikipedia_summary(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, title: str, lang: str = "en",
    error_counts: Optional[Dict] = None,
) -> Optional[Dict]:
    """Fetch Wikipedia summary for a given title, with retry on 429."""
    async with sem:
        encoded = quote(title.replace(" ", "_"), safe="")
        url = "https://{}.wikipedia.org/api/rest_v1/page/summary/{}".format(lang, encoded)
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await client.get(url, timeout=10.0, follow_redirects=True)
                if resp.status_code == 404:
                    return None
                if resp.status_code == 429:
                    if attempt < MAX_RETRIES:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                    return None
                resp.raise_for_status()
                data = resp.json()
                result = {"extract": data.get("extract", "")}
                thumb = data.get("thumbnail", {})
                if thumb:
                    result["thumbnail_url"] = thumb.get("source")
                return result
            except Exception as e:
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                if error_counts is not None:
                    n = error_counts.get("n", 0)
                    if n < MAX_ERROR_LOG:
                        print("  [{}] ERROR fetching '{}': {}".format(lang, title, e))
                        error_counts["n"] = n + 1
                return None


async def fetch_wikipedia_search_fallback(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, query: str, lang: str = "en",
    error_counts: Optional[Dict] = None,
) -> Optional[Dict]:
    """Try searching Wikipedia if direct page lookup fails, with retry on 429."""
    async with sem:
        url = "https://{}.wikipedia.org/w/api.php".format(lang)
        title = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await client.get(
                    url,
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": "{} plant".format(query),
                        "srlimit": 1,
                        "format": "json",
                    },
                    timeout=10.0,
                )
                if resp.status_code == 429:
                    if attempt < MAX_RETRIES:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                    return None
                resp.raise_for_status()
                results = resp.json().get("query", {}).get("search", [])
                if not results:
                    return None
                title = results[0]["title"]
                break
            except Exception as e:
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                if error_counts is not None:
                    n = error_counts.get("n", 0)
                    if n < MAX_ERROR_LOG:
                        print("  [{}] ERROR searching '{}': {}".format(lang, query, e))
                        error_counts["n"] = n + 1
                return None
    if not title:
        return None
    # Fetch summary for the found title (will acquire sem inside)
    return await fetch_wikipedia_summary(client, sem, title, lang, error_counts)


async def fetch_one_description(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    scientific_name: str,
    common_name: Optional[str],
    lang: str,
    error_counts: Optional[Dict] = None,
) -> Optional[Dict]:
    """Fetch description for a single species in a given language."""
    # Use canonical name (no author) for Wikipedia lookup
    lookup_name = strip_author(scientific_name)
    result = await fetch_wikipedia_summary(client, sem, lookup_name, lang, error_counts)
    if not result and common_name and lang == "en":
        result = await fetch_wikipedia_search_fallback(client, sem, common_name, lang, error_counts)
    if result and result.get("extract"):
        return result
    return None


async def fetch_descriptions_for_lang(
    species_list: List[Dict], lang: str, output_file: Path, resume: bool
):
    """Fetch descriptions for all species in a given language with concurrency."""
    # Load existing for resume
    descriptions = {}  # type: Dict[str, Dict]
    existing_keys = set()  # type: set
    if resume and output_file.exists():
        with open(output_file, encoding="utf-8") as f:
            descriptions = json.load(f)
        existing_keys = set(descriptions.keys())
        print("  [{}] Resuming: {} already fetched".format(lang, len(existing_keys)))

    to_fetch = [sp for sp in species_list if sp["scientific_name"] not in existing_keys]
    total = len(to_fetch)
    if total == 0:
        print("  [{}] Nothing to fetch.".format(lang))
        return

    print("  [{}] Fetching {} descriptions (concurrency={})...".format(lang, total, CONCURRENCY))
    sem = asyncio.Semaphore(CONCURRENCY)
    error_counts = {"n": 0}  # type: Dict[str, int]
    done = 0
    hits = 0
    t0 = time.time()

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=CONCURRENCY + 5),
        headers={"User-Agent": "TerraFlora/1.0 (https://github.com/CocoriM/terra-flower; contact@terraflora.app)"},
    ) as client:
        for batch_start in range(0, total, SAVE_EVERY):
            batch = to_fetch[batch_start:batch_start + SAVE_EVERY]
            tasks = [
                fetch_one_description(
                    client, sem, sp["scientific_name"], sp.get("common_name"), lang,
                    error_counts,
                )
                for sp in batch
            ]
            results = await asyncio.gather(*tasks)

            for sp, result in zip(batch, results):
                if result:
                    descriptions[sp["scientific_name"]] = result
                    hits += 1
            done += len(batch)

            elapsed = time.time() - t0
            eta = format_eta(elapsed, done, total)
            print(
                "  [{}] {}/{} done, {} hits | ETA: {}".format(
                    lang, done, total, hits, eta
                )
            )
            # Incremental save
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(descriptions, f, ensure_ascii=False, indent=2)

    total_all = len(species_list)
    total_hits = len(descriptions)
    print(
        "  [{}] Total: {}/{} descriptions ({:.1f}%)".format(
            lang, total_hits, total_all, total_hits / total_all * 100 if total_all else 0
        )
    )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Only process first N species")
    parser.add_argument("--resume", action="store_true", help="Skip already fetched species")
    args = parser.parse_args()

    if not INPUT_FILE.exists():
        print("ERROR: {} not found. Run 01_fetch_species.py first.".format(INPUT_FILE))
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        species_list = json.load(f)

    if args.limit:
        species_list = species_list[:args.limit]

    print("Loaded {} species".format(len(species_list)))

    print("\nFetching English descriptions...")
    await fetch_descriptions_for_lang(species_list, "en", OUTPUT_EN, args.resume)

    print("\nFetching Chinese descriptions...")
    await fetch_descriptions_for_lang(species_list, "zh", OUTPUT_ZH, args.resume)


if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    elapsed = time.time() - start
    print("\nDone in {:.0f}s ({:.1f} min)".format(elapsed, elapsed / 60))
