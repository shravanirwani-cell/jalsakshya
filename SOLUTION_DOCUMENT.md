# JalSakshya — Geo-Coded Image Intelligence for Watershed Development

**SIH 2026 · PS SIH26015 · Ministry of Rural Development (Dept. of Land Resources) · Software / Disaster Management**
*(JalSakshya = "water evidence". The name is a placeholder; rename freely.)*

---

## 1. One-line pitch

JalSakshya turns the geo-tagged photos that watershed staff already take (and only file away) into **analysed, satellite-verified evidence**: every photo is located on the watershed map, interpreted by AI, linked to the 30 m satellite pixel beneath it, and tested against a before/after trend with a control area, so an officer can see *did this check dam, pond or plantation actually work, and can we trust the claim?*

## 2. The problem in plain words

- Watershed works (check dams, farm ponds, trenches, plantations) are built to hold rain water on the land and improve soil, vegetation and groundwater.
- Checking whether they worked is done with field visits and paper reports: slow, costly, small coverage.
- Field staff already upload geo-tagged photos, but these are used only as "proof of work done", not analysed.
- Satellite data at 30 m (SRISHTI-DRISHTI platform) exists but is not joined to those photos or to watershed boundaries.
- Result: no standard way to visualise field conditions, track change, or produce reliable evidence for decisions.

**What the PS wants:** a scalable GIS + remote-sensing approach that integrates geo-coded images, satellite data, thematic layers and watershed boundaries, and produces maps and insights for planners.

Note: the PS text still says "Table to be Added here" for Scope of Study, so scope is partly open. We define it ourselves (Section 5) and say so in the presentation.

## 3. Users

| User | What they need |
|---|---|
| District / block watershed officer | See every intervention on a map, know which ones are working, which need a visit |
| Project implementing agency (field staff) | Upload a photo, instantly see it on the map with an AI check |
| State / national monitor (MoRD/DoLR) | Compare watersheds, get standard reports, spot claims that do not match reality |
| Planner | See drainage, degradation and gaps, and get suggestions on where to build next |

## 4. Reality checks (state these honestly; judges respect it)

1. **30 m pixel = 0.09 ha.** A small check dam is smaller than a pixel. We therefore measure *effect in the surrounding zone* (buffer and downstream stream reach), not the structure itself. Photos provide the close-up truth that the satellite cannot.
2. **SRISHTI-DRISHTI access.** We could not confirm a public API or download route. The prototype uses a **pluggable data-provider interface**. Landsat 8/9 (natively 30 m, open) is the stand-in, and SRISHTI-DRISHTI drops in by implementing one class. Say this openly in the PPT.
3. **No public archive of watershed geo-tagged photos exists.** The prototype uses a small curated/synthetic photo set placed on real geography. The pipeline is real; the photo set is demo data.
4. **Rainfall varies year to year**, so naive before/after vegetation comparisons are misleading. We use a **control-area comparison** (Section 6, step 6) to handle this.

## 5. Scope we define (fills the PS's missing table)

| Area | Included in prototype | In full solution |
|---|---|---|
| Field data | Geo-tagged photos (EXIF GPS, time, direction) | Mobile PWA capture, offline queue |
| Satellite data | Landsat 8/9 30 m time series via provider interface | SRISHTI-DRISHTI, Sentinel-2, Resourcesat/LISS |
| Thematic layers | LULC, NDVI, water bodies, soil-moisture proxy, drainage and stream order, watershed boundary | Soil maps, groundwater well data, rainfall |
| Analysis | Change detection, control-area impact score, photo-satellite verification | Time-series trend/anomaly models |
| AI | Photo interpretation by a vision model | Fine-tuned on-device model for offline use |
| Outputs | Interactive map workbench, per-intervention cards, PDF report | State dashboards, APIs |

## 6. Methodology (step by step)

**Step 1 — Ingest and standardise photos.** Read EXIF (GPS lat/lon, timestamp, compass bearing). Reject photos with no GPS or GPS outside the watershed. Store with intervention ID and type.

**Step 2 — AI photo interpretation.** A vision model receives the photo and returns structured JSON: `{structure_type, water_present, vegetation_level (none/sparse/moderate/dense), land_condition (degraded/stable/improving), condition_of_structure (intact/damaged/silted), confidence, notes}`. A cached fallback result per demo photo guarantees the demo works offline.

**Step 3 — Satellite time series.** For the watershed, build seasonal composites (median of cloud-masked scenes) for matched seasons, e.g. post-monsoon Oct–Dec, so years are comparable. Landsat 8/9 Collection 2 Level-2 scale: `reflectance = DN × 0.0000275 − 0.2`.

**Step 4 — Indices (thematic layers).**

- NDVI = (NIR − Red) / (NIR + Red) → vegetation status (Landsat: B5, B4)
- MNDWI = (Green − SWIR1) / (Green + SWIR1) → open water (B3, B6)
- NDMI = (NIR − SWIR1) / (NIR + SWIR1) → moisture proxy (B5, B6). Label it a *proxy*, not measured soil moisture.
- LULC: simple rule/ML classes (water, forest/dense veg, cropland, scrub/sparse, barren/built) from indices; stretch: use an existing open land-cover product as a check.
- Drainage: DEM → fill pits → D8 flow direction → flow accumulation → stream extraction → Strahler order; watershed boundary delineated from a pour point (or supplied).

**Step 5 — Link photo to pixel.** For each photo, take the 30 m pixel at its GPS point plus two zones: a **local zone** (3×3 pixels ≈ 90 m) and a **context zone** (≈ 500 m buffer, downstream-biased along the stream). Pull index time series for each zone.

**Step 6 — Impact with a control (the key scientific step).** For each intervention completed on date *T*:

1. Pick **control pixels**: same watershed, same LULC class, similar slope, not within 500 m of any intervention.
2. Compute mean index before *T* and after *T*, for treated zone and control.
3. Impact = (treated_after − treated_before) − (control_after − control_before). This is difference-in-differences and removes the effect of a good or bad monsoon that hit both equally.
4. Do this for NDVI, water frequency (share of clear scenes where MNDWI > 0), and NDMI.

**Step 7 — Photo ↔ satellite verification.** Compare what the photo says with what the satellite sees on the nearest clear date:

| Photo says | Satellite check | Verdict |
|---|---|---|
| Water present at pond | MNDWI > 0 in local/context zone | **Corroborated** |
| Water present | No water signal, and structure large enough to show | **Mismatch → verify in field** |
| Dense vegetation | NDVI high vs control | **Corroborated** |
| Structure too small / cloud / gap in data | Not enough signal | **Inconclusive** (never forced to pass or fail) |

The explicit "Inconclusive" state is deliberate: it stops the system from making false claims at 30 m.

**Step 8 — Watershed Impact Index (WII, 0–100).** Per intervention and per micro-watershed: weighted average of min-max or z-normalised impact scores (NDVI 35%, water 35%, moisture 15%, photo-verification confidence 15%). Weights are configurable and shown on screen, not hidden.

**Step 9 — Outputs.** Maps, cards, change slider, ranked list, PDF report.

**Step 10 (stretch) — Where to build next.** Suitability layer for new structures: stream order 1–3, slope below ~15%, not already within an existing structure's zone, low vegetation/degraded land. Shown as a map layer for planners.

## 7. Architecture

```
 Field staff (web/PWA)         Open/partner satellite data
        │ photo + GPS                │ (Landsat 30 m now, SRISHTI-DRISHTI later)
        ▼                            ▼
 ┌──────────────┐    ┌───────────────────────────────┐
 │  FastAPI     │◄──►│  Data Provider interface       │
 │  backend     │    │  (LandsatProvider, SDProvider) │
 └─────┬────────┘    └───────────────────────────────┘
       │
 ┌─────▼──────────────┐   ┌─────────────────────┐   ┌────────────────┐
 │ Geo pipeline        │   │ AI photo interpreter │   │ Report builder │
 │ rasterio/geopandas  │   │ vision model + cache │   │ PDF (reportlab)│
 │ pysheds (drainage)  │   └─────────────────────┘   └────────────────┘
 └─────┬──────────────┘
       ▼
 SQLite (interventions, photos, scores) + GeoTIFF / PNG layer store
       ▼
 React + Leaflet map workbench
```

Stack: React (Vite) + Leaflet, FastAPI, rasterio, geopandas, shapely, pysheds, numpy, reportlab, matplotlib, SQLite.

## 8. How this answers each "Expected Solution" (a–g)

| PS item | Our answer |
|---|---|
| a) Integrated geospatial visualisation framework | Map workbench that overlays photos, watershed boundary, thematic layers and satellite time series in one place |
| b) Improved geo-coded image interpretation | AI structured interpretation of every photo, linked to the satellite pixel |
| c) Thematic maps and products | LULC, drainage and stream order, NDVI, water bodies, intervention map, change-detection layer |
| d) Enhanced monitoring and assessment | Per-intervention verification verdict and Impact Index |
| e) Decision support | Ranked "needs a visit" list, PDF report, suitability layer |
| f) Scalable, cost-effective | Open data, one config per watershed, provider interface, runs on one modest server |
| g) Strengthen SRISHTI-DRISHTI use | Provider interface makes it the primary source the moment access exists; outputs are designed to be fed back as layers |

## 9. Novelty and differentiation

At least several teams have public repos for this PS with a photo-versus-satellite cross-check idea, so "we link photos to satellite" alone will not stand out. Ours differs in:

1. **Control-area impact (difference-in-differences)**, so results are not fooled by rainfall.
2. **Uncertainty-aware verdicts**: Corroborated / Mismatch / Inconclusive, with the 30 m limit acknowledged in the product itself.
3. **Zone-based analysis** (local, context, downstream) rather than pretending a pixel sees a small structure.
4. **Provider-agnostic design** ready for SRISHTI-DRISHTI.
5. **Explainable index**: weights and inputs visible and adjustable.
6. **Planner-facing next-site suggestion** (stretch) so the tool guides future spending, not only audits past spending.

## 10. Impact, feasibility, cost

- **Impact:** faster verification, fewer needless field visits, evidence-based funding and fraud/mismatch flagging, standard reports.
- **Feasibility:** all inputs are open or already collected; every step uses mature libraries.
- **Cost:** no new hardware; cloud-free satellite access; AI calls only per uploaded photo.
- **Scalability:** a new watershed needs a boundary, an intervention list and a date range; the pipeline is the same.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Cloud cover in monsoon | Seasonal median composites; use post-monsoon windows; "Inconclusive" state |
| 30 m too coarse | Zone analysis and photo ground truth; state limits openly |
| No photo dataset | Curated/synthetic demo set, clearly labelled; real-upload path works |
| SRISHTI-DRISHTI access | Provider interface, Landsat stand-in |
| AI misclassifies photos | Confidence shown; low-confidence photos routed to human review |
| Live demo failure | Precomputed data bundle plus cached AI results; no external call required in the demo |

## 12. Roadmap beyond the hackathon

Mobile PWA with offline capture; on-device photo classifier; SRISHTI-DRISHTI and Sentinel-2 providers; rainfall and groundwater-well integration; multi-watershed dashboards; audit trail for adjudicating mismatches; export to departmental formats.

## 13. Suggested PPT outline (SIH format)

1. Title, team, PS code
2. Problem and gap (photos filed, not analysed; satellite not linked)
3. Our idea in one picture (photo → pixel → trend → verdict)
4. Solution workflow (the 10 steps, condensed)
5. Architecture diagram
6. Thematic layers and outputs (screenshots)
7. Verification logic (table from step 7)
8. Impact Index and control-area method
9. Prototype demo screenshots
10. Novelty vs existing approaches
11. Feasibility, scalability, cost
12. Risks and honest limits
13. Roadmap and SRISHTI-DRISHTI integration
14. Team and thank-you

## 14. Likely judge questions and answers

- **"30 m can't see a check dam."** Correct, and we say so. We measure the zone effect and use the photo as close-up evidence; unclear cases are marked Inconclusive.
- **"Do you have SRISHTI-DRISHTI data?"** The prototype uses Landsat 30 m as a stand-in through a provider interface; SRISHTI-DRISHTI plugs in by implementing one class.
- **"How do you know it was the intervention, not the rain?"** Control-area difference-in-differences.
- **"Is the photo data real?"** The demo photo set is curated and labelled as demo; the upload and analysis pipeline is real.
- **"How does it scale?"** One config per watershed; same pipeline; open data.
- **"What if the AI is wrong?"** Confidence scores and human-review queue; the AI never overrides the satellite check alone.

## 15. Live demo script (about 4 minutes)

1. Open map: watershed boundary, drainage, intervention markers (20 s).
2. Toggle NDVI / water / LULC layers (30 s).
3. Click a pond photo: AI reading plus satellite time-series chart plus verdict (60 s).
4. Use the before/after slider around that pond (30 s).
5. Show a Mismatch flagged for field verification (30 s).
6. Upload a new photo live: it appears on the map with AI output (45 s).
7. Generate the PDF report (30 s).

---

**Sources and notes**

- PS details: [SIH Buddy – SIH26015](https://www.sihbuddy.in/ps/SIH26015)
- Existing public attempts reviewed for differentiation: [Walkouts035-SIH26015](https://github.com/M-Kishore92/Walkouts035-SIH26015)
- Landsat scale factors and index formulas are standard USGS/literature values; confirm band numbers against the Landsat Collection 2 Level-2 documentation when implementing.
