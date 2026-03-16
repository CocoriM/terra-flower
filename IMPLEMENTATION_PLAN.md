# TerraFlora — Implementation Plan

Follow these phases in order. Each phase builds on the previous one.

---

## Phase 1 — Project scaffolding

### 1.1 Create monorepo
```
mkdir terraflora && cd terraflora
```
Create the full folder structure as shown in ARCHITECTURE.md section 7.

### 1.2 Docker Compose
Create `docker-compose.yml`:
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
Create `backend/requirements.txt`:
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
Create `backend/app/config.py` — use `pydantic-settings` `BaseSettings` class that reads from `.env`. Include every variable listed in PROJECT_SPEC.md section 9.

### 1.5 Backend database
Create `backend/app/database.py`:
- Create async SQLAlchemy engine from `DATABASE_URL`
- Create `async_sessionmaker`
- Create `Base = declarative_base()`
- Create `async def get_db()` generator for dependency injection

### 1.6 Backend models
Create SQLAlchemy models for all three tables exactly matching the SQL in PROJECT_SPEC.md section 4:
- `backend/app/models/user.py` → `User` model
- `backend/app/models/upload.py` → `UserUpload` model
- `backend/app/models/gallery.py` → `ApprovedGalleryItem` model

### 1.7 Alembic setup
```bash
cd backend
alembic init alembic
```
Configure `alembic/env.py` for async SQLAlchemy. Update `alembic.ini` with the database URL. Generate initial migration:
```bash
alembic revision --autogenerate -m "initial tables"
alembic upgrade head
```

### 1.8 Backend main app
Create `backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, plants, uploads, moderation, health

app = FastAPI(title="TerraFlora API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(plants.router, prefix="/api/plants", tags=["plants"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(moderation.router, prefix="/api/moderation", tags=["moderation"])
app.include_router(health.router, prefix="/api", tags=["health"])
```

### 1.9 Frontend setup
```bash
npx create-next-app@14 frontend --typescript --tailwind --app --src-dir=false --import-alias="@/*"
cd frontend
npm install react-globe.gl three zustand next-auth axios
npm install -D @types/three
```

### 1.10 Verify setup
- `docker-compose up -d` → Postgres + Redis running
- `cd backend && alembic upgrade head` → tables created
- `cd backend && uvicorn app.main:app --reload` → FastAPI at localhost:8000
- `cd frontend && npm run dev` → Next.js at localhost:3000
- Browse `http://localhost:8000/docs` → see Swagger UI

---

## Phase 2 — Backend services (external API clients)

### 2.1 Redis dependency
Create `backend/app/dependencies.py`:
- `get_redis()` → returns an `aioredis` / `redis.asyncio` connection from `REDIS_URL`
- `get_current_user(token)` → decodes JWT, queries DB for user, raises 401 if invalid
- `require_moderator(user)` → raises 403 if `user.role not in ['moderator', 'admin']`

### 2.2 Trefle service (`backend/app/services/trefle.py`)
Create class `TrefleService`:

**Method: `async def list_plants(self, redis, type_filter, search, page, per_page)`**
1. Compute cache key: `trefle:list:{type_filter}:{search}:{page}:{per_page}`
2. Check Redis. If hit, return parsed JSON.
3. If miss:
   - Build URL: `https://trefle.io/api/v1/plants` (or `/plants/search` if search is provided)
   - Add params: `token`, `page`, `per_page`, and any `filter[ligneous_type]` for tree
   - Call with `httpx.AsyncClient(timeout=10.0)`
   - Transform each item using `classify_plant_type()` (logic from PROJECT_SPEC section 3.1)
   - Cache result in Redis with 86400s TTL
4. Return transformed list

**Method: `async def get_plant(self, redis, trefle_id)`**
1. Cache key: `trefle:plant:{trefle_id}`
2. If miss: call `https://trefle.io/api/v1/plants/{trefle_id}?token=...`
3. Transform to full detail with description, regions, images
4. Cache 86400s. Return.

**Method: `def classify_plant_type(self, item) -> str`**
Implement the exact logic from PROJECT_SPEC section 3.1 plant type classification.

### 2.3 GBIF service (`backend/app/services/gbif.py`)
Create class `GBIFService`:

**Method: `async def get_occurrences(self, redis, scientific_name, limit=300)`**
1. Cache key: `gbif:occurrences:{scientific_name}:{limit}`
2. If miss:
   a. Resolve name: `GET https://api.gbif.org/v1/species/match?name={scientific_name}`
   b. Extract `usageKey`
   c. Fetch: `GET https://api.gbif.org/v1/occurrence/search?taxonKey={usageKey}&hasCoordinate=true&limit={limit}&basisOfRecord=HUMAN_OBSERVATION`
   d. Map each result to `{"lat", "lng", "country", "year"}`
3. Cache 21600s (6 hours). Return.

### 2.4 PlantNet service (`backend/app/services/plantnet.py`)
Create class `PlantNetService`:

**Method: `async def identify(self, image_bytes: bytes) -> dict`**
1. POST to `https://my-api.plantnet.org/v2/identify/all?api-key={key}`
2. Multipart form: `images` = image bytes, `organs` = `"auto"`
3. Return: `{"predicted_name", "confidence", "top_results"}`
4. On error/timeout: return `{"predicted_name": None, "confidence": 0, "top_results": [], "error": "..."}`

**Method: `def decide_status(self, confidence, predicted_name, expected_name) -> str`**
Apply rules from PROJECT_SPEC section 3.3 using threshold env vars.

### 2.5 Storage service (`backend/app/services/storage.py`)
Using `boto3`:
- `upload_file(file_bytes, key, content_type) -> str` → uploads to S3, returns public URL
- `delete_file(key)` → deletes from S3

Configure boto3 client with `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` from settings.

### 2.6 Auth service (`backend/app/services/auth.py`)
- `hash_password(password) -> str` using passlib bcrypt
- `verify_password(plain, hashed) -> bool`
- `create_access_token(user_id, role) -> str` using python-jose, exp = `JWT_ACCESS_EXPIRE_MINUTES`
- `create_refresh_token(user_id) -> str` using python-jose, exp = `JWT_REFRESH_EXPIRE_DAYS`
- `decode_token(token) -> dict` raises exception if invalid/expired

---

## Phase 3 — Backend API routes

### 3.1 Pydantic schemas
Create request/response schemas in `backend/app/schemas/`:

**`user.py`:**
- `UserCreate(email, password, display_name)`
- `UserLogin(email, password)`
- `UserResponse(id, email, display_name, role)`
- `TokenResponse(access_token, refresh_token, token_type)`

**`plant.py`:**
- `PlantSummary(trefle_id, common_name, scientific_name, plant_type, family, image_url, native_regions)`
- `PlantListResponse(plants: list[PlantSummary], page, per_page, total)`
- `OccurrencePoint(lat, lng, country, year)`
- `OccurrenceResponse(trefle_id, scientific_name, occurrences: list[OccurrencePoint], total_fetched)`

**`upload.py`:**
- `UploadResponse(id, trefle_plant_id, plant_common_name, ..., ai_status, moderation_status, ...)`
- `ModerationAction(reason: str | None)`

### 3.2 Auth router (`backend/app/routers/auth.py`)
Implement 3 endpoints exactly as specified in PROJECT_SPEC section 5.2.

### 3.3 Plants router (`backend/app/routers/plants.py`)
Implement 4 endpoints exactly as specified in PROJECT_SPEC section 5.1:
- `GET /` → `list_plants`
- `GET /{trefle_id}` → `get_plant`
- `GET /{trefle_id}/occurrences` → `get_occurrences`
- `GET /{trefle_id}/gallery` → query own DB

### 3.4 Uploads router (`backend/app/routers/uploads.py`)
Implement 3 endpoints exactly as specified in PROJECT_SPEC section 5.3.
The `POST /` endpoint follows the 12-step pipeline from PROJECT_SPEC section 5.3. Use `FastAPI.BackgroundTasks` for the PlantNet call (step 9).

### 3.5 Moderation router (`backend/app/routers/moderation.py`)
Implement 3 endpoints exactly as specified in PROJECT_SPEC section 5.4.
Use the `require_moderator` dependency.

### 3.6 Health router (`backend/app/routers/health.py`)
Implement as specified in PROJECT_SPEC section 5.5. Ping DB, Redis, and each external API.

### 3.7 Verify Phase 3
- All routes visible at `http://localhost:8000/docs`
- Can register a user and login
- Can call `GET /api/plants` and see Trefle data
- Can call `GET /api/plants/{id}/occurrences` and see GBIF coordinates
- Health endpoint returns all green

---

## Phase 4 — Frontend: Globe and browse

### 4.1 TypeScript types (`frontend/lib/types.ts`)
Define all interfaces from PROJECT_SPEC section 8.

### 4.2 Zustand store (`frontend/lib/store.ts`)
Implement the store from PROJECT_SPEC section 7 using `zustand/create`.

### 4.3 API client (`frontend/lib/api.ts`)
Create axios instance with `baseURL = process.env.NEXT_PUBLIC_API_URL`.
Add interceptor to attach JWT from session to Authorization header.
Export typed functions:
```typescript
fetchPlants(params) → GET /api/plants
fetchPlantDetail(trefleId) → GET /api/plants/{id}
fetchOccurrences(trefleId) → GET /api/plants/{id}/occurrences
fetchGallery(trefleId, page) → GET /api/plants/{id}/gallery
uploadPhoto(formData) → POST /api/uploads
fetchMyUploads(page) → GET /api/uploads/me
deleteUpload(id) → DELETE /api/uploads/{id}
fetchPendingUploads(page) → GET /api/moderation/pending
approveUpload(id, reason) → POST /api/moderation/{id}/approve
rejectUpload(id, reason) → POST /api/moderation/{id}/reject
login(email, password) → POST /api/auth/login
register(email, password, displayName) → POST /api/auth/register
```

### 4.4 Root layout (`frontend/app/layout.tsx`)
- Import `globals.css`
- Wrap children with `SessionProvider` (NextAuth) and any Zustand providers if needed
- Set page metadata: title "TerraFlora", description

### 4.5 Globe component (`frontend/components/Globe.tsx`)
Implement exactly as described in PROJECT_SPEC section 6.3:
- Dynamic import with `ssr: false` (CRITICAL)
- Earth texture and night sky background URLs
- pointsData from Zustand occurrences filtered by selectedPlantType
- Colour mapping per plant type
- onPointClick handler
- Data loading on mount with Promise.allSettled

### 4.6 FilterBar (`frontend/components/FilterBar.tsx`)
Implement as PROJECT_SPEC section 6.4.

### 4.7 SearchBar (`frontend/components/SearchBar.tsx`)
Implement as PROJECT_SPEC section 6.5. Use `setTimeout`/`clearTimeout` for 300ms debounce.

### 4.8 PlantDetailDrawer (`frontend/components/PlantDetailDrawer.tsx`)
Implement as PROJECT_SPEC section 6.6. Fetch plant detail and gallery on open.

### 4.9 PlantGallery (`frontend/components/PlantGallery.tsx`)
- Receives `trefle_id` as prop
- Calls `fetchGallery(trefle_id)`
- Renders 2-column grid of thumbnails
- Empty state: "No community photos yet. Be the first to upload!"

### 4.10 Globe page (`frontend/app/page.tsx`)
Compose all components as in PROJECT_SPEC section 6.2 component tree. This page should be the main entry point.

### 4.11 Verify Phase 4
- Globe renders with Earth texture
- Plants load from API and markers appear
- Clicking a marker opens the drawer
- Filter buttons hide/show markers by type
- Search finds plants and moves the globe

---

## Phase 5 — Frontend: Upload

### 5.1 UploadButton (`frontend/components/UploadButton.tsx`)
- Only renders if user is logged in (check Zustand `user`)
- Clicking opens upload modal via Zustand `openUploadModal()`

### 5.2 UploadModal (`frontend/components/UploadModal.tsx`)
Implement exactly as PROJECT_SPEC section 6.7:
- Drag-and-drop image area
- Preview
- Pre-filled plant name (read-only)
- Location text + "Use my location" button
- Consent checkbox
- Submit → POST multipart → show AI result → "Done" button

### 5.3 Verify Phase 5
- Logged-in user sees "Upload a Photo" button in drawer
- Upload modal works with file selection and preview
- Submit sends to backend, receives AI result
- Upload appears in gallery if auto-approved

---

## Phase 6 — Frontend: Auth pages

### 6.1 Login page (`frontend/app/login/page.tsx`)
- Centred card, email + password inputs, submit button
- Calls `login()`, stores token, redirects to `/`
- Link to `/register`

### 6.2 Register page (`frontend/app/register/page.tsx`)
- Centred card, display name + email + password, submit
- Calls `register()`, auto-login, redirect to `/`

### 6.3 Navbar (`frontend/components/Navbar.tsx`)
Implement as PROJECT_SPEC section 6.11.

### 6.4 Verify Phase 6
- Can register a new account
- Can login and see user name in navbar
- Logout works

---

## Phase 7 — Frontend: Profile and moderation

### 7.1 Profile page (`frontend/app/profile/page.tsx`)
Implement as PROJECT_SPEC section 6.8. Protected route.

### 7.2 Moderation page (`frontend/app/moderation/page.tsx`)
Implement as PROJECT_SPEC section 6.9. Protected, role-gated.

### 7.3 StatusBadge (`frontend/components/StatusBadge.tsx`)
Implement as PROJECT_SPEC section 6.10.

### 7.4 Verify Phase 7
- Profile shows user's uploads with correct status badges
- Moderation page shows pending uploads
- Approve/reject works and updates gallery

---

## Phase 8 — Polish

### 8.1 Loading states
- Globe: centred spinner + "Loading globe..." while initialising
- Drawer: skeleton loader while fetching plant detail
- Gallery: skeleton image placeholders
- Upload: progress spinner after submit

### 8.2 Error handling
- API errors: toast notification at bottom of screen
- External API down: "Plant data temporarily unavailable" message
- Upload errors: specific messages ("File too large", "Invalid format", "Rate limit")

### 8.3 Empty states
- No markers loaded: "Loading plants..." overlay on globe
- Empty gallery: "No community photos yet. Be the first to upload!"
- No search results: "No plants found for '[query]'"
- No pending moderation: "All caught up! No uploads pending review."

### 8.4 Responsive design
- Desktop (1024px+): drawer 420px right side
- Tablet (768–1023px): drawer 350px right side
- Mobile (< 768px): drawer becomes bottom sheet (80% height)
- Modals: full-width on mobile with padding

### 8.5 Accessibility
- All buttons: `aria-label`
- Filter buttons: `role="group"`, `aria-pressed`
- Drawer: `role="dialog"`, `aria-label="Plant details"`
- Modal: focus trap
- Images: `alt` text with plant name

---

## Verification checklist (final)

Before the project is complete, verify:

- [ ] Globe renders with plant markers at 30+ FPS
- [ ] Filters (all/flower/tree/grass) work correctly
- [ ] Clicking a marker opens plant detail drawer
- [ ] Drawer shows plant info + community gallery
- [ ] Search finds plants and moves globe
- [ ] Registration and login work
- [ ] Logged-in user can upload a photo
- [ ] Upload validates file type, size
- [ ] PlantNet AI returns prediction and confidence
- [ ] Auto-approved photos appear in gallery immediately
- [ ] Moderation page shows pending uploads
- [ ] Moderator can approve/reject
- [ ] Approved uploads appear in gallery
- [ ] Profile page shows user's upload history
- [ ] Health endpoint returns all green
- [ ] Responsive on mobile
