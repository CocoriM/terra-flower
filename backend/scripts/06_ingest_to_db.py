"""
Step 6: Ingest all processed data into PostgreSQL.

Reads all intermediate JSON files and inserts into:
  - plants
  - plant_distribution_points
  - plant_images

Flags:
  --limit N    Only ingest first N species
"""

import argparse
import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Union

import asyncpg
from dotenv import load_dotenv

# Load .env from the backend directory
load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
CLASSIFIED_FILE = DATA_DIR / "classified.json"
DESCRIPTIONS_EN_FILE = DATA_DIR / "descriptions_en.json"
DESCRIPTIONS_ZH_FILE = DATA_DIR / "descriptions_zh.json"
IMAGES_FILE = DATA_DIR / "images.json"
DISTRIBUTIONS_FILE = DATA_DIR / "distributions.json"


def get_asyncpg_url() -> str:
    """Get a plain postgresql:// URL suitable for asyncpg.connect()."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://terraflora:terraflora@localhost:5432/terraflora",
    )
    # asyncpg doesn't understand SQLAlchemy's "+asyncpg" dialect suffix
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url

BATCH_SIZE = 500


def trunc(value, maxlen):
    # type: (str, int) -> str
    """Truncate a string to maxlen, or return None if value is falsy."""
    if not value:
        return value
    return value[:maxlen]


def format_eta(elapsed: float, done: int, total: int) -> str:
    if done == 0:
        return "calculating..."
    rate = done / elapsed
    remaining = (total - done) / rate
    mins, secs = divmod(int(remaining), 60)
    return f"{mins}m{secs:02d}s"


def load_json(path: Path) -> Union[dict, list]:
    if not path.exists():
        print("  Warning: {} not found, skipping".format(path.name))
        return {} if path.name != "classified.json" else []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Only ingest first N species")
    args = parser.parse_args()

    # Load all data files
    print("Loading data files...")
    classified = load_json(CLASSIFIED_FILE)
    if not classified:
        print("ERROR: classified.json not found or empty. Run steps 01-05 first.")
        return

    if args.limit:
        classified = classified[:args.limit]

    descriptions_en = load_json(DESCRIPTIONS_EN_FILE)
    descriptions_zh = load_json(DESCRIPTIONS_ZH_FILE)
    images = load_json(IMAGES_FILE)
    distributions = load_json(DISTRIBUTIONS_FILE)

    print("  Species: {}".format(len(classified)))
    print("  English descriptions: {}".format(len(descriptions_en)))
    print("  Chinese descriptions: {}".format(len(descriptions_zh)))
    print("  Images: {}".format(len(images)))
    print("  Distributions: {} species with points".format(len(distributions)))

    # Connect to database
    db_url = get_asyncpg_url()
    print("Connecting to: {}".format(db_url.split("@")[-1]))  # log host only, not creds
    conn = await asyncpg.connect(db_url)

    try:
        # Clear existing seed data (in case of re-run)
        print("\nClearing existing seed data...")
        await conn.execute("DELETE FROM plant_images")
        await conn.execute("DELETE FROM plant_distribution_points")
        await conn.execute("""
            DELETE FROM plants WHERE id NOT IN (
                SELECT DISTINCT confirmed_plant_id FROM user_uploads
                WHERE confirmed_plant_id IS NOT NULL
            )
        """)

        # ---- Insert plants ----
        print("Inserting plants...")
        plants_inserted = 0
        total_plants = len(classified)
        t0 = time.time()

        for sp in classified:
            scientific_name = sp["scientific_name"]
            if not scientific_name:
                continue

            plant_id = uuid.uuid4()

            en_desc = descriptions_en.get(scientific_name, {})
            description = en_desc.get("extract")
            common_name_zh = sp.get("common_name_zh")

            img_data = images.get(scientific_name, {})
            hero_image_url = img_data.get("image_url")
            hero_image_attribution = img_data.get("attribution")

            await conn.execute(
                """
                INSERT INTO plants (
                    id, common_name, common_name_zh, scientific_name,
                    family, genus, plant_type, description,
                    hero_image_url, hero_image_attribution
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (scientific_name) DO UPDATE SET
                    common_name = EXCLUDED.common_name,
                    plant_type = EXCLUDED.plant_type,
                    description = EXCLUDED.description,
                    hero_image_url = EXCLUDED.hero_image_url,
                    updated_at = NOW()
                """,
                plant_id,
                sp.get("common_name", scientific_name),
                common_name_zh,
                scientific_name,
                sp.get("family"),
                sp.get("genus"),
                sp.get("plant_type", "flower"),
                description,
                hero_image_url,
                hero_image_attribution,
            )
            plants_inserted += 1

            if plants_inserted % BATCH_SIZE == 0:
                elapsed = time.time() - t0
                eta = format_eta(elapsed, plants_inserted, total_plants)
                print("  Plants: {}/{} | ETA: {}".format(plants_inserted, total_plants, eta))

        print("  Plants inserted: {}".format(plants_inserted))

        # ---- Build lookup from DB (handles upsert keeping existing IDs) ----
        print("Building scientific_name -> id lookup from DB...")
        rows = await conn.fetch("SELECT id, scientific_name FROM plants")
        plant_ids = {r["scientific_name"]: r["id"] for r in rows}
        print("  {} plants in lookup".format(len(plant_ids)))

        # ---- Insert distribution points ----
        print("Inserting distribution points...")
        points_inserted = 0
        species_to_insert = [sn for sn in distributions if sn in plant_ids]
        total_dist_species = len(species_to_insert)
        species_done = 0
        t0 = time.time()

        for scientific_name in species_to_insert:
            points = distributions[scientific_name]
            plant_id = plant_ids[scientific_name]

            for p in points:
                await conn.execute(
                    """
                    INSERT INTO plant_distribution_points (
                        id, plant_id, latitude, longitude, elevation_meters,
                        country, continent, source, source_record_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    uuid.uuid4(),
                    plant_id,
                    p["lat"],
                    p["lng"],
                    p.get("elevation"),
                    trunc(p.get("country"), 100),
                    trunc(p.get("continent"), 50),
                    "gbif",
                    trunc(str(p.get("gbif_id", "")), 100),
                )
                points_inserted += 1

            species_done += 1
            if species_done % BATCH_SIZE == 0:
                elapsed = time.time() - t0
                eta = format_eta(elapsed, species_done, total_dist_species)
                print("  Species: {}/{}, {} points | ETA: {}".format(
                    species_done, total_dist_species, points_inserted, eta
                ))

        print("  Distribution points inserted: {}".format(points_inserted))

        # ---- Insert plant images ----
        print("Inserting plant images...")
        images_inserted = 0

        for scientific_name, img_data in images.items():
            plant_id = plant_ids.get(scientific_name)
            if not plant_id:
                continue

            await conn.execute(
                """
                INSERT INTO plant_images (
                    id, plant_id, image_url, image_type, attribution, source
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.uuid4(),
                plant_id,
                img_data["image_url"],
                "reference",
                img_data.get("attribution"),
                img_data.get("source", "wikimedia"),
            )
            images_inserted += 1

        print("  Images inserted: {}".format(images_inserted))

        # Summary
        print("\n--- Ingestion Summary ---")
        row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM plants")
        print("  Total plants in DB: {}".format(row["cnt"]))
        row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM plant_distribution_points")
        print("  Total distribution points: {}".format(row["cnt"]))
        row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM plant_images")
        print("  Total images: {}".format(row["cnt"]))

        rows = await conn.fetch(
            "SELECT plant_type, COUNT(*) as cnt FROM plants GROUP BY plant_type ORDER BY cnt DESC"
        )
        print("  Type distribution:")
        for r in rows:
            print("    {}: {}".format(r["plant_type"], r["cnt"]))

    finally:
        await conn.close()


if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    elapsed = time.time() - start
    print("\nDone in {:.0f}s ({:.1f} min)".format(elapsed, elapsed / 60))
