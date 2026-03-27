# TerraFlora — Claude Code Instructions

This file is automatically read at the start of every Claude Code session.

## Before writing any code, read these documents in order:

1. `docs/PROJECT_SPEC.md` — **single source of truth** for all features, APIs, schemas, components
2. `docs/ARCHITECTURE.md` — system design, tech stack, folder structure, data flow
3. `docs/IMPLEMENTATION_PLAN.md` — step-by-step build order

**PROJECT_SPEC.md always wins if there is a conflict.**

---

## What is TerraFlora?

A 3D globe web app with real terrain, dynamic day/night cycle, seasonal plant visualization, and atmospheric effects (aurora, ocean currents). Users explore 10,000+ plant species, filter by type and season, upload photos for AI identification, and contribute to a community gallery.

---

## Current status and priorities

### PRIORITY 0 — Fix CesiumJS compilation (BLOCKING)
CesiumJS fails to compile in Next.js due to webpack bundling issues with @zip.js/zip.js.
**This must be fixed before anything else works.**

Recommended fix approach:
- Do NOT import cesium source modules directly in Next.js
- Use the pre-built Cesium bundle: `node_modules/cesium/Build/Cesium/Cesium.js`
- In `next.config.js`, alias cesium to the pre-built bundle:
  ```js
  const path = require('path');
  config.resolve.alias.cesium = path.join(__dirname, 'node_modules/cesium/Build/Cesium/Cesium.js');
  ```
- If resium still fails with the alias, abandon resium and use CesiumJS directly:
  - Load Cesium via `<Script src="/cesium/Cesium.js" strategy="beforeInteractive" />` in `app/layout.tsx`
  - Access `window.Cesium` in a client component with `useRef` + `useEffect`
  - This bypasses all webpack issues because Cesium is loaded as a plain script tag
- Always delete `.next/` cache before retrying: `rm -rf .next`
- Current versions: cesium@1.125.0, resium@1.18.2, next@14.2.3, react@18.3.1

### PRIORITY 1 — Core plant globe (must work first)
- 3D globe with Cesium World Terrain
- 10,000 plant markers from our database
- Filter by flower/tree/grass
- Click marker → plant detail drawer
- Search plants → fly to location
- Upload photo → AI identification → confirm → gallery
- Auth (register/login)
- Profile page, moderation page

### PRIORITY 2 — Time & light effects (high impact, low effort)
These features use CesiumJS built-in capabilities. Do them in this order:

**2a. Day/night cycle + lighting**
- `viewer.scene.globe.enableLighting = true`
- Sun position calculated from the Cesium clock
- Dark side of Earth visible, cities not lit (we don't have city light tiles, that's OK)
- Day/night terminator line visible on the globe
- This is essentially 1 line of code but looks spectacular

**2b. Time slider UI**
- Add a horizontal time slider at the bottom of the globe page
- Slider controls `viewer.clock.currentTime`
- Range: full year (Jan 1 – Dec 31)
- As user drags, sun position changes → day/night shifts across the globe
- Show current month label above the slider: "January", "February", etc.
- Do NOT use CesiumJS's built-in timeline widget (it's ugly). Build a custom Tailwind slider.

**2c. Seasonal flower filtering**
- When user drags time slider to a month, only show plants that bloom in that month
- Requires: `bloom_season` field in our `plants` table
- Current state: bloom_season is mostly NULL in seed data
- Fix: create a script `scripts/07_fetch_bloom_seasons.py` that:
  - For each plant, queries Wikipedia or Wikidata for flowering months
  - Falls back to hemisphere-based estimation (Southern hemisphere months are offset by 6)
  - Stores as a JSON array in the DB, e.g. `[3, 4, 5]` for March–May
- Frontend: when time slider is at month M, filter markers to only show plants where `bloom_months` includes M
- Add a toggle: "Show all plants" vs "Show blooming now"

### PRIORITY 3 — Aurora borealis animation (medium effort, very impressive)
- Render aurora as animated particle ribbons near the polar regions
- Position: latitude 65°–75° N (and optionally S for aurora australis)
- Visual: green/blue/purple translucent curtain effect above the terrain
- Implementation options (in order of preference):
  1. CesiumJS `Primitive` with custom GLSL fragment shader — best quality, most control
  2. Animated billboard sprites positioned in an arc — simpler but less fluid
  3. A pre-rendered transparent video/GIF overlaid on the globe at polar coordinates
- Aurora should be visible when the globe is zoomed out, subtle when zoomed in
- Aurora intensity can be linked to the time slider (stronger in winter months = closer to solstice)
- This is the single most impressive visual feature for a demo

### PRIORITY 4 — Ocean current animation (high effort, very impressive)
- Animated particles flowing along major ocean current paths
- Data source: NASA OSCAR (Ocean Surface Current Analysis Real-time) or simplified static paths
- Simplified approach for MVP:
  - Define 10–15 major current paths as polyline coordinates (Gulf Stream, Kuroshio, etc.)
  - Animate small particles along these polylines using CesiumJS `CallbackProperty`
  - Particle color: blue-white, semi-transparent
  - Speed: visually smooth, not scientifically accurate
- Advanced approach (stretch):
  - Use a velocity field texture (wind/current data as UV vectors)
  - Render with a GPU particle system
- This is the hardest feature. Do it last. It's OK to ship without it.

### NOT building
- ~~Precipitation/rainfall visualization~~ — cut, too much effort for limited visual impact
- No landing page — globe IS the homepage
- No OAuth — email + password only
- No dark mode, no i18n in v1
- No image cropping UI

---

## Critical technical rules

### CesiumJS
- Must use `dynamic import` with `ssr: false` — WebGL crashes during SSR
- Use `createWorldTerrainAsync()` for 3D terrain
- Set `Ion.defaultAccessToken` from `NEXT_PUBLIC_CESIUM_ION_TOKEN`
- Markers include elevation: `Cartesian3.fromDegrees(lng, lat, elevation)`
- For lighting: `viewer.scene.globe.enableLighting = true`
- For time control: manipulate `viewer.clock.currentTime` with `JulianDate`

### Database
- Self-built PostgreSQL with 6 tables (plants, plant_distribution_points, plant_images, users, user_uploads, approved_gallery_items)
- NOT external API at runtime (except PlantNet for AI identification)
- GBIF, Wikipedia, Wikimedia used only during seed pipeline

### Upload flow (reverse identification)
- User uploads photo + location → PlantNet identifies → user confirms → gallery
- `POST /api/uploads` does NOT require a plant_id
- Backend selects PlantNet regional flora from user coordinates
- `POST /api/uploads/{id}/confirm` is where the user confirms the species

### Do not substitute
- Do not replace CesiumJS with any other globe library
- Do not replace FastAPI with Flask or Django
- Do not replace Zustand with Redux
- Do not hardcode AI thresholds (read from env vars)

---

## Code quality expectations

Write code at the level of a **competent junior developer**:
- Clear variable names, not over-engineered
- Comments that explain WHY, not WHAT
- No unnecessary abstractions — keep it simple
- Error handling that shows user-friendly messages
- TypeScript types for all props and API responses
- Tailwind for styling, no CSS modules or styled-components

---

## When modifying code

1. Check if the change contradicts PROJECT_SPEC.md
2. If it does, tell the user and suggest updating the spec first
3. If it doesn't, implement the change
4. After implementing, note which doc sections may need updating

## If migrating from v1

Read `MIGRATION.md` for targeted changes. Do NOT rebuild from scratch.
