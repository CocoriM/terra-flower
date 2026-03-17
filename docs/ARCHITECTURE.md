# TerraFlora — Architecture

---

## 1. System diagram

```
┌─────────────────────────────────────────────────────────┐
│                       FRONTEND                          │
│   Next.js 14 (App Router) + TypeScript + Tailwind CSS   │
│   CesiumJS via resium (3D globe with real terrain)      │
│   Zustand (state) + NextAuth.js (auth)                  │
└─────────────────────┬───────────────────────────────────┘
                      │ REST API calls
┌─────────────────────▼───────────────────────────────────┐
│                       BACKEND                           │
│   Python FastAPI + Pydantic v2                          │
│   SQLAlchemy 2.0 (async) + Alembic (migrations)        │
│   httpx (async HTTP for PlantNet API)                   │
│   Pillow (image processing)                             │
│   boto3 (S3 uploads)                                    │
│   passlib + python-jose (auth)                          │
└──┬──────────┬──────────────┬────────────────────────────┘
   │          │              │
   ▼          ▼              ▼
┌──────────┐ ┌───────┐ ┌────────────────────────────────┐
│PostgreSQL│ │ Redis │ │ External APIs                   │
│• plants  │ │(cache)│ │ • PlantNet → AI identification  │
│• distrib │ │       │ │ • Cesium Ion → 3D terrain tiles │
│• users   │ │       │ └────────────────────────────────┘
│• uploads │ └───────┘
│• gallery │     ┌──────────────────┐
└──────────┘     │ S3-Compatible    │
                 │ Object Storage   │
                 │ (uploaded images) │
                 └──────────────────┘
```

---

## 2. Data ownership

### Stored in PostgreSQL (our data — fully self-managed)
| Table | Contents |
|-------|----------|
| `plants` | curated plant taxonomy, names, descriptions |
| `plant_distribution_points` | lat/lng/elevation coordinates per plant |
| `plant_images` | reference and community images per plant |
| `users` | accounts, roles, credentials |
| `user_uploads` | submitted photos, AI results, user confirmations |
| `approved_gallery_items` | photos approved for public gallery |

### Fetched from external services (runtime)
| Service | Purpose | When called |
|---------|---------|-------------|
| PlantNet API | AI plant identification from uploaded photo | on each user upload |
| Cesium Ion | 3D terrain tile streaming | continuous during globe interaction |

### NOT fetched at runtime (seed pipeline only, one-time)
| Service | Purpose | When used |
|---------|---------|-----------|
| GBIF Species API | Top observed species, taxonomy, vernacular names | Seed script step 1 |
| GBIF Occurrence API | Distribution coordinates + elevation | Seed script step 4 |
| Wikipedia REST API | Plant descriptions in English + Chinese | Seed script step 2 |
| Wikimedia Commons API | CC-licensed reference images | Seed script step 3 |

These APIs are called once by the seed pipeline scripts, NOT at app runtime.

---

## 3. Tech stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend framework | Next.js (App Router) | 14 |
| Frontend language | TypeScript | 5+ |
| Styling | Tailwind CSS | 3+ |
| 3D Globe | CesiumJS via **resium** | latest |
| 3D Terrain | Cesium World Terrain (Cesium Ion) | — |
| State management | Zustand | 4+ |
| Auth (frontend) | NextAuth.js | 4+ |
| Backend framework | FastAPI | 0.111+ |
| Backend language | Python | 3.11+ |
| ORM | SQLAlchemy (async) | 2.0+ |
| Migrations | Alembic | 1.13+ |
| Database | PostgreSQL | 16 |
| Cache | Redis | 7+ |
| Object storage | S3-compatible (Cloudflare R2) | — |
| AI identification | PlantNet API | v2 |
| Async HTTP client | httpx | 0.27+ |
| Image processing | Pillow | 10+ |
| Password hashing | passlib (bcrypt) | 1.7+ |
| JWT tokens | python-jose | 3.3+ |

### Removed from previous version
| Removed | Reason |
|---------|--------|
| react-globe.gl | Replaced by CesiumJS for real 3D terrain |
| Trefle API | Replaced by self-built plant database |
| GBIF runtime calls | Replaced by one-time seed import |

---

## 4. Caching strategy

Redis is used for API response caching and rate limiting.

| Data | Redis key pattern | TTL |
|------|------------------|-----|
| Plant list queries | `plants:list:{type}:{search}:{page}` | 1 hour |
| Plant detail | `plants:detail:{plant_id}` | 1 hour |
| Globe markers | `globe:markers:{type}:{continent}` | 1 hour |
| Rate limit counters | `ratelimit:{user_id}:hour` / `ratelimit:{user_id}:day` | 1h / 24h |

Since plant data lives in our own DB, cache TTLs can be shorter (1 hour). The cache is mainly for reducing DB load on repeated queries, not for avoiding rate limits on external APIs.

PlantNet responses are NOT cached (each upload is unique).

Cesium terrain tiles are cached by the browser and Cesium's internal tile management — no Redis needed.

---

## 5. Authentication flow

```
Register: email + password → bcrypt hash → store in DB → return JWT
Login: email + password → verify hash → return access token (1h) + refresh token (7d)
Protected request: Authorization: Bearer <token> → decode JWT → inject user
Role check: moderation routes require role in ['moderator', 'admin']
```

---

## 6. Upload & identification pipeline (reverse flow)

```
User uploads photo + location
       │
       ▼
[1] Validate MIME (jpeg/png/webp)
       │
       ▼
[2] Check file size ≤ 10MB
       │
       ▼
[3] Rate limit check (10/hr, 30/day per user)
       │
       ▼
[4] SHA-256 hash → duplicate check
       │
       ▼
[5] Compress to max 2MB (Pillow)
       │
       ▼
[6] Generate thumbnail (400px wide, JPEG q80)
       │
       ▼
[7] Upload original + thumbnail to S3
       │
       ▼
[8] Determine region from lat/lng → PlantNet project code
       │
       ▼
[9] Send image to PlantNet API (regional flora)
       │
       ▼
[10] Receive top-5 species predictions
       │
       ▼
[11] Match predictions against our plant DB (by scientific_name)
       │
       ▼
[12] Create user_uploads record with AI results
       │
       ▼
[13] Return AI suggestions to frontend
       │
       ▼
User sees: "This looks like Sunflower (91%)"
       │
       ▼
[14] User confirms a species → POST /api/uploads/{id}/confirm
       │
       ├── score ≥ 0.85 + confirmed → approved_auto → gallery
       ├── score ≥ 0.50 + confirmed → needs_review → moderator
       └── user says "None of these" → not_identified
```

---

## 7. Folder structure

```
terraflora/
  frontend/
    app/
      layout.tsx
      page.tsx                    ← globe page
      login/page.tsx
      register/page.tsx
      profile/page.tsx
      moderation/page.tsx
      globals.css
    components/
      CesiumGlobe.tsx             ← CesiumJS via resium (was Globe.tsx)
      FilterBar.tsx
      SearchBar.tsx
      PlantDetailDrawer.tsx
      PlantGallery.tsx
      UploadModal.tsx              ← multi-step: upload → AI results → confirm
      AIResultsPanel.tsx           ← NEW: shows AI suggestions
      ConfirmSpeciesPanel.tsx      ← NEW: user picks correct species
      UploadButton.tsx
      StatusBadge.tsx
      Navbar.tsx
    lib/
      api.ts
      store.ts
      types.ts
      regions.ts                   ← region detection helper (optional)
    providers/
      SessionProvider.tsx
    public/
      cesium/                      ← CesiumJS static assets (Workers, etc.)
    next.config.js
    package.json
    tailwind.config.ts
    tsconfig.json

  backend/
    app/
      __init__.py
      main.py
      config.py
      database.py
      dependencies.py
      models/
        __init__.py
        user.py
        plant.py                   ← NEW: Plant, PlantDistributionPoint, PlantImage
        upload.py
        gallery.py
      schemas/
        __init__.py
        user.py
        plant.py
        upload.py
      routers/
        __init__.py
        auth.py
        plants.py
        globe.py                   ← NEW: optimised globe markers endpoint
        uploads.py
        moderation.py
        health.py
      services/
        __init__.py
        plantnet.py                ← PlantNet client + region detection
        storage.py
        auth.py
    alembic/
    alembic.ini
    scripts/
      01_fetch_species.py          ← fetch top 10k species from GBIF
      02_fetch_descriptions.py     ← fetch Wikipedia descriptions (en + zh)
      03_fetch_images.py           ← fetch Wikimedia Commons images
      04_fetch_distributions.py    ← fetch GBIF occurrence coordinates
      05_classify_types.py         ← assign flower/tree/grass types
      06_ingest_to_db.py           ← load all data into PostgreSQL
      seed_all.sh                  ← run entire pipeline
    data/
      processed/                   ← intermediate JSON files from seed scripts
    requirements.txt
    .env.example

  docker-compose.yml
  README.md
```

---

## 8. Error handling strategy

| Scenario | Behaviour |
|----------|-----------|
| PlantNet API down | Return HTTP 503 "Plant identification temporarily unavailable. Try again later." |
| PlantNet returns no results | Set `ai_status = 'not_identified'`, tell user "We couldn't identify this plant" |
| Cesium Ion unavailable | Globe renders without terrain (flat globe fallback) |
| Redis down | Bypass cache, query DB directly |
| S3 upload fails | Return HTTP 500, do not create DB record |
| Invalid file type | Return HTTP 400 "Only JPEG, PNG, and WebP images are accepted" |
| File too large | Return HTTP 400 "File must be 10MB or smaller" |
| Rate limit exceeded | Return HTTP 429 "Upload limit reached. Try again later." |
| Duplicate image | Return HTTP 409 "This image has already been uploaded" |
| Unauthorised | Return HTTP 401 |
| Forbidden (wrong role) | Return HTTP 403 |
| AI suggestion has no match in our DB | Show result greyed out with "Not in our database" label |
