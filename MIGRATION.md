# Migration Instructions — Update Existing Codebase

The codebase already has a working v1 built with react-globe.gl, Trefle API, and forward identification flow. We are NOT starting over. We are migrating to v2 with targeted changes.

Read `docs/PROJECT_SPEC.md` for the full v2 specification.

## DO NOT rebuild from scratch. Only make these specific changes:

---

## Change 1: Add 3 new database tables

The existing tables (`users`, `user_uploads`, `approved_gallery_items`) stay. Add 3 new tables:

- `plants` — our own plant data (see PROJECT_SPEC section 4)
- `plant_distribution_points` — coordinates with elevation
- `plant_images` — reference images per plant

Create a new Alembic migration for these 3 tables. Do not touch existing tables.

Also update `user_uploads` table:
- Remove `trefle_plant_id` column (if it exists)
- Add `confirmed_plant_id` (UUID FK to plants)
- Add `user_confirmed` (boolean, default false)
- Add `ai_project_used` (varchar)
- Rename `ai_predicted_name` to `ai_best_match_name` (if needed)

Create a new Alembic migration for these column changes.

---

## Change 2: Add plant models and routes

Create new SQLAlchemy models:
- `backend/app/models/plant.py` → Plant, PlantDistributionPoint, PlantImage

Create new router:
- `backend/app/routers/plants.py` → serves plants from OUR database (not Trefle)
  - `GET /api/plants` (query our DB with type/search/continent filters)
  - `GET /api/plants/{plant_id}`
  - `GET /api/plants/{plant_id}/distributions`
  - `GET /api/plants/{plant_id}/gallery`

Create new router:
- `backend/app/routers/globe.py` → `GET /api/globe/markers` (aggregated, one point per plant)

Remove any Trefle API service file if it exists. Remove GBIF runtime service if it exists. We no longer call these at runtime.

Mount the new routers in `main.py`.

---

## Change 3: Create seed data pipeline

Create these 6 scripts in `backend/scripts/` exactly as described in docs/IMPLEMENTATION_PLAN.md Phase 2:

- `01_fetch_species.py`
- `02_fetch_descriptions.py`
- `03_fetch_images.py`
- `04_fetch_distributions.py`
- `05_classify_types.py`
- `06_ingest_to_db.py`
- `seed_all.sh`

Create `backend/data/processed/` directory for intermediate JSON files.

---

## Change 4: Replace globe component (react-globe.gl → CesiumJS)

Install new packages:
```bash
cd frontend
npm uninstall react-globe.gl
npm install resium cesium
```

Copy Cesium static assets to public/:
```bash
mkdir -p public/cesium
cp -r node_modules/cesium/Build/Cesium/Workers public/cesium/
cp -r node_modules/cesium/Build/Cesium/Assets public/cesium/
cp -r node_modules/cesium/Build/Cesium/Widgets public/cesium/
```

Replace the existing Globe component (`components/Globe.tsx`) with a new `components/CesiumGlobe.tsx` using resium. See PROJECT_SPEC section 6.3 for exact implementation.

Update `app/page.tsx` to use the new component.

Update `next.config.js` to set `CESIUM_BASE_URL`.

---

## Change 5: Update upload flow (forward → reverse identification)

Modify `backend/app/routers/uploads.py`:
- `POST /api/uploads` no longer requires `trefle_plant_id`
- Instead: accept `image` + `latitude` + `longitude`
- After file processing, call PlantNet with regional project (see PROJECT_SPEC section 11)
- Match AI results against our `plants` table
- Return suggestions to frontend

Add new endpoint:
- `POST /api/uploads/{upload_id}/confirm` — user confirms which species

Modify `backend/app/services/plantnet.py`:
- Add `get_plantnet_project(lat, lng)` function (PROJECT_SPEC section 11)
- Add `match_with_database(ai_results, db_session)` function
- Update `identify()` to use regional project

Modify frontend `components/UploadModal.tsx`:
- Change from single-step to 3-step flow:
  - Step 1: upload image + location
  - Step 2: show AI suggestions (new `AIResultsPanel` component)
  - Step 3: user confirms species (new `ConfirmSpeciesPanel` component)

---

## Change 6: Update Zustand store and types

Update `lib/types.ts`:
- Change `Plant` interface: remove `trefle_id`, add `id` (UUID from our DB)
- Add `GlobeMarker` interface (with elevation)
- Add `AIResult` interface
- Update `UserUpload` interface (add `confirmed_plant_id`, `user_confirmed`)

Update `lib/store.ts`:
- Add `identificationResults` state
- Change markers to use our DB format

Update `lib/api.ts`:
- Remove any Trefle-related API calls
- Update plant endpoints to use our DB endpoints
- Add `confirmUpload()` function
- Add `fetchGlobeMarkers()` function

---

## What to keep untouched:
- Auth system (register, login, JWT, bcrypt) — no changes needed
- S3 storage service — no changes needed
- Moderation routes — minor updates only (field names)
- Frontend: FilterBar, SearchBar, Navbar, StatusBadge, Profile page, Login/Register pages — mostly keep, small field name updates
- Docker Compose — no changes
- Redis setup — no changes
- Error handling middleware — no changes

---

## Order of operations:
1. Database changes (new tables + column updates) → run migrations
2. New plant models + routes
3. Seed pipeline scripts (build all 6, run them to populate DB)
4. Update PlantNet service (add region detection + DB matching)
5. Update upload routes (reverse flow + confirm endpoint)
6. Replace globe component (react-globe.gl → CesiumJS)
7. Update UploadModal (3-step flow)
8. Update types, store, API client
9. Test everything
