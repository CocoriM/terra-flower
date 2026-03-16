# Claude Code Prompt — TerraFlora

You are building TerraFlora. Read these documents before writing any code:

1. **PROJECT_SPEC.md** — single source of truth for all features, APIs, schemas, components
2. **ARCHITECTURE.md** — system design, tech stack, folder structure, data flow
3. **IMPLEMENTATION_PLAN.md** — step-by-step build order

PROJECT_SPEC.md always wins if there is a conflict.

---

## Build order

Follow the phases in IMPLEMENTATION_PLAN.md strictly:

1. **Scaffolding** — monorepo, Docker Compose, backend app structure, frontend Next.js app, Alembic migrations
2. **Backend services** — Trefle client, GBIF client, PlantNet client, S3 storage, auth service (JWT + bcrypt)
3. **Backend routes** — auth, plants, uploads, moderation, health
4. **Frontend globe** — Globe component, FilterBar, SearchBar, PlantDetailDrawer, PlantGallery
5. **Frontend upload** — UploadModal, UploadButton
6. **Frontend auth** — Login page, Register page, Navbar
7. **Frontend profile & moderation** — Profile page, Moderation page, StatusBadge
8. **Polish** — loading states, error handling, empty states, responsive, accessibility

---

## Critical rules

### Do not create a plant database
All plant taxonomy, images, descriptions, and distribution data come from Trefle API and GBIF API. Cache in Redis. The only PostgreSQL tables are `users`, `user_uploads`, and `approved_gallery_items`.

### Do not substitute libraries
Use exactly the tech stack in ARCHITECTURE.md section 3. Do not replace react-globe.gl with Cesium, deck.gl, or anything else. Do not replace FastAPI with Flask or Django. Do not replace Zustand with Redux.

### react-globe.gl must use dynamic import
```typescript
const ReactGlobe = dynamic(() => import('react-globe.gl'), { ssr: false });
```
This is mandatory. WebGL will crash during server-side rendering without it.

### External API caching is mandatory
Every call to Trefle or GBIF must check Redis first. Never call an external API without checking the cache. See ARCHITECTURE.md section 4 for cache key patterns and TTLs.

### Plant type classification
Trefle does not have a flower/tree/grass field. You must derive it using the logic in PROJECT_SPEC.md section 3.1. Do not skip this — the filters depend on it.

### Upload pipeline has 12 steps
Follow the exact 12-step sequence in PROJECT_SPEC.md section 5.3. Do not skip validation steps. Use FastAPI BackgroundTasks for the PlantNet call.

### AI verification thresholds are from environment variables
Do not hardcode `0.70` and `0.40`. Read from `PLANTNET_AUTO_APPROVE_THRESHOLD` and `PLANTNET_MANUAL_REVIEW_THRESHOLD`.

### Auth
- Use bcrypt for password hashing (via passlib)
- Use python-jose for JWT
- Access token expires in 1 hour, refresh token in 7 days
- Moderation routes require role check: `moderator` or `admin`

### Error handling
Follow ARCHITECTURE.md section 9. Every external API failure must be handled gracefully with appropriate HTTP status codes and user-facing messages. Never let an external API failure crash the app.

---

## What NOT to build

- No landing page. The globe IS the homepage.
- No user registration via OAuth in v1. Email + password only.
- No real-time notifications. User checks status by refreshing.
- No image cropping or editing UI. Upload as-is.
- No admin panel for managing plants. Plants come from Trefle.
- No multi-language support in v1.
- No dark mode in v1.

---

## How to verify your work

After each phase, run the verification checks listed at the end of that phase in IMPLEMENTATION_PLAN.md. The final verification checklist is at the bottom of IMPLEMENTATION_PLAN.md.
