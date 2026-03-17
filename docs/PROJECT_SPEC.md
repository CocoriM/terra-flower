# TerraFlora — Product Specification

This document is the **single source of truth** for the TerraFlora system.
If any functionality changes, update this document first. Code follows the spec.

---

## 1. Core concept

A 3D globe web app with real terrain elevation (mountains, valleys, basins) where users explore plants worldwide. Users can filter plants by type (flower / tree / grass), click markers to view plant details, and upload plant photos. The system uses AI to identify the plant species from the photo (the user does NOT need to pre-select a species), cross-references with regional flora data, and publishes confirmed matches to a community gallery.

### Key changes from v1
- **True 3D terrain**: CesiumJS replaces react-globe.gl. Users see real mountain ridges and valleys when zooming in.
- **Self-built plant database**: we maintain our own curated PostgreSQL database instead of relying on Trefle API for plant information. GBIF is used only for initial seed data import, not live queries.
- **Reverse identification flow**: users upload a photo → AI identifies the plant → user confirms → gallery. Users never need to guess which species they're looking at.

---

## 2. Plant categories

Three categories supported in v1:

| Category | UI colour | Marker hex |
|----------|-----------|------------|
| flower | pink | `#F472B6` |
| tree | green | `#34D399` |
| grass | yellow | `#FBBF24` |

---

## 3. External API specifications

### 3.1 PlantNet API — AI plant identification (primary external dependency)

- Base URL: `https://my-api.plantnet.org/v2`
- Auth: API key query param (`?api-key=PLANTNET_API_KEY`)
- Free tier: 500 identifications/day

**Endpoint:**
```
POST /identify/{project}?api-key={key}&lang=en&nb-results=5
Content-Type: multipart/form-data
Form fields: images (file), organs ("auto")
```

**The `project` parameter is critical.** It selects a regional flora for more accurate results:
| User region | PlantNet project value |
|-------------|----------------------|
| Global (fallback) | `all` |
| Western Europe | `weurope` |
| North America | `namerica` |
| Central America | `the-caribbean` |
| South America | `south-america` |
| Tropical Africa | `tropical-africa` |
| North Africa | `north-africa` |
| Southern Africa | `southern-africa` |
| Eastern Mediterranean | `eastern-mediterranean` |
| South-East Asia | `southeast-asia` |
| East Asia | `east-asia` |
| Australia & NZ | `australia` |
| Pacific Islands | `pacific-islands` |
| Indian subcontinent | `indian-subcontinent` |

**Response shape:**
```json
{
  "bestMatch": "Ajuga genevensis L.",
  "results": [
    {
      "score": 0.90734,
      "species": {
        "scientificNameWithoutAuthor": "Ajuga genevensis",
        "commonNames": ["Blue bugleweed", "Blue bugle"],
        "family": {
          "scientificNameWithoutAuthor": "Lamiaceae"
        }
      },
      "gbif": { "id": "2927079" }
    }
  ],
  "remainingIdentificationRequests": 498
}
```

**How we use it (reverse identification flow):**
1. User uploads a photo + provides their location (GPS or manual)
2. Backend determines the PlantNet `project` from the user's coordinates
3. Backend sends image to PlantNet with that regional project
4. PlantNet returns top-5 species predictions with confidence scores
5. Backend matches predictions against our plant database
6. Frontend shows user: "This looks like [species X] (confidence: 91%)"
7. User confirms or rejects the suggestion
8. If confirmed AND confidence ≥ threshold → publish to gallery

**Decision rules for gallery admission:**
| Condition | Result |
|-----------|--------|
| `score >= 0.85` AND user confirms AND species exists in our DB | `approved_auto` → gallery |
| `score >= 0.50` AND user confirms | `needs_review` → moderator decides |
| `score < 0.50` OR user rejects all suggestions | `not_identified` → not published, user can retry |

Thresholds configurable via env vars:
```
PLANTNET_AUTO_APPROVE_THRESHOLD=0.85
PLANTNET_REVIEW_THRESHOLD=0.50
```

### 3.2 GBIF API — seed data import only

- Base URL: `https://api.gbif.org/v1`
- Used ONLY during database seeding, NOT at runtime
- We download occurrence data once and import into our database
- No Redis caching needed because we don't call GBIF at runtime

**Seed data usage:**
```
GET /occurrence/search?taxonKey={key}&hasCoordinate=true&limit=300&basisOfRecord=HUMAN_OBSERVATION
```
Extract: `decimalLatitude`, `decimalLongitude`, `elevation` (if available), `country`, `year`

### 3.3 Cesium Ion — 3D terrain tiles

- Service: Cesium Ion (free tier)
- Free tier: 5 GB storage + 100 GB streaming/month
- Terrain: Cesium World Terrain (asset ID 1) — global high-res elevation data
- Auth: Cesium Ion access token (free registration at cesium.com/ion)
- No Redis caching — Cesium handles tile streaming and caching internally

---

## 4. Database schema (PostgreSQL — self-built plant database + user data)

### Table: `plants`
```sql
CREATE TABLE plants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    common_name VARCHAR(255) NOT NULL,
    common_name_zh VARCHAR(255),
    scientific_name VARCHAR(255) NOT NULL UNIQUE,
    family VARCHAR(100),
    genus VARCHAR(100),
    plant_type VARCHAR(20) NOT NULL,          -- 'flower', 'tree', 'grass'
    description TEXT,
    habitat TEXT,
    bloom_season VARCHAR(100),
    hero_image_url TEXT,
    hero_image_attribution TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_plants_type ON plants(plant_type);
CREATE INDEX idx_plants_scientific ON plants(scientific_name);
```

### Table: `plant_distribution_points`
```sql
CREATE TABLE plant_distribution_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plant_id UUID REFERENCES plants(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    elevation_meters DOUBLE PRECISION,        -- for 3D positioning on terrain
    country VARCHAR(100),
    region VARCHAR(200),
    continent VARCHAR(50),
    source VARCHAR(50) DEFAULT 'gbif',        -- 'gbif', 'manual', 'community'
    source_record_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_distribution_plant ON plant_distribution_points(plant_id);
CREATE INDEX idx_distribution_location ON plant_distribution_points(continent, country);
```

### Table: `plant_images`
```sql
CREATE TABLE plant_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plant_id UUID REFERENCES plants(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    thumbnail_url TEXT,
    image_type VARCHAR(20) DEFAULT 'reference',  -- 'reference', 'community'
    attribution TEXT,
    source VARCHAR(50),                           -- 'wikimedia', 'seed', 'upload'
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_plant_images_plant ON plant_images(plant_id);
```

### Table: `users`
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255),
    auth_provider VARCHAR(50) DEFAULT 'email',
    role VARCHAR(20) DEFAULT 'contributor',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```
Roles: `contributor`, `moderator`, `admin`

### Table: `user_uploads`
```sql
CREATE TABLE user_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    -- image
    image_url TEXT NOT NULL,
    thumbnail_url TEXT,
    image_hash VARCHAR(64),
    -- location (from user's device or manual input)
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    elevation_meters DOUBLE PRECISION,
    location_text VARCHAR(500),
    country VARCHAR(100),
    continent VARCHAR(50),
    -- AI identification result
    ai_top_results JSONB,                     -- full top-5 from PlantNet
    ai_best_match_name VARCHAR(255),
    ai_best_match_score DOUBLE PRECISION,
    ai_project_used VARCHAR(50),              -- which regional flora was queried
    -- user confirmation
    confirmed_plant_id UUID REFERENCES plants(id),  -- which plant the user confirmed
    user_confirmed BOOLEAN DEFAULT FALSE,
    -- moderation
    ai_status VARCHAR(30) DEFAULT 'pending',  -- 'pending','approved_auto','needs_review','not_identified'
    moderation_status VARCHAR(30) DEFAULT 'pending', -- 'pending','approved','rejected'
    moderation_reason TEXT,
    moderator_id UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    -- timestamps
    captured_at TIMESTAMP,
    submitted_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_uploads_plant ON user_uploads(confirmed_plant_id);
CREATE INDEX idx_uploads_status ON user_uploads(moderation_status);
CREATE INDEX idx_uploads_user ON user_uploads(user_id);
```

### Table: `approved_gallery_items`
```sql
CREATE TABLE approved_gallery_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id UUID REFERENCES user_uploads(id) ON DELETE CASCADE,
    plant_id UUID REFERENCES plants(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    elevation_meters DOUBLE PRECISION,
    approved_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_gallery_plant ON approved_gallery_items(plant_id);
```

---

## 5. Backend API endpoints

### 5.1 Plant endpoints (served from our database)

#### `GET /api/plants`
**Purpose:** List plants from our database.
- Query params: `type` (flower|tree|grass|all), `search` (text), `continent`, `page`, `per_page` (max 50)
- Response:
```json
{
  "plants": [
    {
      "id": "uuid",
      "common_name": "Sunflower",
      "common_name_zh": "向日葵",
      "scientific_name": "Helianthus annuus",
      "plant_type": "flower",
      "family": "Asteraceae",
      "hero_image_url": "https://...",
      "distribution_count": 45
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 340
}
```

#### `GET /api/plants/{plant_id}`
**Purpose:** Get single plant detail with images and distribution summary.

#### `GET /api/plants/{plant_id}/distributions`
**Purpose:** Get lat/lng/elevation points for globe markers.
- Query params: `limit` (default 300)
- Response:
```json
{
  "plant_id": "uuid",
  "distributions": [
    {"lat": 34.05, "lng": -118.24, "elevation": 150, "country": "US"}
  ]
}
```

#### `GET /api/plants/{plant_id}/gallery`
**Purpose:** Get approved community photos.
- Query params: `page`, `per_page`

#### `GET /api/globe/markers`
**Purpose:** Optimised endpoint for initial globe load. Returns aggregated markers for all plants.
- Query params: `type` (flower|tree|grass|all), `continent`
- Returns one representative point per plant (centroid or most common location):
```json
{
  "markers": [
    {
      "plant_id": "uuid",
      "common_name": "Sunflower",
      "plant_type": "flower",
      "lat": 34.05,
      "lng": -118.24,
      "elevation": 150,
      "occurrence_count": 45
    }
  ]
}
```
This avoids loading thousands of individual distribution points on initial page load.

### 5.2 Auth endpoints

#### `POST /api/auth/register`
- Body: `{ "email", "password", "display_name" }`
- Hash password with bcrypt, create user, return JWT

#### `POST /api/auth/login`
- Body: `{ "email", "password" }`
- Return access token (1h) + refresh token (7d)

#### `GET /api/auth/me`
- Auth: Bearer token required

### 5.3 Upload & identification endpoints (authenticated)

#### `POST /api/uploads`
- Auth: required
- Content-Type: `multipart/form-data`
- Form fields: `image` (file), `latitude` (float, optional), `longitude` (float, optional), `location_text` (str, optional)
- Note: user does NOT select a plant. The AI identifies it.

**Processing pipeline (14 steps):**
1. Validate MIME type: only `image/jpeg`, `image/png`, `image/webp`
2. Check file size ≤ 10 MB
3. Rate limit: max 10/hour, 30/day per user
4. Compute SHA-256 hash, check for duplicates
5. Compress to max 2 MB (Pillow)
6. Generate thumbnail: 400px wide, JPEG q80, < 100 KB
7. Upload original + thumbnail to S3
8. Determine user's region from lat/lng → map to PlantNet project code
9. Send image to PlantNet API with the regional project
10. Receive top-5 predictions
11. Match predictions against our plant database (by scientific name)
12. Create `user_uploads` record with AI results
13. Apply decision rules → set `ai_status`
14. Return upload record with AI suggestions to frontend

#### `POST /api/uploads/{upload_id}/confirm`
- Auth: required (must be upload owner)
- Body: `{ "confirmed_plant_id": "uuid" }`
- User confirms which plant from the AI suggestions is correct
- If `ai_best_match_score >= AUTO_APPROVE_THRESHOLD` → `approved_auto`, create gallery item
- If `ai_best_match_score >= REVIEW_THRESHOLD` → `needs_review`
- Return updated upload record

#### `GET /api/uploads/me`
- Auth: required
- Returns current user's uploads with status

#### `DELETE /api/uploads/{upload_id}`
- Auth: required, own uploads only, `moderation_status == 'pending'`

### 5.4 Moderation endpoints (moderator/admin only)

#### `GET /api/moderation/pending`
- Auth: moderator or admin role
- Returns paginated pending uploads with AI results

#### `POST /api/moderation/{upload_id}/approve`
- Body: `{ "reason": "..." }` (optional)
- Creates `approved_gallery_items` record

#### `POST /api/moderation/{upload_id}/reject`
- Body: `{ "reason": "..." }` (required)

### 5.5 Health endpoint

#### `GET /api/health`
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected",
  "plantnet_api": "reachable",
  "cesium_ion": "reachable"
}
```

---

## 6. Frontend pages and components

### 6.1 Page structure
```
app/
  layout.tsx          — root layout, global styles, providers
  page.tsx            — globe page (main)
  login/page.tsx
  register/page.tsx
  profile/page.tsx
  moderation/page.tsx
```

### 6.2 Globe page — component tree
```
<GlobePage>
  <Navbar />
  <FilterBar />
  <SearchBar />
  <CesiumGlobe />                 — CesiumJS 3D globe with terrain
  <PlantDetailDrawer />
    <PlantInfo />
    <PlantGallery />
    <UploadButton />
  <UploadModal />                  — NEW: reverse identification flow
    <ImageUploader />
    <LocationInput />
    <AIResultsPanel />             — shows AI suggestions after upload
    <ConfirmSpeciesPanel />        — user picks the correct species
</GlobePage>
```

### 6.3 CesiumGlobe component
- Library: CesiumJS via `resium`
- **CRITICAL:** must use `dynamic(() => import(...), { ssr: false })` — WebGL crashes during SSR
- Terrain: Cesium World Terrain via Cesium Ion token
- When zoomed out: smooth globe with satellite imagery
- When zoomed in: real 3D terrain with mountains and valleys visible

**Resium component setup:**
```tsx
import { Viewer, Entity, PointGraphics, CameraFlyTo } from 'resium';
import { createWorldTerrainAsync, Cartesian3, Ion } from 'cesium';

Ion.defaultAccessToken = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;
```

**Markers:**
- Use resium `<Entity>` components with `<PointGraphics>` for each plant marker
- Position includes elevation: `Cartesian3.fromDegrees(lng, lat, elevation)`
- Marker colours per plant type (same hex as section 2)
- `onClick`: set selected plant → open PlantDetailDrawer

**Data loading:**
1. On mount: call `GET /api/globe/markers` (single request, aggregated)
2. Filter markers client-side by `selectedPlantType`
3. When a plant is selected and drawer opens: fetch full distribution points for that plant

### 6.4 FilterBar
- 4 pill buttons: All | 🌸 Flowers | 🌳 Trees | 🌿 Grass
- Active button has filled category colour background
- Filters markers client-side in Zustand store
- Fixed at top, overlaying globe

### 6.5 SearchBar
- Text input, top-left overlay
- Debounced (300ms): calls `GET /api/plants?search={query}` (our DB, no external API)
- Dropdown shows matching plants
- On click: fly globe to plant's primary distribution point

### 6.6 PlantDetailDrawer
- Right-side drawer, 420px, slides in when plant selected
- Mobile: bottom sheet (80% height)
- Content:
  1. Close (X) button
  2. Hero image (`h-48 w-full object-cover`)
  3. Common name + Chinese name + scientific name (italic)
  4. Type badge (coloured pill)
  5. Family & genus info
  6. "Native to: [regions]"
  7. Description / habitat
  8. Divider
  9. "Community Photos" grid from gallery endpoint
  10. "Upload a Photo" button (logged-in only)

### 6.7 UploadModal — reverse identification flow
This is the new core interaction. The flow is:

**Step 1: Upload image**
- Drag-and-drop or click to browse
- Image preview
- "Use my location" button → `navigator.geolocation.getCurrentPosition()`
- Optional manual location text
- Consent checkbox
- "Identify This Plant" button

**Step 2: AI identification results (shown after ~2 seconds)**
- Shows top suggestions from PlantNet:
  ```
  🌿 This looks like:
  1. Sunflower (Helianthus annuus) — 91% confidence ✅
  2. Black-eyed Susan (Rudbeckia hirta) — 5%
  3. Coneflower (Echinacea purpurea) — 2%
  ```
- Each suggestion shows: common name, scientific name, confidence bar, small reference image from our DB
- Only suggestions that match a plant in our database are shown
- "Yes, this is correct!" button next to top match (or any match)
- "None of these" button at bottom

**Step 3: Confirmation**
- If user confirms a match:
  - High confidence (≥ 0.85) → "Photo approved! It's now in the community gallery."
  - Medium confidence (≥ 0.50) → "Photo submitted for review. A moderator will check it soon."
- If user clicks "None of these":
  - "Sorry we couldn't identify this plant. You can try again with a different photo."

### 6.8 Profile page
- Protected route
- User info card
- Upload history table with status badges
- Each row shows: thumbnail, AI result, confirmed species, status

### 6.9 Moderation page
- Protected, moderator/admin only
- Cards for each pending upload
- Shows: uploaded image, AI prediction, confirmed plant, confidence
- Side-by-side: uploaded image vs reference image of the confirmed plant
- Approve / Reject buttons

### 6.10 StatusBadge
- `approved` / `approved_auto` → green
- `needs_review` / `pending` → yellow
- `rejected` / `not_identified` → red

### 6.11 Navbar
- Transparent on globe page, opaque on others
- Left: "TerraFlora" logo
- Right: auth state (profile link or login button)

---

## 7. Zustand store
```typescript
interface AppState {
  // Globe filter
  selectedPlantType: 'all' | 'flower' | 'tree' | 'grass';
  setPlantType: (type: string) => void;

  // Globe markers (aggregated, one per plant)
  markers: GlobeMarker[];
  setMarkers: (markers: GlobeMarker[]) => void;

  // Selected plant for detail drawer
  selectedPlant: Plant | null;
  setSelectedPlant: (plant: Plant | null) => void;

  // Upload modal
  isUploadModalOpen: boolean;
  openUploadModal: () => void;
  closeUploadModal: () => void;

  // Upload identification results
  identificationResults: AIResult[] | null;
  setIdentificationResults: (results: AIResult[] | null) => void;

  // Auth
  user: User | null;
  setUser: (user: User | null) => void;
}
```

---

## 8. TypeScript types
```typescript
interface Plant {
  id: string;
  common_name: string;
  common_name_zh: string | null;
  scientific_name: string;
  plant_type: 'flower' | 'tree' | 'grass';
  family: string;
  genus: string;
  description: string | null;
  habitat: string | null;
  hero_image_url: string | null;
  distribution_count: number;
}

interface GlobeMarker {
  plant_id: string;
  common_name: string;
  plant_type: 'flower' | 'tree' | 'grass';
  lat: number;
  lng: number;
  elevation: number;
  occurrence_count: number;
}

interface DistributionPoint {
  lat: number;
  lng: number;
  elevation: number | null;
  country: string;
}

interface AIResult {
  scientific_name: string;
  common_name: string;
  confidence: number;
  matched_plant_id: string | null;   // null if not in our DB
  matched_plant_image: string | null; // reference image from our DB
}

interface UserUpload {
  id: string;
  image_url: string;
  thumbnail_url: string;
  latitude: number | null;
  longitude: number | null;
  ai_best_match_name: string | null;
  ai_best_match_score: number | null;
  ai_top_results: AIResult[];
  confirmed_plant_id: string | null;
  user_confirmed: boolean;
  ai_status: 'pending' | 'approved_auto' | 'needs_review' | 'not_identified';
  moderation_status: 'pending' | 'approved' | 'rejected';
  submitted_at: string;
}

interface User {
  id: string;
  email: string;
  display_name: string;
  role: 'contributor' | 'moderator' | 'admin';
}
```

---

## 9. Environment variables
```env
# Backend
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/terraflora
REDIS_URL=redis://localhost:6379
PLANTNET_API_KEY=
JWT_SECRET=
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=60
JWT_REFRESH_EXPIRE_DAYS=7
S3_ENDPOINT=
S3_BUCKET=terraflora-uploads
S3_ACCESS_KEY=
S3_SECRET_KEY=
PLANTNET_AUTO_APPROVE_THRESHOLD=0.85
PLANTNET_REVIEW_THRESHOLD=0.50

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXT_PUBLIC_CESIUM_ION_TOKEN=
NEXTAUTH_SECRET=
```

---

## 10. Seed data strategy

### Target scale
**5,000 to 10,000 plant species** — covering the most commonly observed plants globally. This is achieved through a semi-automated pipeline, NOT manual curation.

### Pipeline overview
```
Step 1: GBIF Species API → fetch top observed plant species (taxonomy)
Step 2: Wikipedia API → fetch descriptions in English + Chinese
Step 3: Wikimedia Commons API → fetch CC-licensed reference images
Step 4: GBIF Occurrence API → fetch distribution coordinates + elevation
Step 5: Classification script → assign flower/tree/grass type
Step 6: Ingestion script → load everything into PostgreSQL
```

### Step 1 — Fetch species list from GBIF

Use the GBIF occurrence search facet to find the most frequently observed plant species:

```
GET https://api.gbif.org/v1/occurrence/search
  ?kingdom=Plantae
  &rank=SPECIES
  &hasCoordinate=true
  &basisOfRecord=HUMAN_OBSERVATION
  &facet=speciesKey
  &facetLimit=10000
  &limit=0
```

This returns the top 10,000 most observed plant species by occurrence count. For each `speciesKey`, fetch full taxonomy:

```
GET https://api.gbif.org/v1/species/{speciesKey}
```

Extract: `scientificName`, `canonicalName`, `kingdom`, `family`, `genus`, `order`, `class`, `rank`

Also fetch common names:
```
GET https://api.gbif.org/v1/species/{speciesKey}/vernacularNames
```
Extract English (`language=eng`) and Chinese (`language=zho`) common names.

**Rate limiting:** GBIF may rate limit at high volumes. Add 100ms delay between requests. For 10,000 species, this takes ~17 minutes.

### Step 2 — Fetch descriptions from Wikipedia

For each species, query Wikipedia for a summary:

```
GET https://en.wikipedia.org/api/rest_v1/page/summary/{scientific_name}
```

Response includes `extract` (plain text summary, ~2-3 sentences) and `thumbnail` (image URL).

For Chinese descriptions:
```
GET https://zh.wikipedia.org/api/rest_v1/page/summary/{scientific_name}
```

**Handling misses:** Not all species have Wikipedia articles. If no article found:
- Try searching by common name: `GET https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={common_name}+plant`
- If still no result, leave `description` as NULL in the database (can be filled later)
- Expected hit rate: ~60-70% for top 10,000 observed species

### Step 3 — Fetch images from Wikimedia Commons

For species where Wikipedia returned a thumbnail, use that URL directly.

For others, query Wikimedia Commons:
```
GET https://commons.wikimedia.org/w/api.php
  ?action=query
  &generator=search
  &gsrsearch={scientific_name}
  &gsrlimit=3
  &prop=imageinfo
  &iiprop=url|extmetadata
  &format=json
```

Extract: `url` (image URL), `extmetadata.LicenseShortName` (license type), `extmetadata.Artist` (attribution).

**Only use images with CC licenses** (CC0, CC BY, CC BY-SA). Store the `hero_image_attribution` field with proper credit.

**Alternative for bulk image sourcing:** Use `gbif-dl` Python package (by PlantNet team) to download occurrence images from GBIF directly. These include PlantNet and iNaturalist contributed photos with CC licenses.

### Step 4 — Fetch distribution coordinates from GBIF

For each species, fetch occurrence records with coordinates and elevation:

```
GET https://api.gbif.org/v1/occurrence/search
  ?speciesKey={speciesKey}
  &hasCoordinate=true
  &basisOfRecord=HUMAN_OBSERVATION
  &limit=50
  &fields=decimalLatitude,decimalLongitude,elevation,country,continent
```

**Limit to 50 points per species.** With 10,000 species × 50 points = 500,000 distribution points. This is enough for good globe coverage without overwhelming the database.

For bulk downloads of many species, use the GBIF async download API instead of paginating the search API:
```
POST https://api.gbif.org/v1/occurrence/download/request
Body: {
  "creator": "your_username",
  "predicate": {
    "type": "and",
    "predicates": [
      {"type": "equals", "key": "KINGDOM_KEY", "value": "6"},
      {"type": "equals", "key": "HAS_COORDINATE", "value": "true"},
      {"type": "equals", "key": "BASIS_OF_RECORD", "value": "HUMAN_OBSERVATION"}
    ]
  }
}
```
This creates a download job. When ready, download the CSV (may be several GB), then filter to our target species list and sample 50 records per species.

### Step 5 — Classify plant type (flower / tree / grass)

GBIF does not have a "flower/tree/grass" field. Use this classification logic:

```python
# Known tree families (non-exhaustive, covers most common trees)
TREE_FAMILIES = {
    "Fagaceae", "Pinaceae", "Betulaceae", "Sapindaceae", "Rosaceae",
    "Fabaceae", "Myrtaceae", "Cupressaceae", "Salicaceae", "Oleaceae",
    "Malvaceae", "Moraceae", "Juglandaceae", "Ulmaceae", "Platanaceae",
    "Magnoliaceae", "Lauraceae", "Meliaceae", "Anacardiaceae", "Arecaceae",
    "Taxaceae", "Araucariaceae", "Podocarpaceae", "Casuarinaceae"
}

# Known grass families
GRASS_FAMILIES = {
    "Poaceae", "Cyperaceae", "Juncaceae", "Typhaceae", "Restionaceae"
}

def classify_plant_type(family: str, order: str, genus: str) -> str:
    if family in GRASS_FAMILIES:
        return "grass"
    if family in TREE_FAMILIES:
        return "tree"
    # Palms are trees
    if family == "Arecaceae":
        return "tree"
    # Most remaining flowering plants → flower
    return "flower"
```

**Known limitations:** This is imperfect. Some Rosaceae are flowers (roses), some are trees (cherry). Some Fabaceae are herbs, some are trees. For the MVP, this heuristic is acceptable. A manual correction pass on the top 500 most visible species is recommended post-import.

### Step 6 — Ingestion into PostgreSQL

The ingestion script reads the processed data and inserts into the database:

1. Insert species into `plants` table (with taxonomy, description, type, image)
2. Insert distribution points into `plant_distribution_points` table
3. Insert reference images into `plant_images` table

**Expected database size after seeding:**
| Table | Estimated rows |
|-------|---------------|
| `plants` | 5,000 – 10,000 |
| `plant_distribution_points` | 250,000 – 500,000 |
| `plant_images` | 5,000 – 10,000 |

### Seed data scripts summary

| Script | Purpose | Runtime |
|--------|---------|---------|
| `scripts/01_fetch_species.py` | Fetch top species from GBIF | ~20 min |
| `scripts/02_fetch_descriptions.py` | Fetch Wikipedia descriptions (en + zh) | ~60 min |
| `scripts/03_fetch_images.py` | Fetch Wikimedia Commons images | ~40 min |
| `scripts/04_fetch_distributions.py` | Fetch GBIF occurrence coordinates | ~90 min |
| `scripts/05_classify_types.py` | Assign flower/tree/grass classification | ~1 min |
| `scripts/06_ingest_to_db.py` | Load all data into PostgreSQL | ~5 min |
| `scripts/seed_all.sh` | Run all steps in sequence | ~3.5 hours |

All scripts save intermediate results as JSON files in `backend/data/processed/` so that each step can be re-run independently without repeating earlier steps.

### Intermediate data files
```
backend/data/
  processed/
    species_list.json         ← Step 1 output: 10,000 species with taxonomy
    descriptions_en.json      ← Step 2 output: English descriptions
    descriptions_zh.json      ← Step 2 output: Chinese descriptions
    images.json               ← Step 3 output: image URLs + attribution
    distributions.json        ← Step 4 output: coordinates + elevation
    classified.json           ← Step 5 output: species with flower/tree/grass types
```

### Data quality checks (run after ingestion)
```sql
-- Check total plants
SELECT COUNT(*) FROM plants;  -- expect 5000-10000

-- Check distribution coverage
SELECT COUNT(*) FROM plant_distribution_points;  -- expect 250k-500k

-- Check type distribution
SELECT plant_type, COUNT(*) FROM plants GROUP BY plant_type;
-- flower should be largest, tree second, grass third

-- Check for plants with no distribution points
SELECT COUNT(*) FROM plants p
WHERE NOT EXISTS (SELECT 1 FROM plant_distribution_points d WHERE d.plant_id = p.id);
-- should be 0 or very few

-- Check for plants with no images
SELECT COUNT(*) FROM plants WHERE hero_image_url IS NULL;
-- acceptable if < 30% of total

-- Check for plants with no description
SELECT COUNT(*) FROM plants WHERE description IS NULL;
-- acceptable if < 40% of total
```

---

## 11. Region detection logic

Map user coordinates to PlantNet regional project:

```python
def get_plantnet_project(lat: float, lng: float) -> str:
    """Determine PlantNet flora project from coordinates."""
    if lat is None or lng is None:
        return "all"
    # North America
    if 15 <= lat <= 72 and -170 <= lng <= -50:
        return "namerica"
    # South America
    if -56 <= lat < 15 and -82 <= lng <= -34:
        return "south-america"
    # Western Europe
    if 36 <= lat <= 71 and -12 <= lng <= 25:
        return "weurope"
    # Eastern Mediterranean
    if 28 <= lat <= 45 and 25 <= lng <= 45:
        return "eastern-mediterranean"
    # North Africa
    if 15 <= lat <= 37 and -18 <= lng <= 35:
        return "north-africa"
    # Tropical Africa
    if -35 <= lat < 15 and -18 <= lng <= 52:
        return "tropical-africa"
    # Southern Africa
    if -35 <= lat <= -15 and 10 <= lng <= 41:
        return "southern-africa"
    # Indian subcontinent
    if 5 <= lat <= 37 and 60 <= lng <= 98:
        return "indian-subcontinent"
    # Southeast Asia
    if -11 <= lat <= 28 and 93 <= lng <= 153:
        return "southeast-asia"
    # East Asia
    if 20 <= lat <= 54 and 100 <= lng <= 150:
        return "east-asia"
    # Australia & NZ
    if -48 <= lat <= -10 and 110 <= lng <= 180:
        return "australia"
    # Fallback
    return "all"
```

---

## 12. UX rules
1. Globe is the homepage. No landing page.
2. Plant detail is a right-side drawer, not a new page.
3. Upload opens a modal with a multi-step flow: upload → AI identifies → user confirms.
4. User does NOT need to pre-select a plant species.
5. Anonymous users can browse everything. Login only for upload.
6. Never say "AI confirms". Always "AI suggests" or "This looks like".
7. Show AI confidence as a visual bar, not just a number.

---

## 13. Non-functional requirements
- Globe with terrain: 30+ FPS on laptop with integrated GPU
- Initial load: < 5 seconds on 4G (terrain tiles stream progressively)
- API responses: < 500ms for DB queries
- AI identification: < 5 seconds end-to-end
- Max 500 initial markers on globe (one per plant, not per occurrence)
- Responsive: desktop (1024px+), tablet (768px), mobile (375px+)
- Thumbnails: < 100 KB
- Stored originals: max 2 MB after compression
