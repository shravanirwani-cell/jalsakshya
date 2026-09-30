# PROTOTYPE_PLAN.md — Build instructions for Claude Code

**How to use:** put `PROJECT_CONTEXT.md` and this file in an empty folder `jalsakshya/`, open Claude Code there, and say: *"Read PROJECT_CONTEXT.md and PROTOTYPE_PLAN.md, then build the prototype phase by phase. Run and test each phase before moving on. Ask me only if blocked."*

You are building a **one-day hackathon prototype** of JalSakshya: a map workbench that links geo-tagged watershed photos to 30 m satellite trends. Follow the phases in order. After each phase run the listed check. Do not add out-of-scope features.

## 0. Constraints

- Stack: React + Vite + Leaflet; FastAPI; rasterio, geopandas, shapely, numpy, pysheds, matplotlib, reportlab, Pillow, piexif; SQLite (plain SQLAlchemy or sqlite3).
- The running app must work **offline from local files**: no live satellite calls, no required API key.
- AI photo reading is optional live (if `ANTHROPIC_API_KEY` is set) and otherwise uses `data/ai_cache.json`.
- Synthetic/demo data must be labelled in the UI ("Demo data").
- One sample watershed only. Default: the area around **Ralegan Siddhi, Ahmednagar, Maharashtra** (centre about 19.0 N, 74.9 E; a well-known watershed success story). Verify coordinates and use a bounding box of roughly 10 km × 10 km. If data for it is poor, choose any semi-arid area and tell the user.

## 1. Phase 1 — Project scaffold (15 min)

- Create the layout from `PROJECT_CONTEXT.md` section 7.
- `backend/requirements.txt`, virtualenv, FastAPI app with `/api/health`.
- Vite React app, proxy `/api` to the backend (port 8000), Leaflet base map.
- **Check:** backend health returns OK; frontend shows an empty map.

## 2. Phase 2 — Data preparation scripts (core; 90 min)

Write `backend/scripts/prepare_data.py` with a provider interface:

```python
class SatelliteProvider(ABC):
    def get_seasonal_composites(self, bbox, years, season) -> dict  # {year: xarray/ndarray bands}
class LandsatProvider(SatelliteProvider): ...   # Planetary Computer STAC, collection "landsat-c2-l2"
class SrishtiDrishtiProvider(SatelliteProvider):  # stub: raises NotImplementedError with a clear message
```

`LandsatProvider` (real data): use `pystac-client` with `https://planetarycomputer.microsoft.com/api/stac/v1`, `planetary-computer` for signing, `stackstac` or `rioxarray` for loading. Filter `eo:cloud_cover < 30`, bbox, post-monsoon window (Oct 1 to Dec 15) for each year in **2018–2025**. Mask clouds/shadow with `QA_PIXEL`. Scale `DN*0.0000275-0.2`. Median composite per year. Reproject to a common 30 m grid (EPSG:32643 for this area; choose the right UTM zone otherwise).

Produce in `backend/data/processed/`:

- `ndvi_{year}.tif`, `mndwi_{year}.tif`, `ndmi_{year}.tif` per year
- `water_freq.tif` (share of clear scenes with MNDWI > 0, per year if feasible)
- `lulc_{year}.tif` from simple rules on indices (classes: 1 water, 2 dense vegetation, 3 cropland/moderate, 4 scrub/sparse, 5 barren/built) with thresholds in config
- `dem.tif` from Copernicus DEM 30 m (`cop-dem-glo-30` on Planetary Computer)
- Drainage with `pysheds`: `flowacc.tif`, `streams.geojson` (with Strahler order), `watershed.geojson` (delineate from the lowest stream outlet, or use the bbox polygon if delineation fails)
- Pre-rendered colour PNG overlays per layer and year with a `bounds.json` (WGS84 bounds), for fast Leaflet `ImageOverlay`

`backend/scripts/make_synthetic_data.py` is a **fallback** that generates plausible rasters for the same bbox and years (smooth noise, vegetation gain near streams after intervention dates, a few ponds that show water) so the app runs even if downloads fail. `prepare_data.py --synthetic` uses it. Label the output `"source": "synthetic"` in a `data/processed/meta.json`, and show "Demo data" in the UI when that is the case.

**Interventions and photos** (`seed_db.py` plus `data/manifest.json`):

- Generate **16 interventions** placed on or near stream pixels (orders 1–3): mix of check_dam, farm_pond, trench, plantation, with `completed_on` dates in 2020–2022 (leave at least two years after completion).
- Make `manifest.json` with one photo per intervention: file name, lat/lon (within about 15 m of the point), `taken_on` (after completion), bearing.
- Photos: put real images in `data/photos/` if the user provides them. Otherwise generate clearly labelled placeholder images with Pillow (landscape colour blocks with a text label) and write GPS into EXIF with `piexif`. Tell the user to replace them with real photos (Wikimedia Commons search terms: "check dam India", "farm pond Maharashtra", "gully plug", "watershed plantation India").
- Create `data/ai_cache.json`: a plausible AI interpretation object per photo (schema in `PROJECT_CONTEXT.md` section 8). Make **3 deliberately conflicting cases** (for example the photo says "water present" but satellite shows none) so the Mismatch demo works, and **2 inconclusive** (tiny structure or cloudy year).

**Check:** `python scripts/prepare_data.py` (or `--synthetic`) finishes; files exist; open one PNG and confirm it looks sensible; DB has 16 interventions and 16 photos.

## 3. Phase 3 — Analysis services (75 min)

- `indices.py`: NDVI, MNDWI, NDMI exactly as in context section 4.
- `impact.py`: for each intervention, sample local (3×3) and context (about 500 m buffer) zones; select control pixels (same LULC class, slope within ±3°, >500 m from any intervention, at least 30 pixels); compute mean pre/post (pre = years before `completed_on` year, post = years after) and **DiD** for NDVI, water_freq, NDMI. Compute `wii` = 100 × weighted sum of min-max normalised DiD values across all interventions (weights: NDVI 0.35, water 0.35, NDMI 0.15, photo confidence 0.15; in `config.py`). Save yearly series for treated and control for the chart.
- `verification.py`: implement the table from `SOLUTION_DOCUMENT.md` step 7. Inputs: AI result and satellite values at the photo's year. Rules: `water_present` true and MNDWI local/context > 0 → corroborated; true but no signal and structure_type in (farm_pond, check_dam) and zone water_freq < 0.1 → mismatch; `vegetation_level` dense/moderate with NDVI DiD > 0 → corroborated; sparse/none with large positive DiD → mismatch; any case with fewer than 2 clear years, or AI confidence < 0.5 → inconclusive. Return `verdict` plus a one-sentence `verdict_reason` that cites the numbers.
- `ai_photo.py`: `interpret(photo_path)` returns the JSON object. Order: cache hit, else live call if `ANTHROPIC_API_KEY` set (vision call with the schema in the prompt; temperature 0; parse JSON strictly; on any failure fall back to `inconclusive`-friendly low-confidence default), else default low-confidence.
- Pre-compute everything into the DB during `seed_db.py` so requests are instant.

**Check:** a script prints a table of 16 interventions with `ndvi_did`, `water_freq_did`, `wii`, `verdict`; at least 3 mismatch and 2 inconclusive appear; numbers are plausible.

## 4. Phase 4 — API (45 min)

- `GET /api/meta` → bbox, years, data source (real/synthetic), layer list, weights
- `GET /api/watershed`, `GET /api/streams` → GeoJSON
- `GET /api/layers/{name}/{year}` → `{url, bounds}`; static PNGs served under `/static/layers/...`
- `GET /api/interventions` (GeoJSON with verdict and wii), `GET /api/interventions/{id}` (details, series, photo, AI, verdict, reason)
- `GET /api/photos/{id}/file`
- `POST /api/photos` (multipart: file + optional intervention_id): read EXIF GPS and time (reject with a clear message if no GPS), check inside watershed, run AI, find nearest intervention within 300 m, compute zone stats, return the same object as the detail endpoint and persist it.
- `GET /api/ranking` → interventions sorted by "needs field visit" (mismatch first, then low wii)
- `GET /api/report/{watershed|intervention_id}.pdf`
- `GET /api/pixel?lat=&lon=` → index values for all years at that point (for click inspection)

**Check:** `curl` each endpoint; OpenAPI docs page loads at `/docs`.

## 5. Phase 5 — Frontend (120 min)

Design: clean government-dashboard look, green/blue palette, readable at projector size, light theme. Three columns on desktop: left layer/filter panel, centre map, right detail panel. Mobile: stacked.

Components:

1. **Header** with title, "Demo data" badge when synthetic, and a "Generate report" button.
2. **Layer panel:** base layers (LULC, NDVI, Water, Moisture proxy), year selector, toggles for watershed boundary, streams (width by order), intervention markers (colour by verdict: green corroborated, red mismatch, grey inconclusive). Legends for each layer.
3. **Map:** Leaflet; click a marker to open its detail; click anywhere to show the pixel inspector (index values over years).
4. **Before/after slider** (two image overlays with a draggable divider, or a year-A/year-B side-by-side) centred on the selected intervention.
5. **Detail panel:** photo, AI interpretation (chips and confidence bar), verdict badge with the reason sentence, DiD numbers (NDVI, water, moisture) with plain-language captions, WII gauge, time-series line chart (treated vs control, completion date marker). Use Recharts.
6. **Ranking view:** table "Needs field verification" with sort and click-to-zoom.
7. **Upload dialog:** drop a photo, show progress, then fly the map to the new point and open its panel. Show a friendly error when there is no GPS.
8. **Limits note** in a footer popover: "30 m pixels cannot resolve small structures; results describe surrounding zones."

**Check:** run both servers; click through the demo script (section 7); no console errors.

## 6. Phase 6 — PDF report (30 min)

`reports` service with reportlab and matplotlib: cover (watershed name, date, data source), summary table (counts of corroborated/mismatch/inconclusive, mean WII), map figure with markers, top-5 and bottom-5 interventions with photo thumbnail and numbers, methodology paragraph, limits paragraph. Single-intervention report: photo, AI output, verdict, chart.

**Check:** generated PDF opens and looks tidy.

## 7. Phase 7 — Demo polish and README (30 min)

- `README.md` with setup (`pip install -r requirements.txt`; `python scripts/prepare_data.py`; `uvicorn app.main:app`; `npm install && npm run dev`) and the demo script below.
- Script `run_demo.sh` to start everything.
- Demo script: (1) map overview and layers, (2) click a corroborated pond, (3) show a mismatch, (4) before/after slider, (5) upload a new photo live, (6) ranking view, (7) PDF report.
- Test the whole flow once offline (no network).

## 8. Acceptance criteria

- [ ] App runs fully offline from local files after one data-prep run
- [ ] 16 interventions with photo, AI reading, verdict, WII
- [ ] Four thematic layers plus streams plus watershed boundary, selectable by year
- [ ] At least 3 mismatches and 2 inconclusive cases demonstrate the verdict logic
- [ ] Control-area DiD used (and explained in the UI)
- [ ] Live photo upload works with EXIF GPS and lands on the map
- [ ] PDF report generates
- [ ] Demo/synthetic data labelled when used
- [ ] README with demo script

## 9. Suggested team split (3–4 people, one day)

| Person | Owns |
|---|---|
| A (geo/data) | Phase 2 and review of Phase 3 numbers; real data run |
| B (backend) | Phases 3–4, PDF report |
| C (frontend) | Phase 5 |
| D (pitch) | PPT from `SOLUTION_DOCUMENT.md` section 13, real photos, demo rehearsal |

With Claude Code doing most implementation, people mainly verify, supply real photos and rehearse.

## 10. If time runs short, cut in this order

1. Before/after slider (use year dropdown instead)
2. Single-intervention PDF (keep the watershed report)
3. Pixel inspector
4. Real data (use `--synthetic`, keep the "Demo data" badge)

Never cut: photo → pixel link, verdict with Inconclusive, control-area impact, the upload demo.
