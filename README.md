# TerraFlora 🌍🌿

An interactive 3D globe platform for exploring plant species around the world.

## What users can do

- **Browse** plants on a 3D Earth globe
- **Filter** by plant type — flowers, trees, or grasses
- **Click** markers to view plant details and occurrence locations
- **Search** for any plant by name
- **Upload** their own plant photos
- **AI verification** — PlantNet checks if the photo matches the plant
- **Community gallery** — approved photos appear for everyone to see

## How it works

Plant data is fetched from public biodiversity APIs (Trefle for taxonomy, GBIF for coordinates). We do not maintain our own plant database — we only store user accounts, uploaded photos, and moderation decisions.

```
User → 3D Globe → Click Marker → Plant Detail → Upload Photo → AI Verification → Gallery
```

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, react-globe.gl, Zustand |
| Backend | Python FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL (user data only) |
| Cache | Redis (external API responses) |
| Storage | S3-compatible (uploaded images) |
| Plant data | Trefle API |
| Occurrence data | GBIF API |
| AI identification | PlantNet API |

## Quick start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+
- Python 3.11+
- API keys: [Trefle](https://trefle.io/), [PlantNet](https://my.plantnet.org/)

### Setup
```bash
# Start Postgres and Redis
docker-compose up -d

# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
alembic upgrade head
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

1. **No plant database** — all plant data fetched from Trefle + GBIF, cached in Redis
2. **Globe is the homepage** — users land directly on the interactive globe
3. **AI-assisted, not AI-confirmed** — PlantNet provides suggestions, not guarantees
4. **Three tables only** — users, uploads, approved gallery items
5. **Upload pipeline** — 12-step process with validation, compression, AI check, and moderation
