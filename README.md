# TerraFlora 🌍🌿

An interactive 3D globe platform with real terrain for exploring plant species around the world.

## What users can do

- **Browse** plants on a 3D Earth with real terrain (mountains, valleys, basins)
- **Filter** by plant type — flowers, trees, or grasses
- **Click** markers to view plant details, distribution maps, and community photos
- **Search** for any plant by name
- **Upload** a plant photo and let AI identify the species
- **Confirm** the AI suggestion and contribute to the community gallery

## How it works

```
Upload photo + location
       ↓
AI identifies species (PlantNet, regional flora)
       ↓
"This looks like a Sunflower (91%)"
       ↓
User confirms → photo published to gallery
```

Plant taxonomy and distribution data are stored in our own curated database (seeded from GBIF). The 3D globe uses CesiumJS with Cesium World Terrain for real elevation rendering. AI identification uses PlantNet with regional flora selection for better accuracy.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, CesiumJS (resium), Zustand |
| Backend | Python FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL (plants + user data) |
| Cache | Redis |
| Storage | S3-compatible (uploaded images) |
| 3D Terrain | Cesium Ion (Cesium World Terrain) |
| AI identification | PlantNet API (with regional flora) |

## Quick start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+
- Python 3.11+
- API keys: [PlantNet](https://my.plantnet.org/), [Cesium Ion](https://cesium.com/ion/) (free accounts)

### Setup
```bash
# Start Postgres and Redis
docker-compose up -d

# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env              # fill in API keys
alembic upgrade head              # create tables
bash scripts/seed_all.sh          # run seed pipeline (~3.5 hours, one-time)
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Project documents

| File | Purpose |
|------|---------|
| `PROJECT_SPEC.md` | Product specification — **single source of truth** |
| `ARCHITECTURE.md` | System architecture, tech stack, folder structure |
| `IMPLEMENTATION_PLAN.md` | Step-by-step implementation guide |
| `AI_PROMPT.md` | Prompt for AI coding agents (Claude Code) |
| `README.md` | This file — project overview and quick start |

## Key design decisions

1. **Self-built plant database** — curated data in PostgreSQL, seeded from GBIF, not dependent on external APIs at runtime
2. **Real 3D terrain** — CesiumJS with Cesium World Terrain shows actual mountains and valleys
3. **Reverse identification** — user uploads photo → AI identifies species → user confirms (no guessing needed)
4. **Regional AI** — PlantNet queries use location-based flora projects for higher accuracy
5. **Elevation-aware markers** — plant markers positioned at real-world altitude on the 3D terrain
6. **AI-assisted, not AI-confirmed** — PlantNet provides suggestions, never guarantees
