#!/usr/bin/env bash
# Run all seed pipeline scripts in sequence.
# Usage: cd backend && bash scripts/seed_all.sh [--limit N] [--resume]
#
# Examples:
#   bash scripts/seed_all.sh                  # full run, ~3.5 hours
#   bash scripts/seed_all.sh --limit 100      # test run with 100 species
#   bash scripts/seed_all.sh --resume         # continue where you left off

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# Forward all args to each script
ARGS="$*"

echo "=========================================="
echo "  TerraFlora Seed Data Pipeline"
echo "  Args: ${ARGS:-<none>}"
echo "=========================================="
echo ""

echo "[1/6] Fetching species list from GBIF..."
python scripts/01_fetch_species.py $ARGS
echo ""

echo "[2/6] Fetching descriptions from Wikipedia..."
python scripts/02_fetch_descriptions.py $ARGS
echo ""

echo "[3/6] Fetching images from Wikipedia/Wikimedia..."
python scripts/03_fetch_images.py $ARGS
echo ""

echo "[4/6] Fetching distribution coordinates from GBIF..."
python scripts/04_fetch_distributions.py $ARGS
echo ""

echo "[5/6] Classifying plant types..."
python scripts/05_classify_types.py $(echo "$ARGS" | sed 's/--resume//g')
echo ""

echo "[6/6] Ingesting data into PostgreSQL..."
python scripts/06_ingest_to_db.py $(echo "$ARGS" | sed 's/--resume//g')
echo ""

echo "=========================================="
echo "  Seed pipeline complete!"
echo "=========================================="
