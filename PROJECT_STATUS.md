# StyleSync — Project Status (So Far)

Last updated: 2026-03-25

This document summarizes what’s implemented in the repo today, how to run it locally, and what’s next.

---

## What’s working end-to-end

### 1) Auth flow (UI only)
- **Onboarding** (`/`): landing screen.
- **Login** (`/login`): UI only (no real auth yet).
- **Signup** (`/signup`): UI only (navigates to dashboard).

### 2) Dashboard (real color season display)
- **Dashboard** (`/dashboard`):
  - Links to all core modules.
  - Shows saved **color season** (loaded from backend + Supabase).

### 3) Wardrobe digitization (upload → AI tag → DB → UI)
- **Wardrobe** (`/wardrobe`):
  - Upload image (JPEG/PNG/WebP) → stores image in **Cloudinary**.
  - Runs AI tagging (default pipeline: HF caption → Groq JSON).
  - Saves wardrobe item to **Supabase** (`wardrobe_items`).
  - Displays uploaded wardrobe tiles in the UI.

#### Wardrobe management
- Click any wardrobe tile to open a detail modal:
  - **Edit attributes** and **Save** (PATCH to backend → Supabase update)
  - **Delete item** (DELETE to backend → Supabase delete)
  - **Re-run AI tagging** (default) and **Re-tag with Gemini Flash**
  - **Target item(s)** multi-select for Gemini tagging:
    - Supports co-ords by creating additional items from one photo (Top+Bottom, etc.).

### 4) Color analysis quiz (save → DB → UI)
- **Color quiz** (`/color-quiz`):
  - 3-question MVP quiz → outputs season (warm_spring / soft_autumn / soft_summer / cool_winter).
  - Saves season to Supabase `user_profiles`.
  - Dashboard loads and displays the saved season.

### 5) Shopping Intelligence — Utility Score MVP
- **Shopping** (`/shopping`):
  - “Test a purchase” form calls `POST /api/utility/score`.
  - Returns a utility score breakdown:
    - outfit potential (rule-based)
    - seasonal versatility
    - color match (based on saved color season)
    - cost-per-wear
  - Note: the table below is still mock rows (intentionally for now).

### 6) Outfit generation MVP (hypothetical purchase → 4 matches)
- **Outfits** (`/outfits`):
  - Input occasion/weather/vibe + a hypothetical purchase (candidate item).
  - Calls `POST /api/outfits/generate`.
  - Returns 4 ranked wardrobe matches with reasoning and an overall score.
  - Shows a note if a fallback was used (e.g., no type-compatible wardrobe matches).
  - Current MVP cards show the matched wardrobe item (not full 2–3 piece outfits yet).

### 7) Daily Trend Intelligence MVP (manual/local run → Supabase → UI)
- **Trends page** (`/trends`):
  - Loads trends from backend (`GET /api/trends`) instead of mock data.
- **Local pipeline**:
  - Run `python backend/run_trends_local.py` to scrape sources, extract candidates, cluster, and store trends in Supabase.
  - Trends are then served by the API and shown in the UI with wardrobe coverage.

---

## Backend API (FastAPI)

Backend root: `backend/`

### Core endpoints
- **Health**
  - `GET /health`

### Wardrobe
- `GET /api/wardrobe` — list wardrobe items
- `POST /api/wardrobe/upload` — upload image → Cloudinary → AI tag → Supabase insert
- `PATCH /api/wardrobe/{item_id}` — update attributes
- `DELETE /api/wardrobe/{item_id}` — delete item
- `POST /api/wardrobe/{item_id}/retag` — re-run tagging (default)  
  - `?engine=gemini` — Gemini Flash vision tagging  
  - `&targets=top,bottom,...` — multi-target tagging (may create additional items)

### User profile
- `GET /api/user/color-season`
- `PUT /api/user/color-season`

### Utility score
- `POST /api/utility/score`

### Outfits
- `POST /api/outfits/generate`

### Trends
- `GET /api/trends?limit=10`

---

## Supabase tables you should have

Run these SQL files once (Supabase → SQL Editor):
- `backend/supabase_wardrobe_items.sql`
- `backend/supabase_user_profiles.sql`
- `backend/supabase_trends.sql`

Tables created/used:
- `wardrobe_items`
- `user_profiles`
- `trends`
- `user_trend_matches`

---

## Environment variables (local)

File: `backend/.env` (ignored by git; do not commit)

Required:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `GROQ_API_KEY`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `HF_TOKEN` (HF captioning)
- `GEMINI_API_KEY` (Gemini Flash vision tagging)

---

## How to run locally

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Trends pipeline (manual/local, free-first)
```bash
cd backend
python run_trends_local.py
```

If Playwright errors (missing browser), run once:
```bash
cd backend
python -m playwright install chromium
```

---

## Known limitations (intentional MVP shortcuts)
- **No real user auth**: app uses a single default user id server-side.
- **Wardrobe AI tagging**:
  - Default: HF caption → Groq JSON (can be generic).
  - Gemini Flash is available and improved, especially with target item(s).
- **Outfits**:
  - Current MVP returns “purchase + 1 wardrobe match” cards (not full multi-piece outfits).
- **Trends**:
  - Stored structured trend metadata only (no raw HTML storage).
  - Manual/local run only; no scheduled GitHub Actions cron yet.
- **Utility score**:
  - Trend alignment + gap filling are placeholders in MVP scoring.

---

## Recommended next steps

1. **Outfit generation v2**: generate true multi-piece outfits (top + bottom + layer + shoes) and add a simple LLM judge.
2. **Shopping intelligence v2**:
   - Remove mock table rows.
   - Store scored candidate items in a new `shopping_recommendations` table.
3. **Trends v2**:
   - Add caching + scheduled runs (GitHub Actions 2AM).
   - Improve clustering consistency and labeling.
4. **Auth**:
   - Add Supabase Auth so wardrobes/profiles are user-scoped.

