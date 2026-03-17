"""
Step 5: Classify each species as flower, tree, or grass.

Uses family-based heuristics from the PROJECT_SPEC.

Output: backend/data/processed/classified.json

Flags:
  --limit N    Only process first N species
"""

import argparse
import json
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
INPUT_FILE = DATA_DIR / "species_list.json"
OUTPUT_FILE = DATA_DIR / "classified.json"

# Known tree families (covers most common trees)
TREE_FAMILIES = {
    "Fagaceae", "Pinaceae", "Betulaceae", "Sapindaceae", "Rosaceae",
    "Fabaceae", "Myrtaceae", "Cupressaceae", "Salicaceae", "Oleaceae",
    "Malvaceae", "Moraceae", "Juglandaceae", "Ulmaceae", "Platanaceae",
    "Magnoliaceae", "Lauraceae", "Meliaceae", "Anacardiaceae", "Arecaceae",
    "Taxaceae", "Araucariaceae", "Podocarpaceae", "Casuarinaceae",
}

# Known grass families
GRASS_FAMILIES = {
    "Poaceae", "Cyperaceae", "Juncaceae", "Typhaceae", "Restionaceae",
}


def classify_plant_type(family: str, order: str, genus: str) -> str:
    """Classify a plant as flower, tree, or grass based on taxonomy."""
    if family in GRASS_FAMILIES:
        return "grass"
    if family in TREE_FAMILIES:
        return "tree"
    if family == "Arecaceae":
        return "tree"
    return "flower"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Only process first N species")
    args = parser.parse_args()

    if not INPUT_FILE.exists():
        print("ERROR: {} not found. Run 01_fetch_species.py first.".format(INPUT_FILE))
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        species_list = json.load(f)

    if args.limit:
        species_list = species_list[:args.limit]

    print("Loaded {} species".format(len(species_list)))

    classified = []
    type_counts = {"flower": 0, "tree": 0, "grass": 0}

    for sp in species_list:
        plant_type = classify_plant_type(
            sp.get("family", ""),
            sp.get("order", ""),
            sp.get("genus", ""),
        )
        sp["plant_type"] = plant_type
        classified.append(sp)
        type_counts[plant_type] += 1

    print("\nClassification results:")
    for ptype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = count / len(classified) * 100
        print("  {}: {} ({:.1f}%)".format(ptype, count, pct))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(classified, f, ensure_ascii=False, indent=2)
    print("\nSaved to {}".format(OUTPUT_FILE))


if __name__ == "__main__":
    start = time.time()
    main()
    elapsed = time.time() - start
    print("Done in {:.1f}s".format(elapsed))
