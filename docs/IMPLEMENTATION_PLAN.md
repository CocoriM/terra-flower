# TerraFlora — Implementation Plan

Follow these phases in order. Each phase builds on the previous one.

---

## Phase 1 — Project scaffolding

### 1.1 Create monorepo
Create the full folder structure as shown in ARCHITECTURE.md section 7.

### 1.2 Docker Compose
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: terraflora
      POSTGRES_USER: terraflora
      POSTGRES_PASSWORD: terraflora
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

### 1.3 Backend dependencies
`backend/requirements.txt`:
```
fastapi==0.111.0
uvicorn[standard]==0.30.1
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
alembic==1.13.1
pydantic==2.7.0
pydantic-settings==2.3.0
httpx==0.27.0
redis[hiredis]==5.0.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
pillow==10.3.0
boto3==1.34.0
python-dotenv==1.0.1
```

### 1.4 Backend config
Create `backend/app/config.py` with `pydantic-settings` BaseSettings reading every env var from PROJECT_SPEC section 9.

### 1.5 Backend database
Create `backend/app/database.py`: async SQLAlchemy engine, session maker, declarative Base, `get_db()` dependency.

### 1.6 Backend models
Create SQLAlchemy models matching ALL tables in PROJECT_SPEC section 4:
- `models/plant.py` → `Plant`, `PlantDistributionPoint`, `PlantImage`
- `models/user.py` → `User`
- `models/upload.py` → `UserUpload`
- `models/gallery.py` → `ApprovedGalleryItem`

### 1.7 Alembic
Set up Alembic with async support. Generate initial migration with all 6 tables. Run `alembic upgrade head`.

### 1.8 Backend main app
Create `backend/app/main.py` with FastAPI, CORS, and all router mounts.

### 1.9 Frontend setup
```bash
npx create-next-app@14 frontend --typescript --tailwind --app --src-dir=false --import-alias="@/*"
cd frontend
npm install resium cesium zustand next-auth axios
npm install -D @types/cesium
```

**CesiumJS static assets setup (CRITICAL):**
CesiumJS requires Workers and static assets to be served from the public directory.
```bash
cp -r node_modules/cesium/Build/Cesium/Workers public/cesium/Workers
cp -r node_modules/cesium/Build/Cesium/Assets public/cesium/Assets
cp -r node_modules/cesium/Build/Cesium/Widgets public/cesium/Widgets
```
In `next.config.js`, set:
```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  // CesiumJS needs these
  env: {
    CESIUM_BASE_URL: '/cesium',
  },
};
module.exports = nextConfig;
```

### 1.10 Verify
- `docker-compose up -d` → Postgres + Redis running
- `alembic upgrade head` → 6 tables created
- `uvicorn app.main:app --reload` → FastAPI at localhost:8000
- `npm run dev` → Next.js at localhost:3000

---

## Phase 2 — Seed data pipeline (automated, 5,000–10,000 species)

This phase populates the database with thousands of plant species using automated scripts. All scripts are in `backend/scripts/` and save intermediate results to `backend/data/processed/` as JSON files, so each step can be re-run independently.

### 2.1 Script: Fetch species list from GBIF (`scripts/01_fetch_species.py`)

**Purpose:** Get the top 10,000 most observed plant species with full taxonomy.

**Implementation:**
1. Call GBIF occurrence facet API to get most observed species:
   ```
   GET https://api.gbif.org/v1/occurrence/search
     ?kingdom=Plantae&hasCoordinate=true
     &basisOfRecord=HUMAN_OBSERVATION
     &facet=speciesKey&facetLimit=10000&limit=0
   ```
2. Parse the `facets[0].counts` array → list of `{speciesKey, count}`.
3. For each speciesKey (add 100ms delay between requests to avoid rate limiting):
   ```
   GET https://api.gbif.org/v1/species/{speciesKey}
   ```
   Extract: `scientificName`, `canonicalName`, `family`, `genus`, `order`, `class`.
4. Fetch vernacular names:
   ```
   GET https://api.gbif.org/v1/species/{speciesKey}/vernacularNames
   ```
   Extract first English name (`language=eng`) and first Chinese name (`language=zho`).
5. Save to `backend/data/processed/species_list.json`:
   ```json
   [
     {
       "gbif_key": 5361080,
       "scientific_name": "Helianthus annuus",
       "canonical_name": "Helianthus annuus",
       "common_name_en": "Sunflower",
       "common_name_zh": "向日葵",
       "family": "Asteraceae",
       "genus": "Helianthus",
       "order": "Asterales",
       "class": "Magnoliopsida",
       "observation_count": 385000
     }
   ]
   ```
6. Print: "Fetched {N} species from GBIF"

**Expected runtime:** ~20 minutes for 10,000 species.

### 2.2 Script: Fetch descriptions from Wikipedia (`scripts/02_fetch_descriptions.py`)

**Purpose:** Get English and Chinese text descriptions for each species.

**Implementation:**
1. Read `species_list.json`.
2. For each species, call Wikipedia REST API:
   ```
   GET https://en.wikipedia.org/api/rest_v1/page/summary/{scientific_name_with_underscores}
   ```
   If 404: try `GET https://en.wikipedia.org/api/rest_v1/page/summary/{common_name_en}`
   If still 404: set `description_en = null`.
   If 200: extract `extract` field (plain text summary).
3. Repeat for Chinese Wikipedia:
   ```
   GET https://zh.wikipedia.org/api/rest_v1/page/summary/{scientific_name_with_underscores}
   ```
4. Add 50ms delay between requests. Wikipedia rate limit is generous (~200 req/s) but be polite.
5. Save to `backend/data/processed/descriptions.json`:
   ```json
   [
     {
       "scientific_name": "Helianthus annuus",
       "description_en": "Helianthus annuus is a large annual forb...",
       "description_zh": "向日葵是菊科向日葵属的植物..."
     }
   ]
   ```
6. Print: "Fetched descriptions for {N} / {total} species ({hit_rate}%)"

**Expected hit rate:** ~60-70% for English, ~30-40% for Chinese.
**Expected runtime:** ~60 minutes.

### 2.3 Script: Fetch images from Wikimedia Commons (`scripts/03_fetch_images.py`)

**Purpose:** Get CC-licensed reference images for each species.

**Implementation:**
1. Read `species_list.json`.
2. For each species, query Wikimedia Commons:
   ```
   GET https://commons.wikimedia.org/w/api.php
     ?action=query&generator=search
     &gsrsearch={scientific_name}
     &gsrnamespace=6
     &gsrlimit=3
     &prop=imageinfo
     &iiprop=url|extmetadata|size
     &iiurlwidth=800
     &format=json
   ```
3. From results, select the first image that has:
   - A CC license (CC0, CC BY, CC BY-SA, CC BY-NC-SA)
   - Width >= 400px
4. Extract: `thumburl` (resized URL), license, attribution from `extmetadata.Artist`.
5. If no Wikimedia result: check if the Wikipedia summary from step 2 had a `thumbnail.source` field and use that.
6. Save to `backend/data/processed/images.json`:
   ```json
   [
     {
       "scientific_name": "Helianthus annuus",
       "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/.../800px-Sunflower.jpg",
       "license": "CC BY-SA 4.0",
       "attribution": "Photo by John Smith"
     }
   ]
   ```
7. Print: "Found images for {N} / {total} species ({hit_rate}%)"

**Expected hit rate:** ~70-80%.
**Expected runtime:** ~40 minutes.

### 2.4 Script: Fetch distribution coordinates from GBIF (`scripts/04_fetch_distributions.py`)

**Purpose:** Get 50 lat/lng/elevation points per species for globe markers.

**Implementation:**
1. Read `species_list.json`.
2. For each species, fetch occurrences:
   ```
   GET https://api.gbif.org/v1/occurrence/search
     ?speciesKey={gbif_key}
     &hasCoordinate=true
     &basisOfRecord=HUMAN_OBSERVATION
     &limit=50
   ```
3. Extract from each record: `decimalLatitude`, `decimalLongitude`, `elevation` (nullable), `country`, `continent`.
4. Add 100ms delay between requests.
5. Save to `backend/data/processed/distributions.json`:
   ```json
   [
     {
       "scientific_name": "Helianthus annuus",
       "gbif_key": 5361080,
       "points": [
         {"lat": 34.05, "lng": -118.24, "elevation": 150, "country": "US", "continent": "NORTH_AMERICA"},
         {"lat": 48.86, "lng": 2.35, "elevation": 35, "country": "FR", "continent": "EUROPE"}
       ]
     }
   ]
   ```
6. Print: "Fetched distributions for {N} species, {total_points} total points"

**Expected output:** 10,000 species × 50 points = ~500,000 points.
**Expected runtime:** ~90 minutes.

**Alternative for speed:** Use the GBIF async download API (POST to `/v1/occurrence/download/request`) with a kingdom=Plantae predicate. This generates a full CSV download (several GB) which can be filtered offline. Much faster for large volumes but requires a GBIF account and takes 10-60 min to process on their servers.

### 2.5 Script: Classify plant types (`scripts/05_classify_types.py`)

**Purpose:** Assign `flower`, `tree`, or `grass` to each species.

**Implementation:**
1. Read `species_list.json`.
2. Apply the classification logic from PROJECT_SPEC section 10 (Step 5):
   - Match family against `TREE_FAMILIES` set → `"tree"`
   - Match family against `GRASS_FAMILIES` set → `"grass"`
   - Everything else → `"flower"`
3. Save to `backend/data/processed/classified.json` (species_list + `plant_type` field added).
4. Print type distribution: "Flowers: {N}, Trees: {N}, Grasses: {N}"

**Expected distribution:** ~60% flower, ~25% tree, ~15% grass (rough estimate).
**Expected runtime:** < 1 minute (pure local processing).

### 2.6 Script: Ingest to database (`scripts/06_ingest_to_db.py`)

**Purpose:** Load all processed data into PostgreSQL.

**Implementation:**
1. Read all processed JSON files.
2. For each species in `classified.json`:
   - Merge description from `descriptions.json` (by scientific_name)
   - Merge image from `images.json` (by scientific_name)
   - Insert into `plants` table
3. For each species, insert distribution points from `distributions.json` into `plant_distribution_points`.
4. For each species with an image, insert into `plant_images` as `image_type = 'reference'`.
5. Use batch inserts (SQLAlchemy `session.add_all()`) for performance.
6. Print summary:
   ```
   Inserted:
     Plants: 8,432
     Distribution points: 421,600
     Reference images: 6,105
   Plants with no description: 2,891 (34%)
   Plants with no image: 2,327 (28%)
   ```

**Expected runtime:** ~5 minutes.

### 2.7 Master script (`scripts/seed_all.sh`)
```bash
#!/bin/bash
set -e
echo "=== TerraFlora Seed Pipeline ==="
echo "Step 1/6: Fetching species from GBIF..."
python scripts/01_fetch_species.py
echo "Step 2/6: Fetching Wikipedia descriptions..."
python scripts/02_fetch_descriptions.py
echo "Step 3/6: Fetching Wikimedia images..."
python scripts/03_fetch_images.py
echo "Step 4/6: Fetching GBIF distributions..."
python scripts/04_fetch_distributions.py
echo "Step 5/6: Classifying plant types..."
python scripts/05_classify_types.py
echo "Step 6/6: Ingesting to database..."
python scripts/06_ingest_to_db.py
echo "=== Seed pipeline complete ==="
```

### 2.8 Verify
Run data quality checks from PROJECT_SPEC section 10:
```bash
psql -d terraflora -c "SELECT COUNT(*) FROM plants;"                    # expect 5000-10000
psql -d terraflora -c "SELECT COUNT(*) FROM plant_distribution_points;" # expect 250k-500k
psql -d terraflora -c "SELECT plant_type, COUNT(*) FROM plants GROUP BY plant_type;"
psql -d terraflora -c "SELECT COUNT(*) FROM plants WHERE hero_image_url IS NULL;"
psql -d terraflora -c "SELECT COUNT(*) FROM plants WHERE description IS NULL;"
```

---

## Phase 3 — Backend services

### 3.1 Auth service (`backend/app/services/auth.py`)
- `hash_password(password) -> str` — bcrypt via passlib
- `verify_password(plain, hashed) -> bool`
- `create_access_token(user_id, role) -> str` — JWT, exp from config
- `create_refresh_token(user_id) -> str`
- `decode_token(token) -> dict` — raises on invalid/expired

### 3.2 PlantNet service (`backend/app/services/plantnet.py`)

**Method: `get_plantnet_project(lat, lng) -> str`**
Implement the region detection logic exactly as in PROJECT_SPEC section 11.

**Method: `async def identify(image_bytes, lat, lng) -> dict`**
1. Determine regional project: `project = get_plantnet_project(lat, lng)`
2. POST to `https://my-api.plantnet.org/v2/identify/{project}?api-key={key}&lang=en&nb-results=5`
3. Multipart: `images` = image bytes, `organs` = `"auto"`
4. Parse response → return:
```python
{
    "best_match": "Helianthus annuus",
    "best_score": 0.91,
    "project_used": project,
    "results": [
        {"scientific_name": "Helianthus annuus", "common_names": ["Sunflower"], "score": 0.91, "family": "Asteraceae"},
        ...
    ]
}
```
5. On error: return `{"best_match": None, "best_score": 0, "results": [], "error": "..."}`

**Method: `async def match_with_database(ai_results, db_session) -> list[dict]`**
For each AI result, query our `plants` table by `scientific_name`.
Return enriched results with `matched_plant_id` and `matched_plant_image` from our DB.
If a species isn't in our DB, include it but set `matched_plant_id = None`.

### 3.3 Storage service (`backend/app/services/storage.py`)
- `upload_file(file_bytes, key, content_type) -> str` → S3 upload, return URL
- `delete_file(key)` → S3 delete

### 3.4 Dependencies (`backend/app/dependencies.py`)
- `get_db()` → async DB session
- `get_redis()` → Redis connection
- `get_current_user(token)` → decode JWT, return user or 401
- `require_moderator(user)` → 403 if not moderator/admin

---

## Phase 4 — Backend API routes

### 4.1 Pydantic schemas
Create schemas in `backend/app/schemas/`:
- `plant.py`: PlantSummary, PlantDetail, DistributionPoint, GlobeMarker, PlantListResponse
- `user.py`: UserCreate, UserLogin, UserResponse, TokenResponse
- `upload.py`: UploadResponse, AIResultItem, ConfirmRequest, ModerationAction

### 4.2 Auth router (`routers/auth.py`)
Per PROJECT_SPEC section 5.2: register, login, me.

### 4.3 Plants router (`routers/plants.py`)
Per PROJECT_SPEC section 5.1:
- `GET /api/plants` → query our DB with filters
- `GET /api/plants/{plant_id}` → full detail from our DB
- `GET /api/plants/{plant_id}/distributions` → from our DB
- `GET /api/plants/{plant_id}/gallery` → from our DB

### 4.4 Globe router (`routers/globe.py`)
- `GET /api/globe/markers` → aggregated markers endpoint (one point per plant, representative location)
  - Query: for each plant, select one distribution point (e.g., most common country centroid)
  - Cache in Redis with 1h TTL
  - Return compact marker array

### 4.5 Uploads router (`routers/uploads.py`)
Per PROJECT_SPEC section 5.3:
- `POST /api/uploads` → 14-step pipeline
- `POST /api/uploads/{upload_id}/confirm` → user confirms species
- `GET /api/uploads/me`
- `DELETE /api/uploads/{upload_id}`

The upload endpoint is the most complex. Follow the 14-step pipeline from PROJECT_SPEC section 5.3 exactly. Steps 8-13 can run in a FastAPI BackgroundTask, returning the upload record at step 12 with `ai_status='pending'`, then the frontend polls for results OR uses a second request.

**Alternative (simpler):** do steps 8-13 synchronously (PlantNet responds in ~2s). Return results in the same response. This is simpler and acceptable for MVP.

### 4.6 Moderation router (`routers/moderation.py`)
Per PROJECT_SPEC section 5.4: pending list, approve, reject.

### 4.7 Health router (`routers/health.py`)
Per PROJECT_SPEC section 5.5.

### 4.8 Verify
- `/docs` shows all routes
- `GET /api/plants` returns seeded plants
- `GET /api/globe/markers` returns one marker per plant
- `GET /api/plants/{id}/distributions` returns coordinates with elevation
- Register + login works
- Health endpoint returns all green

---

## Phase 5 — Frontend: CesiumJS globe

### 5.1 TypeScript types (`lib/types.ts`)
All interfaces from PROJECT_SPEC section 8.

### 5.2 Zustand store (`lib/store.ts`)
From PROJECT_SPEC section 7.

### 5.3 API client (`lib/api.ts`)
Axios instance with baseURL. Export typed functions for every backend endpoint.

### 5.4 CesiumGlobe component (`components/CesiumGlobe.tsx`)

**CRITICAL: dynamic import with ssr: false**
```typescript
const CesiumGlobeInner = dynamic(() => import('./CesiumGlobeInner'), { ssr: false });
```

Create `CesiumGlobeInner.tsx` that uses resium:
```tsx
import { Viewer, Entity, PointGraphics } from 'resium';
import { Ion, createWorldTerrainAsync, Cartesian3, Color } from 'cesium';

// Set Cesium Ion token
Ion.defaultAccessToken = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN!;

// Set base URL for Cesium static assets
window.CESIUM_BASE_URL = '/cesium';
```

**Globe setup:**
- `<Viewer>` with `terrainProvider` from `createWorldTerrainAsync()`
- Full screen, no default UI widgets (set all to false: animation, timeline, baseLayerPicker, etc.)
- Satellite imagery (default Bing Maps or Cesium Ion imagery)
- Terrain exaggeration: optionally set `scene.globe.terrainExaggeration = 1.5` for more dramatic terrain

**Markers:**
- For each marker from Zustand store, render `<Entity>` with `<PointGraphics>`
- Position: `Cartesian3.fromDegrees(marker.lng, marker.lat, marker.elevation + 100)` (offset above terrain)
- Colour: `Color.fromCssColorString(colorMap[marker.plant_type])`
- `pixelSize`: 8 (zoom-adaptive if possible)
- On click: set selected plant, open drawer

**Data loading:**
1. On mount: `GET /api/globe/markers` (single request)
2. Store in Zustand
3. Filter by `selectedPlantType` client-side

### 5.5 FilterBar (`components/FilterBar.tsx`)
Per PROJECT_SPEC section 6.4.

### 5.6 SearchBar (`components/SearchBar.tsx`)
Per PROJECT_SPEC section 6.5.
On result click: fly camera to plant location using `viewer.camera.flyTo({ destination: Cartesian3.fromDegrees(lng, lat, elevation + 5000) })`.

### 5.7 PlantDetailDrawer (`components/PlantDetailDrawer.tsx`)
Per PROJECT_SPEC section 6.6.
On open, also fetch `GET /api/plants/{id}/distributions` and render those as additional smaller markers on the globe for that specific plant.

### 5.8 Globe page (`app/page.tsx`)
Compose all components per PROJECT_SPEC section 6.2.

### 5.9 Verify
- Globe renders with real 3D terrain (zoom into the Alps, Himalayas → visible mountains)
- Plant markers appear on the globe
- Filters work (show/hide markers by type)
- Clicking a marker opens the drawer
- Search flies the camera to a plant location
- Drawer shows plant detail from our DB

---

## Phase 6 — Frontend: Upload & AI identification

### 6.1 UploadModal (`components/UploadModal.tsx`)
Multi-step modal per PROJECT_SPEC section 6.7.

**Step 1 state:** image selected, location provided, consent checked
**Step 2 state:** AI results received, showing suggestions
**Step 3 state:** user confirmed or rejected

Use a state machine or simple step counter:
```typescript
const [step, setStep] = useState<'upload' | 'results' | 'done'>('upload');
```

### 6.2 AIResultsPanel (`components/AIResultsPanel.tsx`)
- Receives `AIResult[]` as prop
- Renders each suggestion as a card:
  - Reference image from our DB (or placeholder if not in DB)
  - Common name (bold), scientific name (italic)
  - Confidence bar (visual, coloured by confidence level)
  - "This is it!" button (only for species in our DB)
  - Greyed out if `matched_plant_id == null` with label "Not in our database"
- "None of these match" button at bottom

### 6.3 ConfirmSpeciesPanel (`components/ConfirmSpeciesPanel.tsx`)
- Shown after user clicks "This is it!" on a suggestion
- Shows confirmation message based on confidence level
- Auto-approve message: "Photo approved! You can see it in the gallery."
- Review message: "Photo submitted for review. A moderator will check it."

### 6.4 Verify
- Upload modal opens from drawer
- User can select image and provide location
- After submit, AI results appear within ~3 seconds
- Suggestions show reference images from our DB
- Confirming a high-confidence match → photo appears in gallery
- "None of these" gracefully handles the case

---

## Phase 7 — Frontend: Auth, profile, moderation

### 7.1 Login + Register pages
Per PROJECT_SPEC sections. Simple email + password forms.

### 7.2 Navbar
Per PROJECT_SPEC section 6.11.

### 7.3 Profile page
Per PROJECT_SPEC section 6.8.

### 7.4 Moderation page
Per PROJECT_SPEC section 6.9.
Now includes side-by-side comparison: uploaded photo vs reference image of the confirmed plant species.

### 7.5 StatusBadge
Per PROJECT_SPEC section 6.10.

### 7.6 Verify
- Auth flow works end-to-end
- Profile shows upload history with correct statuses
- Moderation page works for approve/reject

---

## Phase 8 — Polish

### 8.1 Loading states
- Globe: spinner + "Exploring the Earth..." while terrain loads
- Drawer: skeleton while fetching plant detail
- AI identification: spinner + "Identifying your plant..." (~2-3 seconds)
- Gallery: skeleton image placeholders

### 8.2 Error handling
- API errors: toast notification
- PlantNet down: "Plant identification temporarily unavailable"
- Upload errors: specific messages per ARCHITECTURE.md section 8

### 8.3 Empty states
- Empty gallery: "No community photos yet. Upload yours!"
- No search results: "No plants found for '[query]'"
- AI no match: "We couldn't identify this plant. Try a clearer photo."
- No pending moderation: "All caught up!"

### 8.4 Responsive
- Desktop: drawer 420px right
- Tablet: drawer 350px right
- Mobile: drawer as bottom sheet (80% height)
- Upload modal: full-width on mobile

### 8.5 Accessibility
- Buttons: `aria-label`
- Filters: `role="group"`, `aria-pressed`
- Drawer: `role="dialog"`, focus trap
- Images: `alt` with plant name

---

## Verification checklist (final)

- [ ] Globe renders with real 3D terrain (mountains visible on zoom)
- [ ] Plant markers from our database appear on globe
- [ ] Markers positioned correctly with elevation
- [ ] Filters (all/flower/tree/grass) work
- [ ] Clicking marker opens plant detail drawer
- [ ] Drawer shows plant info + community gallery from our DB
- [ ] Search finds plants and flies camera there
- [ ] Registration and login work
- [ ] Upload modal works with reverse identification flow
- [ ] PlantNet returns species suggestions with regional context
- [ ] AI suggestions show reference images from our DB
- [ ] User can confirm a species
- [ ] High-confidence confirmations auto-approve to gallery
- [ ] Medium-confidence goes to moderation queue
- [ ] Moderation page shows pending with side-by-side comparison
- [ ] Moderator can approve/reject
- [ ] Approved photos appear in gallery
- [ ] Profile shows upload history
- [ ] Health endpoint returns all green
- [ ] Responsive on mobile
