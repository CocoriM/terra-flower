# Claude Code Prompt — TerraFlora

You are building TerraFlora. Read these documents before writing any code:

1. **PROJECT_SPEC.md** — single source of truth for all features, APIs, schemas, components
2. **ARCHITECTURE.md** — system design, tech stack, folder structure, data flow
3. **IMPLEMENTATION_PLAN.md** — step-by-step build order

PROJECT_SPEC.md always wins if there is a conflict.

---

## Build order

Follow the phases in IMPLEMENTATION_PLAN.md strictly:

1. **Scaffolding** — monorepo, Docker Compose, backend + frontend apps, Alembic migrations (6 tables)
2. **Seed data** — create plant JSON, fetch GBIF occurrences, run ingestion script
3. **Backend services** — PlantNet client (with region detection), S3 storage, auth (JWT + bcrypt)
4. **Backend routes** — auth, plants, globe, uploads (with reverse ID flow), moderation, health
5. **Frontend globe** — CesiumJS with resium, 3D terrain, markers, filters, search, plant detail drawer
6. **Frontend upload** — UploadModal (multi-step: upload → AI results → confirm species)
7. **Frontend auth, profile, moderation** — login, register, profile page, moderation dashboard
8. **Polish** — loading states, error handling, empty states, responsive, accessibility

---

## Critical rules

### We maintain our own plant database
All plant data lives in our PostgreSQL database (6 tables). We do NOT call Trefle API or GBIF at runtime. GBIF is used once during seeding only. The only external API called at runtime is PlantNet (for AI identification) and Cesium Ion (for terrain tiles).

### CesiumJS replaces react-globe.gl
Do NOT install or use react-globe.gl. Use CesiumJS via `resium` (React wrapper).

**CesiumJS setup requirements:**
- Install: `npm install resium cesium`
- Copy CesiumJS static assets (Workers, Assets, Widgets) to `public/cesium/`
- Set `window.CESIUM_BASE_URL = '/cesium'` before any Cesium imports
- Set `Ion.defaultAccessToken` from env var `NEXT_PUBLIC_CESIUM_ION_TOKEN`
- Use `createWorldTerrainAsync()` for real 3D terrain
- Dynamic import with `ssr: false` — CesiumJS uses WebGL, crashes during SSR

**Terrain is the key feature:** When users zoom in, they must see real mountain ridges, valleys, and basins. This is why we use CesiumJS with Cesium World Terrain.

**Markers use elevation:** Plant markers should be positioned at their real-world elevation using `Cartesian3.fromDegrees(lng, lat, elevation + offsetAboveTerrain)`.

### Reverse identification flow (user does NOT pre-select a species)
The old flow was: user picks a plant → uploads photo → AI checks if it matches.
The NEW flow is: user uploads photo + location → AI identifies the plant → user confirms → gallery.

This means:
- `POST /api/uploads` does NOT require a `plant_id` field
- The backend determines the user's region from lat/lng and sends to the correct PlantNet regional flora
- PlantNet returns top-5 species predictions
- Backend matches predictions against our plant database
- Frontend shows results with reference images from our DB
- User confirms one → `POST /api/uploads/{id}/confirm` with `confirmed_plant_id`

### PlantNet regional project is critical
Do not hardcode `project = "all"`. Use the region detection function from PROJECT_SPEC section 11 to select the correct regional flora based on user coordinates. This dramatically improves identification accuracy.

### Database has 6 tables, not 3
Previous version had 3 tables. Now there are 6:
- `plants` — our curated plant data
- `plant_distribution_points` — coordinates with elevation
- `plant_images` — reference and community images
- `users` — accounts
- `user_uploads` — submissions with AI results and user confirmation
- `approved_gallery_items` — published gallery photos

### Upload pipeline has 14 steps (not 12)
The pipeline now includes region detection (step 8), PlantNet call with regional project (step 9), and database matching (step 11). Follow the exact sequence in PROJECT_SPEC section 5.3.

### AI thresholds from environment variables
```
PLANTNET_AUTO_APPROVE_THRESHOLD=0.85
PLANTNET_REVIEW_THRESHOLD=0.50
```
Do not hardcode these values.

### Seed data is automated, not manual
The database needs 5,000–10,000 plant species to be useful. Do NOT manually create plant entries. Instead, build the 6 seed pipeline scripts described in IMPLEMENTATION_PLAN Phase 2. Each script fetches from a different source (GBIF, Wikipedia, Wikimedia), saves intermediate JSON, and the final script ingests everything into PostgreSQL. The full pipeline takes ~3.5 hours to run. All scripts are in `backend/scripts/` and intermediate data goes in `backend/data/processed/`.

### Auth
- bcrypt for passwords (passlib)
- python-jose for JWT
- Access token: 1 hour, refresh token: 7 days
- Moderation routes: moderator or admin role only

### Error handling
Per ARCHITECTURE.md section 8. PlantNet down → 503. No matches → "not_identified". Never crash on external API failure.

---

## What NOT to build

- No Trefle API integration (removed — we use our own DB)
- No GBIF runtime calls (seed import only)
- No react-globe.gl (replaced by CesiumJS)
- No landing page — globe IS the homepage
- No OAuth in v1 — email + password only
- No real-time notifications — user refreshes to check status
- No image cropping UI
- No dark mode in v1
- No multi-language in v1

---

## How to verify your work

After each phase, run the verification checks at the end of that phase in IMPLEMENTATION_PLAN.md. The final checklist is at the bottom of IMPLEMENTATION_PLAN.md.
