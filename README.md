# JalSakshya — Geospatial Watershed Evidence & Impact Workbench

Prototype for SIH 2026, problem statement **SIH26015** (Ministry of Rural Development,
Dept. of Land Resources). See [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md),
[`PROTOTYPE_PLAN.md`](PROTOTYPE_PLAN.md) and [`SOLUTION_DOCUMENT.md`](SOLUTION_DOCUMENT.md)
for the full specification and pitch.

JalSakshya links geo-tagged watershed photos to the 30 m satellite pixel beneath them,
compares before/after satellite trends against a **control area** (so a good or bad
monsoon doesn't get credited to a check dam), and produces a verdict —
**Corroborated / Mismatch / Inconclusive** — plus a Watershed Impact Index (WII) and a
PDF report, all from a map workbench.

## 1. Quick start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
python scripts/prepare_data.py     # tries real Landsat+DEM, auto-falls back to synthetic
python scripts/seed_db.py          # computes impact/WII/verdicts, writes the DB
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. Check `http://localhost:8000/api/health` and
the interactive API docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` (Vite dev server proxies `/api` and `/static`
to the backend on port 8000 — see `vite.config.js`).

## 2. Data modes: real vs. synthetic

`prepare_data.py` **tries real data first**: it fetches a Copernicus DEM tile and
Landsat 8/9 Collection 2 Level-2 seasonal composites (post-monsoon, 2018–2025) from the
Microsoft Planetary Computer STAC API, runs drainage analysis, computes NDVI/MNDWI/NDMI,
and places the 16 demo interventions on the real stream network.

If **any** step fails — no network, no clear scenes for the season, a missing library —
it automatically falls back to `make_synthetic_data.py`, which procedurally generates a
plausible watershed (terrain, drainage network via the same real `pysheds` pipeline,
vegetation/water/moisture fields with a shared year-to-year "rainfall shock" that the
control-area DiD is designed to cancel out) and deliberately includes:

- **11 corroborated** cases (photo claim matches satellite evidence)
- **3 mismatch** cases (e.g. photo shows a full pond, satellite shows no water signal)
- **2 inconclusive** cases (low AI-confidence photo reading)

Either way, `data/processed/meta.json` records `"source": "real_landsat"` or
`"source": "synthetic"`, and the frontend shows a **Demo Data** badge whenever synthetic
data is active. Force synthetic mode directly with:

```bash
python scripts/prepare_data.py --synthetic
```

**This build's demo dataset uses synthetic data** (see Known limitations below) — the
real-data code path (`LandsatProvider`, Copernicus DEM fetch) is implemented and was
verified to reach the Planetary Computer STAC API successfully, but a full 8-year fetch
was not exercised end-to-end for this submission due to how long the remote reads take.

## 3. Architecture

```
backend/
  app/
    main.py            FastAPI app, static file mounts, router registration
    config.py           bbox, years, thresholds, WII weights (all visible/configurable)
    db.py, models.py    SQLite via SQLAlchemy (Intervention, Photo, Impact)
    routers/            layers, interventions, photos, analysis, reports
    services/
      providers/        SatelliteProvider interface: LandsatProvider (real),
                         SrishtiDrishtiProvider (documented stub)
      indices.py         NDVI / MNDWI / NDMI formulas + LULC classification
      drainage.py         DEM -> pysheds -> streams/watershed/slope
      impact.py           zone sampling, control-pixel selection, DiD, WII
      verification.py     photo vs. satellite verdict rules (3 states, cited reasons)
      ai_photo.py          cached / live (Anthropic) / fallback photo interpretation
      report.py            PDF generation (reportlab + matplotlib)
  scripts/
    prepare_data.py       real-data pipeline, auto-fallback to synthetic
    make_synthetic_data.py synthetic fallback generator (terrain, indices, photos, AI cache)
    seed_db.py             precomputes impact/WII/verdicts into the DB
  data/                  processed/ (rasters+PNGs), photos/, manifest.json, ai_cache.json, jalsakshya.db

frontend/
  src/
    api.js               fetch wrappers for every backend endpoint
    App.jsx               top-level state: selection, layers, map/detail sync
    components/           Header, LayerPanel, MapView, DetailPanel, RankingModal,
                           UploadDialog, PixelInspector, BeforeAfterSlider
```

### Data flow (per intervention)

1. **Photo** (geo-tagged, EXIF GPS + timestamp) → AI vision interpretation
   (`ai_photo.py`): structured JSON (structure type, water present, vegetation level,
   land condition, structure condition, confidence, notes).
2. **Pixel link**: the photo's GPS point is located on the 30 m satellite grid; a local
   zone (3×3 pixels, ~90 m) and a context zone (~500 m buffer) are sampled.
3. **Control-area DiD** (`impact.py`): control pixels are untreated cells of the same
   land-cover class and similar slope, >500 m from any intervention. Impact =
   `(treated_after − treated_before) − (control_after − control_before)` for NDVI, water
   frequency, and NDMI — this cancels out a wet/dry year that hit the whole area equally.
4. **WII** (0–100): weighted, min-max-normalised combination of the three DiD values plus
   AI confidence (weights in `config.WII_WEIGHTS`, shown on screen, not hidden).
5. **Verdict** (`verification.py`): compares the photo's claim against the satellite
   signal using explicit rules, and returns one of exactly three states —
   **Corroborated**, **Mismatch**, or **Inconclusive** — with a reason sentence that
   cites the actual numbers, never a vague statement.
6. Everything above is **precomputed** by `seed_db.py`, so API requests are instant at
   demo time.

## 4. API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | liveness check |
| `GET /api/meta` | bbox, years, data source, WII weights |
| `GET /api/watershed`, `GET /api/streams` | GeoJSON |
| `GET /api/layers/{name}/{year}` | `{url, bounds}` for a rendered PNG overlay (`ndvi`, `mndwi`, `ndmi`, `water_freq`, `lulc`) |
| `GET /api/interventions` | GeoJSON FeatureCollection with verdict + WII, for map markers |
| `GET /api/interventions/{id}` | full detail: photo, AI, verdict, impact, time series |
| `GET /api/photos/{id}/file` | serves a photo file |
| `POST /api/photos` | multipart upload: EXIF GPS check, nearest-intervention match, AI read, verdict |
| `GET /api/ranking` | interventions sorted mismatch-first for field verification |
| `GET /api/report/watershed.pdf`, `GET /api/report/{id}.pdf` | PDF reports |
| `GET /api/pixel?lat=&lon=` | index values for every year at a clicked point |

Full interactive docs at `/docs`.

## 5. Offline behaviour

Once `prepare_data.py`/`seed_db.py` have run, the running app needs **no network,
API keys, or external map tiles**: every thematic layer is a locally rendered PNG, all
photos are served from local disk, and the frontend deliberately has **no basemap tile
layer** (an external map API) — the watershed boundary, streams and thematic layers are
the map's own visual base. AI photo interpretation uses `data/ai_cache.json` for every
demo photo; a live Anthropic call is only attempted if `ANTHROPIC_API_KEY` is set, and
any failure (or missing key) falls back to a safe low-confidence default rather than
breaking the request.

## 6. Known limitations (by design, stated honestly)

- **30 m pixels cannot resolve small structures.** A check dam or pond bund is smaller
  than one Landsat pixel (0.09 ha). The app analyses the surrounding zone (local 3×3 /
  context ~500 m), not the structure itself, and returns **Inconclusive** rather than
  forcing a verdict when evidence is weak — this is visible in the UI and PDF reports.
- **NDMI is a moisture proxy**, not measured soil moisture — labelled as such everywhere.
- **SRISHTI-DRISHTI** access was not confirmed; `LandsatProvider` (real, open Landsat
  8/9) stands in behind the same `SatelliteProvider` interface that
  `SrishtiDrishtiProvider` (documented stub) would implement.
- **No public dataset of watershed geo-tagged photos exists.** The 16 demo photos are
  clearly labelled placeholder images (Pillow-generated, real GPS EXIF); the upload and
  analysis pipeline itself is fully real and works with a genuine photo.
- This build's seeded demo data is **synthetic** (see section 2) — visibly labelled with
  the "Demo Data" badge and in every generated PDF report.
- The before/after slider zooms into the existing full-extent layer PNGs around the
  selected intervention (CSS pan/zoom) rather than requesting a separately cropped image
  from the backend — a deliberate simplification.

## 7. Demo script (~4 minutes)

1. **Map overview** — watershed boundary, streams, intervention markers, switch the LULC
   / NDVI / Water / Moisture-proxy base layers and the year selector.
2. **Click a corroborated farm pond or check dam** (green marker) — photo, AI reading,
   verdict badge + cited reasoning, control-area DiD numbers, WII gauge, NDVI time series
   (treated vs. control), before/after slider.
3. **Click a mismatch case** (red marker) — explain that photo and satellite evidence
   disagree (e.g. claimed water, no MNDWI signal), flagged for a field visit.
4. **Before/after slider** — drag the divider on the selected intervention's NDVI panel.
5. **Upload a new geo-tagged photo** — drag & drop; watch it fly to its GPS location, run
   AI interpretation, and open its own verdict panel. Try a photo with no GPS EXIF to see
   the friendly rejection message.
6. **Open "Needs Field Verification"** — sorted mismatch-first, then inconclusive, then
   corroborated by lowest WII; click a row to jump to it on the map.
7. **Generate Report** — downloads the watershed PDF (or the selected intervention's PDF
   if one is selected): summary counts, mean WII, map figure, top/bottom-5 tables,
   methodology and limitations sections.

## 8. Acceptance checklist

- [x] Runs fully offline from local files after one data-prep run
- [x] 16 interventions with photo, AI reading, verdict, WII
- [x] Four thematic layers (LULC, NDVI, Water, Moisture proxy) + streams + watershed
      boundary, selectable by year
- [x] 3 mismatch + 2 inconclusive cases demonstrate the verdict logic (11 corroborated)
- [x] Control-area DiD computed and explained in the UI
- [x] Live photo upload with EXIF GPS, flies to the map, friendly no-GPS error
- [x] PDF reports (watershed + single intervention) generate correctly
- [x] "Demo Data" badge shown when synthetic data is active
- [x] 30 m limitation stated in the UI (map footer popover) and in PDF reports
- [x] NDMI labelled "Moisture Proxy" everywhere (never "soil moisture")
- [x] README with setup, architecture, demo script
