# PROJECT_CONTEXT.md — JalSakshya (read this first)

This file gives any AI assistant or developer full context on what we are building. Read it before touching code. Companion files: `SOLUTION_DOCUMENT.md` (full solution, pitch, PPT outline) and `PROTOTYPE_PLAN.md` (build instructions).

## 1. What this is

- **Event:** Smart India Hackathon 2026, problem statement **SIH26015**, Ministry of Rural Development (Dept. of Land Resources). Category: Software.
- **PS title:** "Application of Geospatial Techniques for visualization and analysis to interpret Geo-Coded Images to enhance watershed development outcomes."
- **Our product (working name):** **JalSakshya** ("water evidence").
- **Time budget:** one day. Prototype only, not production.

## 2. The problem in five lines

1. Watershed programmes build check dams, farm ponds, trenches and plantations to hold water and restore land.
2. Staff take geo-tagged photos of these works, but the photos are only filed as proof, never analysed.
3. A government satellite platform (SRISHTI-DRISHTI) offers 30 m resolution data, not joined to those photos.
4. Monitoring is manual, slow and unreliable, so nobody can say which interventions worked.
5. The PS asks for a GIS and remote-sensing framework that joins photos, satellite data, thematic layers and watershed boundaries.

## 3. What we are building (one paragraph)

A web app (map workbench). Each geo-tagged photo is placed on the watershed map, interpreted by an AI vision model, linked to the 30 m satellite pixel under it, and compared against a before/after satellite trend **with a control area**. The app gives each intervention a verdict (Corroborated / Mismatch / Inconclusive) and an Impact Score, shows thematic layers (LULC, NDVI, water, moisture proxy, drainage), and exports a PDF report.

## 4. Core concepts and vocabulary

| Term | Meaning |
|---|---|
| Watershed | Land area draining to one outlet; the unit of planning |
| Intervention | A built structure or activity (check dam, farm pond, trench, plantation) with a location and completion date |
| Geo-coded / geo-tagged photo | Photo with GPS coordinates and time in EXIF |
| 30 m pixel | One satellite cell, 30×30 m = 0.09 ha. Smaller than this is sub-pixel |
| NDVI | (NIR−Red)/(NIR+Red), vegetation greenness |
| MNDWI | (Green−SWIR1)/(Green+SWIR1), open water |
| NDMI | (NIR−SWIR1)/(NIR+SWIR1), moisture **proxy** (not measured soil moisture) |
| Local zone / context zone | 3×3 pixels around the point / about 500 m buffer, downstream-biased |
| Control area | Untreated pixels (same watershed, same land class, similar slope, >500 m from any intervention) used to cancel out rainfall effects |
| DiD impact | (treated_after − treated_before) − (control_after − control_before) |
| Verdict | Corroborated, Mismatch, or Inconclusive, from comparing photo claims with satellite evidence |
| WII | Watershed Impact Index, 0–100, weighted score (weights visible and configurable) |
| Provider | Pluggable satellite data source class. `LandsatProvider` now, `SrishtiDrishtiProvider` later |

## 5. Decisions already made (do not revisit without a reason)

- **Stack:** React (Vite) + Leaflet frontend; FastAPI backend; rasterio, geopandas, shapely, pysheds, numpy; reportlab + matplotlib for PDF; SQLite for data.
- **Data strategy:** real open satellite data (Landsat 8/9 Collection 2 Level-2, natively 30 m) for **one sample watershed**, **precomputed offline** into files the app serves. Synthetic fallback generator exists so the app works even if downloads fail.
- **Photos:** small curated/synthetic demo set placed on real geography; clearly labelled as demo data. Real upload path must also work.
- **AI photo interpretation:** vision model returns structured JSON. **Every demo photo has a cached result**, so the demo never depends on network or API keys.
- **Extras in scope:** AI photo interpretation and auto-generated PDF report. Mobile PWA and offline mode are out of scope (mention as roadmap).
- **Presentation:** PPT plus live demo, team of 3–4.

## 6. Honest limits (keep these visible in the product and the pitch)

- 30 m cannot resolve small structures. Analyse zones, not the structure, and return **Inconclusive** when evidence is weak.
- SRISHTI-DRISHTI access was not confirmed. It is represented by the provider interface. Landsat is a stand-in.
- No public dataset of watershed geo-tagged photos exists. Demo photos are curated/synthetic.
- "Soil moisture" is a proxy (NDMI). Never label it as measured soil moisture.

## 7. Repository layout (target)

```
jalsakshya/
  PROJECT_CONTEXT.md  PROTOTYPE_PLAN.md  SOLUTION_DOCUMENT.md
  backend/
    app/ (main.py, config.py, db.py, models.py, schemas.py)
    app/routers/ (layers.py, interventions.py, photos.py, analysis.py, reports.py)
    app/services/ (providers/, indices.py, drainage.py, impact.py, verification.py, ai_photo.py, report.py)
    data/ (raw/, processed/, photos/, manifest.json, ai_cache.json)
    scripts/ (prepare_data.py, make_synthetic_data.py, seed_db.py)
    requirements.txt
  frontend/
    src/ (App.jsx, api.js, components/, pages/)
    package.json  vite.config.js
```

## 8. Key data contracts (keep consistent everywhere)

**Intervention:** `id, name, type (check_dam|farm_pond|trench|plantation), lat, lon, completed_on (YYYY-MM-DD), micro_watershed_id`

**Photo:** `id, intervention_id, file, lat, lon, taken_on, bearing_deg, ai (object), verdict, verdict_reason`

**AI interpretation JSON:** `structure_type, water_present (bool), vegetation_level (none|sparse|moderate|dense), land_condition (degraded|stable|improving), structure_condition (intact|damaged|silted), confidence (0–1), notes`

**Impact result per intervention:** `ndvi_did, water_freq_did, ndmi_did, wii (0–100), series (dates + treated/control values), n_clear_scenes`

**Verdict values:** `corroborated | mismatch | inconclusive`

## 9. Rules for any AI working on this repo

1. Prototype quality: working end to end beats perfect. Do not add features outside `PROTOTYPE_PLAN.md` without asking.
2. Never hard-depend on the network, API keys or live satellite calls at demo time. Everything the UI needs must be served from local precomputed files.
3. Never invent numbers in the UI. Every displayed metric comes from the pipeline output (real or clearly synthetic-labelled).
4. Keep the "Inconclusive" verdict. Do not collapse it into pass/fail.
5. Label synthetic or demo data visibly in the UI.
6. Keep index formulas exactly as in section 4. Landsat C2 L2 scaling: `reflectance = DN × 0.0000275 − 0.2`; bands B3 Green, B4 Red, B5 NIR, B6 SWIR1.
7. Keep code simple and commented; four students will read it.

## 10. Source references

- PS page: https://www.sihbuddy.in/ps/SIH26015
- Another team's public approach (for differentiation only): https://github.com/M-Kishore92/Walkouts035-SIH26015
