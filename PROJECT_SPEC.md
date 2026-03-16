# TerraFlora — Product Specification

This document is the **single source of truth** for the TerraFlora system.
If any functionality changes, update this document first. Code follows the spec.

---

## 1. Core concept

A 3D globe web app where users explore plants worldwide. Plant data comes from external APIs (Trefle for plant info, GBIF for occurrence coordinates). Users can filter plants by type (flower / tree / grass), click markers on the globe to view plant details, and upload their own plant photos. Uploaded photos go through AI verification via PlantNet API. Approved photos appear in a community gallery for each plant.

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

### 3.1 Trefle API — plant information

- Base URL: `https://trefle.io/api/v1`
- Auth: token query param (`?token=TREFLE_API_KEY`)
- Rate limit: 120 requests/minute (free tier)
- Cache: Redis, 24-hour TTL

**Endpoints used:**

| Purpose | Endpoint | Key params |
|---------|----------|------------|
| List plants | `GET /plants` | `filter[ligneous_type]`, `page`, `per_page` |
| Search plants | `GET /plants/search` | `q` |
| Plant detail | `GET /plants/{id}` | — |
| Distributions | `GET /distributions/plants/{id}` | — |

**Field mapping — Trefle response → our UI:**

| UI element | Trefle field |
|------------|--------------|
| Common name | `common_name` |
| Scientific name | `scientific_name` |
| Hero image | `image_url` |
| Family | `family_common_name` |
| Description | `observations` or `bibliography` |
| Native regions | `distributions` → `native` array |

**Plant type classification logic:**

Trefle does not have a direct flower/tree/grass field. Derive it:

```
IF ligneous_type == "tree" OR growth_habit contains "Tree"
  → type = "tree"

ELSE IF growth_habit contains "Graminoid" OR "Grass"
  → type = "grass"

ELSE IF flower_color != null OR growth_habit contains "Herb" OR "Forb"
  → type = "flower"

ELSE
  → type = "flower" (default fallback)
```

### 3.2 GBIF API — occurrence coordinates

- Base URL: `https://api.gbif.org/v1`
- Auth: none (free and open)
- Rate limit: may receive HTTP 429 under heavy load
- Cache: Redis, 6-hour TTL

**Endpoints used:**

| Purpose | Endpoint | Key params |
|---------|----------|------------|
| Species lookup | `GET /species/match` | `name` (scientific name) → returns `usageKey` |
| Occurrences | `GET /occurrence/search` | `taxonKey`, `hasCoordinate=true`, `limit=300`, `basisOfRecord=HUMAN_OBSERVATION` |

**Fields extracted from each occurrence record:**
```json
{
  "lat": "decimalLatitude",
  "lng": "decimalLongitude",
  "country": "country",
  "year": "year"
}
```

**Clustering rule:**
Fetch max 300 points per species. On frontend, if total markers exceed 500, group into 5°×5° grid cells showing one marker per cell with a count badge. Expand clusters on zoom-in.

### 3.3 PlantNet API — AI verification

- Base URL: `https://my-api.plantnet.org/v2`
- Auth: API key query param (`?api-key=PLANTNET_API_KEY`)
- Free tier: 500 identifications/day

**Endpoint:**
```
POST /identify/all?api-key={key}
Content-Type: multipart/form-data
Form fields: images (file), organs ("auto")
```

**Response shape:**
```json
{
  "results": [
    {
      "score": 0.92,
      "species": {
        "scientificNameWithoutAuthor": "Rosa canina",
        "commonNames": ["Dog Rose"]
      }
    }
  ]
}
```

**Decision rules:**

| Condition | Result |
|-----------|--------|
| `score >= 0.70` AND top prediction matches user-selected plant | `approved_auto` |
| `score >= 0.40` but `< 0.70`, OR name mismatch | `needs_review` |
| `score < 0.40` | `rejected_auto` |

Thresholds are configurable via environment variables:
```
PLANTNET_AUTO_APPROVE_THRESHOLD=0.70
PLANTNET_MANUAL_REVIEW_THRESHOLD=0.40
```

**Fallback:** If PlantNet is unreachable, set `ai_status = "needs_review"` and let a moderator handle it.

---

## 4. Database schema (PostgreSQL — user data only)

We do NOT store plant reference data. Only user-generated content.

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
    trefle_plant_id INTEGER NOT NULL,
    plant_scientific_name VARCHAR(255) NOT NULL,
    plant_common_name VARCHAR(255),
    plant_type VARCHAR(20),
    image_url TEXT NOT NULL,
    thumbnail_url TEXT,
    image_hash VARCHAR(64),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location_text VARCHAR(500),
    country VARCHAR(100),
    continent VARCHAR(50),
    ai_predicted_name VARCHAR(255),
    ai_confidence DOUBLE PRECISION,
    ai_top_results JSONB,
    ai_status VARCHAR(30) DEFAULT 'pending',
    moderation_status VARCHAR(30) DEFAULT 'pending',
    moderation_reason TEXT,
    moderator_id UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    captured_at TIMESTAMP,
    submitted_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_uploads_plant ON user_uploads(trefle_plant_id);
CREATE INDEX idx_uploads_status ON user_uploads(moderation_status);
CREATE INDEX idx_uploads_user ON user_uploads(user_id);
```

### Table: `approved_gallery_items`
```sql
CREATE TABLE approved_gallery_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id UUID REFERENCES user_uploads(id) ON DELETE CASCADE,
    trefle_plant_id INTEGER NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    approved_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_gallery_plant ON approved_gallery_items(trefle_plant_id);
```

---

## 5. Backend API endpoints

### 5.1 Plant endpoints (proxy + cache external APIs)

#### `GET /api/plants`
Proxies to Trefle. Returns normalised plant list.
- Query params: `type` (flower|tree|grass|all), `search` (text), `page`, `per_page` (max 50)
- Cache key: `trefle:list:{type}:{search}:{page}:{per_page}`, TTL 24h
- Response:
```json
{
  "plants": [
    {
      "trefle_id": 123456,
      "common_name": "Sunflower",
      "scientific_name": "Helianthus annuus",
      "plant_type": "flower",
      "family": "Asteraceae",
      "image_url": "https://...",
      "native_regions": ["North America"]
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 340
}
```

#### `GET /api/plants/{trefle_id}`
Proxies to Trefle. Returns full plant detail.
- Cache key: `trefle:plant:{trefle_id}`, TTL 24h

#### `GET /api/plants/{trefle_id}/occurrences`
Proxies to GBIF. Returns lat/lng points.
- Query params: `limit` (default 300)
- Implementation: resolve scientific name → GBIF `species/match` → get `usageKey` → `occurrence/search`
- Cache key: `gbif:occurrences:{trefle_id}:{limit}`, TTL 6h
- Response:
```json
{
  "trefle_id": 123456,
  "scientific_name": "Helianthus annuus",
  "occurrences": [
    {"lat": 34.05, "lng": -118.24, "country": "US", "year": 2023}
  ],
  "total_fetched": 300
}
```

#### `GET /api/plants/{trefle_id}/gallery`
Queries own DB. Returns approved user photos.
- Query params: `page`, `per_page`
- Source: JOIN `approved_gallery_items` + `user_uploads`

### 5.2 Auth endpoints

#### `POST /api/auth/register`
- Body: `{ "email", "password", "display_name" }`
- Hash password with bcrypt, create user, return JWT

#### `POST /api/auth/login`
- Body: `{ "email", "password" }`
- Verify password, return access token (1h) + refresh token (7d)

#### `GET /api/auth/me`
- Auth: Bearer token required
- Returns user profile

### 5.3 Upload endpoints (authenticated)

#### `POST /api/uploads`
- Auth: required
- Content-Type: `multipart/form-data`
- Form fields: `image` (file), `trefle_plant_id` (int), `plant_scientific_name` (str), `plant_common_name` (str, optional), `plant_type` (str), `latitude` (float, optional), `longitude` (float, optional), `location_text` (str, optional)

**Processing pipeline (12 steps, in this exact order):**
1. Validate MIME type server-side: only `image/jpeg`, `image/png`, `image/webp`
2. Check file size ≤ 10 MB
3. Rate limit check: max 10 uploads/hour and 30/day per user (query DB)
4. Compute SHA-256 hash of file bytes, check DB for duplicate `image_hash`
5. Compress to max 2 MB using Pillow if larger
6. Generate thumbnail: 400px wide, JPEG quality 80, target < 100 KB
7. Upload original + thumbnail to S3 storage
8. Create `user_uploads` record with `ai_status='pending'`, `moderation_status='pending'`
9. **In background** (FastAPI `BackgroundTasks`): send image to PlantNet API
10. Store AI results: `ai_predicted_name`, `ai_confidence`, `ai_top_results`, `ai_status`
11. If `ai_status == 'approved_auto'`, also create `approved_gallery_items` record
12. Return the upload record with current status

#### `GET /api/uploads/me`
- Auth: required
- Returns current user's uploads, paginated

#### `DELETE /api/uploads/{upload_id}`
- Auth: required
- Rule: only own uploads with `moderation_status == 'pending'`

### 5.4 Moderation endpoints (moderator/admin only)

#### `GET /api/moderation/pending`
- Auth: role must be `moderator` or `admin`
- Returns paginated pending uploads with AI results

#### `POST /api/moderation/{upload_id}/approve`
- Body: `{ "reason": "..." }` (optional)
- Sets `moderation_status='approved'`, records `moderator_id` and `reviewed_at`
- Creates `approved_gallery_items` record

#### `POST /api/moderation/{upload_id}/reject`
- Body: `{ "reason": "..." }` (required)
- Sets `moderation_status='rejected'`, records reason, moderator_id, reviewed_at

### 5.5 Health endpoint

#### `GET /api/health`
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected",
  "trefle_api": "reachable",
  "gbif_api": "reachable",
  "plantnet_api": "reachable"
}
```

---

## 6. Frontend pages and components

### 6.1 Page structure
```
app/
  layout.tsx          — root layout, global styles, providers
  page.tsx            — globe page (main)
  login/page.tsx      — login form
  register/page.tsx   — registration form
  profile/page.tsx    — user upload history (protected)
  moderation/page.tsx — moderation dashboard (protected, admin/moderator only)
```

### 6.2 Globe page — component tree
```
<GlobePage>
  <Navbar />                   — top bar, logo, auth links
  <FilterBar />                — flower/tree/grass toggle buttons
  <SearchBar />                — plant name search with dropdown
  <Globe />                    — react-globe.gl 3D globe
  <PlantDetailDrawer />        — right-side panel on marker click
    <PlantInfo />              — name, scientific name, type badge, region, description
    <PlantGallery />           — approved user photos grid
    <UploadButton />           — opens upload modal (logged-in only)
  <UploadModal />              — photo upload form
</GlobePage>
```

### 6.3 Globe component
- Library: `react-globe.gl`
- **CRITICAL:** must use `dynamic(() => import('react-globe.gl'), { ssr: false })` — WebGL crashes during SSR
- Globe texture: `"//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"`
- Background: `"//unpkg.com/three-globe/example/img/night-sky.png"`
- Markers via `htmlElementsData` prop: each marker is a circular plant thumbnail image (32×32px, rounded, with a coloured border matching plant type)
- Each marker element shows the plant's `image_url` as a small circular thumbnail on the globe
- `htmlElement`: render a `<div>` containing an `<img>` with the plant's image, styled as a circle with a 2px border in the category colour
- Clicking a marker: fetch plant detail → open PlantDetailDrawer

**Data loading on mount:**
1. Call `GET /api/plants?per_page=50` to get initial plant list
2. For each plant, call `GET /api/plants/{id}/occurrences` in parallel (`Promise.allSettled`)
3. Aggregate all occurrence points into Zustand store
4. Show loading spinner until complete

### 6.4 FilterBar
- 4 pill buttons: All | 🌸 Flowers | 🌳 Trees | 🌿 Grass
- Active button gets filled background in category colour
- Stored in Zustand: `selectedPlantType`
- Filters `pointsData` on the globe client-side (no re-fetch needed)
- Position: fixed top, overlaying globe, semi-transparent backdrop

### 6.5 SearchBar
- Text input, top-left overlay on globe
- Debounced (300ms): calls `GET /api/plants?search={query}`
- Dropdown shows max 8 results
- On click: fetch occurrences for that plant, fly globe to first point via `globeRef.current.pointOfView({lat, lng, altitude: 1.5}, 1000)`

### 6.6 PlantDetailDrawer
- Visible when `selectedPlant !== null` in Zustand
- Right side, absolute positioned, 420px wide, full height, white background, shadow
- On mobile (< 768px): bottom sheet, 80% viewport height
- Content sections:
  1. Close (X) button
  2. Hero image from Trefle (`h-48 w-full object-cover`)
  3. Common name (`text-2xl font-bold`) + scientific name (`text-sm italic text-gray-500`)
  4. Type badge (coloured pill)
  5. "Native to: [regions]"
  6. Description paragraph
  7. Divider
  8. "Community Photos" heading + grid (2 columns, `gap-2`) from `GET /api/plants/{id}/gallery`
  9. "Upload a Photo" button (only if logged in) → opens UploadModal

### 6.7 UploadModal
- Full-screen overlay with centred modal (`max-w-lg`)
- Fields:
  - Image dropzone (drag-and-drop + click-to-browse)
  - Image preview after selection
  - Plant name (pre-filled, read-only)
  - Location text input
  - "Use my location" button → `navigator.geolocation.getCurrentPosition()`
  - Consent checkbox: "I confirm this is my own photo"
- Submit: disabled until image + consent checked
- On submit: POST `/api/uploads` as multipart
- Show spinner during upload
- On success: display AI result (predicted name, confidence, status)
- "Done" button closes modal and refreshes gallery

### 6.8 Profile page
- Protected route (redirect to /login if unauthenticated)
- User info card (name, email)
- Table: thumbnail, plant name, date, AI status badge, moderation status badge
- Delete button on rows with `moderation_status == 'pending'`

### 6.9 Moderation page
- Protected route (moderator/admin only)
- Cards for each pending upload:
  - Thumbnail (left)
  - "User selected: [plant]", "AI prediction: [name] ([X]%)", status badge (right)
  - Approve (green) / Reject (red) buttons
  - Reject shows text input for reason

### 6.10 StatusBadge (shared component)
- `approved` / `approved_auto` → green (`bg-green-100 text-green-800`)
- `needs_review` / `pending` → yellow (`bg-yellow-100 text-yellow-800`)
- `rejected` / `rejected_auto` → red (`bg-red-100 text-red-800`)

### 6.11 Navbar
- Transparent overlay on globe page, opaque white on other pages
- Left: "TerraFlora" logo text
- Right: logged in → display name + "Profile" + "Logout"; not logged in → "Login"

---

## 7. Zustand store
```typescript
interface AppState {
  selectedPlantType: 'all' | 'flower' | 'tree' | 'grass';
  setPlantType: (type: string) => void;
  plants: Plant[];
  setPlants: (plants: Plant[]) => void;
  occurrences: OccurrencePoint[];
  setOccurrences: (points: OccurrencePoint[]) => void;
  selectedPlant: Plant | null;
  setSelectedPlant: (plant: Plant | null) => void;
  isUploadModalOpen: boolean;
  openUploadModal: () => void;
  closeUploadModal: () => void;
  user: User | null;
  setUser: (user: User | null) => void;
}
```

---

## 8. TypeScript types
```typescript
interface Plant {
  trefle_id: number;
  common_name: string;
  scientific_name: string;
  plant_type: 'flower' | 'tree' | 'grass';
  family: string;
  image_url: string | null;
  native_regions: string[];
  description?: string;
}

interface OccurrencePoint {
  lat: number;
  lng: number;
  country: string;
  year: number;
  trefle_id: number;
  plant_type: 'flower' | 'tree' | 'grass';
  plant_name: string;
}

interface UserUpload {
  id: string;
  trefle_plant_id: number;
  plant_common_name: string;
  plant_scientific_name: string;
  plant_type: string;
  image_url: string;
  thumbnail_url: string;
  latitude: number | null;
  longitude: number | null;
  location_text: string | null;
  ai_predicted_name: string | null;
  ai_confidence: number | null;
  ai_status: 'pending' | 'approved_auto' | 'needs_review' | 'rejected_auto';
  moderation_status: 'pending' | 'approved' | 'rejected';
  moderation_reason: string | null;
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
TREFLE_API_KEY=
PLANTNET_API_KEY=
JWT_SECRET=
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=60
JWT_REFRESH_EXPIRE_DAYS=7
S3_ENDPOINT=
S3_BUCKET=terraflora-uploads
S3_ACCESS_KEY=
S3_SECRET_KEY=
PLANTNET_AUTO_APPROVE_THRESHOLD=0.70
PLANTNET_MANUAL_REVIEW_THRESHOLD=0.40

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXTAUTH_SECRET=
```

---

## 10. S3 storage structure
```
terraflora-uploads/
  originals/{upload_id}.jpg
  thumbnails/{upload_id}_thumb.jpg
```

---

## 11. UX rules
1. Globe is the homepage. No landing page, no splash screen.
2. Plant detail is a right-side drawer, not a new page.
3. Upload is a modal, not a new page.
4. Anonymous users can browse everything. Login only for upload.
5. AI result shown immediately after upload (~2 second PlantNet response).
6. Never say "AI confirms". Always "AI suggests" or "AI-assisted".

---

## 12. Non-functional requirements
- Globe: 30+ FPS on laptop with integrated GPU
- Initial load: < 4 seconds on 4G
- API cached responses: < 500ms
- API uncached external proxy: < 2 seconds
- Upload end-to-end: < 5 seconds including AI
- Max visible globe markers: 500 (cluster the rest)
- Responsive: desktop (1024px+), tablet (768px), mobile (375px+)
- Thumbnails: < 100 KB
- Stored originals: max 2 MB after compression
