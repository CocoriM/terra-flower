# TerraFlora — Architecture

---

## 1. System diagram

```
┌─────────────────────────────────────────────────────────┐
│                       FRONTEND                          │
│   Next.js 14 (App Router) + TypeScript + Tailwind CSS   │
│   react-globe.gl (3D globe)                             │
│   Zustand (state) + NextAuth.js (auth)                  │
└─────────────────────┬───────────────────────────────────┘
                      │ REST API calls
┌─────────────────────▼───────────────────────────────────┐
│                       BACKEND                           │
│   Python FastAPI + Pydantic v2                          │
│   SQLAlchemy 2.0 (async) + Alembic (migrations)        │
│   httpx (async HTTP client for external APIs)           │
│   Pillow (image processing)                             │
│   boto3 (S3 uploads)                                    │
│   passlib + python-jose (auth)                          │
└──┬──────────┬──────────────┬────────────────────────────┘
   │          │              │
   ▼          ▼              ▼
┌──────┐  ┌────────┐  ┌──────────────────────────────────┐
│Postgres│ │ Redis  │  │ External APIs (read-only)        │
│(user  │  │(cache) │  │  • Trefle → plant taxonomy       │
│data   │  │        │  │  • GBIF → occurrence coordinates │
│only)  │  │        │  │  • PlantNet → AI verification    │
└──────┘  └────────┘  └──────────────────────────────────┘
   │
   ▼
┌──────────────────┐
│ S3-Compatible    │
│ Object Storage   │
│ (uploaded images)│
└──────────────────┘
```

---

## 2. Data ownership

### Stored in PostgreSQL (our data)
| Table | Contents |
|-------|----------|
| `users` | accounts, roles, credentials |
| `user_uploads` | submitted photos, AI results, moderation status |
| `approved_gallery_items` | photos approved for public gallery |

### Fetched from external APIs (not our data)
| Data | Source | Cache TTL |
|------|--------|-----------|
| Plant taxonomy, names, images | Trefle API | 24 hours |
| Occurrence lat/lng coordinates | GBIF API | 6 hours |
| AI plant identification | PlantNet API | not cached (per-request) |

### Key rule
We do NOT maintain a plant reference database. PostgreSQL only stores user-generated content. All plant information is fetched on demand from external APIs and cached in Redis.

---

## 3. Tech stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend framework | Next.js (App Router) | 14 |
| Frontend language | TypeScript | 5+ |
| Styling | Tailwind CSS | 3+ |
| 3D Globe | react-globe.gl | latest |
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
| Plant data | Trefle API | v1 |
| Occurrence data | GBIF API | v1 |
| Async HTTP client | httpx | 0.27+ |
| Image processing | Pillow | 10+ |
| Password hashing | passlib (bcrypt) | 1.7+ |
| JWT tokens | python-jose | 3.3+ |

---

## 4. Caching strategy

All external API responses are cached in Redis to reduce latency and avoid rate limits.

| Data | Redis key pattern | TTL |
|------|------------------|-----|
| Plant list | `trefle:list:{type}:{search}:{page}:{per_page}` | 24 hours |
| Plant detail | `trefle:plant:{trefle_id}` | 24 hours |
| Occurrences | `gbif:occurrences:{trefle_id}:{limit}` | 6 hours |

Cache flow for every external-API-backed endpoint:
1. Compute cache key from request params
2. Check Redis: if hit → return `json.loads(cached_value)` immediately
3. If miss → call external API via `httpx.AsyncClient`
4. Transform response to our schema
5. Store in Redis with TTL: `redis.setex(key, ttl, json.dumps(data))`
6. Return data

PlantNet responses are NOT cached because each request is a unique image.

---

## 5. Authentication flow

```
Register: email + password → bcrypt hash → store in DB → return JWT
Login: email + password → verify hash → return access token (1h) + refresh token (7d)
Protected request: Authorization: Bearer <access_token> → decode JWT → inject user into route
Role check: for moderation routes, verify user.role in ['moderator', 'admin']
```

JWT payload:
```json
{
  "sub": "user-uuid",
  "role": "contributor",
  "exp": 1700000000
}
```

---

## 6. Upload processing pipeline

```
User submits image
       │
       ▼
[1] Validate MIME (jpeg/png/webp only)
       │
       ▼
[2] Check file size ≤ 10MB
       │
       ▼
[3] Rate limit check (10/hr, 30/day per user)
       │
       ▼
[4] SHA-256 hash → check for duplicates in DB
       │
       ▼
[5] Compress to max 2MB (Pillow)
       │
       ▼
[6] Generate thumbnail (400px wide, JPEG q80, <100KB)
       │
       ▼
[7] Upload original + thumbnail to S3
       │
       ▼
[8] Create user_uploads record (status: pending)
       │
       ▼
[9] Background task: send to PlantNet API
       │
       ▼
[10] Store AI results (predicted_name, confidence, top_results)
       │
       ▼
[11] Apply decision rules → set ai_status
       │
       ├── approved_auto → also create approved_gallery_items record
       ├── needs_review → wait for moderator
       └── rejected_auto → done
       │
       ▼
[12] Return upload record with status to user
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
      Globe.tsx
      FilterBar.tsx
      SearchBar.tsx
      PlantDetailDrawer.tsx
      PlantGallery.tsx
      UploadModal.tsx
      UploadButton.tsx
      StatusBadge.tsx
      Navbar.tsx
    lib/
      api.ts                      ← axios instance + all API functions
      store.ts                    ← Zustand store
      types.ts                    ← TypeScript interfaces
    providers/
      SessionProvider.tsx
    next.config.js
    package.json
    tailwind.config.ts
    tsconfig.json

  backend/
    app/
      __init__.py
      main.py                     ← FastAPI app, CORS, router mounts
      config.py                   ← pydantic-settings, reads .env
      database.py                 ← SQLAlchemy async engine + session
      dependencies.py             ← get_db, get_current_user, get_redis
      models/
        __init__.py
        user.py
        upload.py
        gallery.py
      schemas/
        __init__.py
        user.py                   ← UserCreate, UserLogin, UserResponse
        upload.py                 ← UploadResponse
        plant.py                  ← Plant, OccurrencePoint
      routers/
        __init__.py
        auth.py                   ← POST register, login; GET me
        plants.py                 ← GET plants, detail, occurrences, gallery
        uploads.py                ← POST upload; GET my uploads; DELETE
        moderation.py             ← GET pending; POST approve/reject
        health.py                 ← GET health
      services/
        __init__.py
        trefle.py                 ← Trefle API client with Redis cache
        gbif.py                   ← GBIF API client with Redis cache
        plantnet.py               ← PlantNet API client
        storage.py                ← S3 upload/delete via boto3
        auth.py                   ← JWT + password hashing
    alembic/
    alembic.ini
    requirements.txt
    .env.example

  docker-compose.yml              ← Postgres + Redis for local dev
  README.md
```

---

## 8. S3 storage layout
```
terraflora-uploads/
  originals/{upload_uuid}.jpg
  thumbnails/{upload_uuid}_thumb.jpg
```

Images served via S3 public URL or CDN. Backend uses `boto3` to upload.

---

## 9. Error handling strategy

| Scenario | Behaviour |
|----------|-----------|
| Trefle API down | Return HTTP 503 with message "Plant data temporarily unavailable" |
| GBIF API down | Return HTTP 503 with message "Occurrence data temporarily unavailable" |
| PlantNet API down | Set `ai_status = 'needs_review'`, let moderator decide |
| Redis down | Bypass cache, call external API directly (slower but functional) |
| S3 upload fails | Return HTTP 500, do not create DB record |
| Invalid file type | Return HTTP 400 with "Only JPEG, PNG, and WebP images are accepted" |
| File too large | Return HTTP 400 with "File must be 10MB or smaller" |
| Rate limit exceeded | Return HTTP 429 with "Upload limit reached. Try again later." |
| Duplicate image | Return HTTP 409 with "This image has already been uploaded" |
| Unauthorised | Return HTTP 401 |
| Forbidden (wrong role) | Return HTTP 403 |
