# TerraFlora — Claude Code Instructions

This file is automatically read at the start of every Claude Code session.

## Before writing any code, read these documents in order:

1. `docs/PROJECT_SPEC.md` — **single source of truth** for all features, APIs, schemas, components
2. `docs/ARCHITECTURE.md` — system design, tech stack, folder structure, data flow
3. `docs/IMPLEMENTATION_PLAN.md` — step-by-step build order

**PROJECT_SPEC.md always wins if there is a conflict.**

---

## What is TerraFlora?

A 3D globe web app with real terrain (CesiumJS) where users explore 5,000–10,000 plant species worldwide. Users filter by type (flower/tree/grass), click markers to view details, and upload plant photos. AI (PlantNet) identifies the species from the photo — the user does NOT pre-select a species. Confirmed matches go to a community gallery.

---

## Critical rules (always follow these)

### Architecture
- **CesiumJS + resium** for the 3D globe (NOT react-globe.gl)
- **Self-built PostgreSQL database** with 6 tables (NOT external API at runtime)
- **PlantNet API** is the only external API called at runtime (for AI identification)
- **Cesium Ion** streams terrain tiles (free tier)
- **GBIF, Wikipedia, Wikimedia** are used only during the one-time seed pipeline

### Globe
- CesiumJS must use `dynamic import` with `ssr: false` — WebGL crashes during SSR
- Use `createWorldTerrainAsync()` for real 3D terrain
- Set `Ion.defaultAccessToken` from `NEXT_PUBLIC_CESIUM_ION_TOKEN`
- Plant markers include elevation: `Cartesian3.fromDegrees(lng, lat, elevation)`

### Upload flow (reverse identification)
- User uploads photo + location → AI identifies → user confirms species → gallery
- `POST /api/uploads` does NOT require a plant_id
- Backend selects PlantNet regional flora based on user coordinates (see PROJECT_SPEC section 11)
- `POST /api/uploads/{id}/confirm` is where the user confirms the species

### Seed data
- 6 automated scripts in `backend/scripts/` (01 through 06)
- Fetches from GBIF, Wikipedia, Wikimedia Commons
- Total pipeline: ~3.5 hours, run once
- Must complete before the app is functional

### Do not substitute
- Do not replace CesiumJS with any other globe library
- Do not replace FastAPI with Flask or Django
- Do not replace Zustand with Redux
- Do not hardcode AI thresholds (read from env vars)
- Do not create a Trefle API integration (removed)
- Do not call GBIF at runtime (seed only)

### Do not build
- No landing page (globe IS the homepage)
- No OAuth (email + password only in v1)
- No dark mode, no i18n in v1
- No image cropping UI

---

## Build order

Follow IMPLEMENTATION_PLAN.md phases strictly:

1. Scaffolding (monorepo, Docker, backend, frontend, Alembic)
2. Seed data pipeline (6 scripts → 5,000–10,000 plants in DB)
3. Backend services (PlantNet client, S3, auth)
4. Backend routes (auth, plants, globe, uploads, moderation, health)
5. Frontend globe (CesiumJS, filters, search, plant detail drawer)
6. Frontend upload (multi-step modal: upload → AI results → confirm)
7. Frontend auth + profile + moderation
8. Polish (loading, errors, responsive, accessibility)

---

## When modifying code

If the user asks you to change functionality:
1. Check if the change contradicts PROJECT_SPEC.md
2. If it does, tell the user and suggest updating the spec first
3. If it doesn't, implement the change
4. After implementing, note which doc sections may need updating

## If migrating from v1

If there is already existing code built with react-globe.gl, Trefle API, or forward identification flow, read `MIGRATION.md` for targeted changes. Do NOT rebuild from scratch — modify incrementally.
