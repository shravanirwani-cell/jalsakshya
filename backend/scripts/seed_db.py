"""Populate the SQLite database with the demo interventions/photos and
pre-computed impact analysis (control-area DiD + WII) and verdicts, so API
requests at demo time are instant (PROTOTYPE_PLAN.md section 3).

Reads: data/manifest.json (interventions + photos), data/ai_cache.json,
data/processed/*.tif (per-year NDVI/MNDWI/NDMI/LULC + slope).

Run after prepare_data.py / make_synthetic_data.py:
    python scripts/seed_db.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import rasterio

from app import config
from app.db import Base, engine, SessionLocal
from app.models import Intervention, Photo, Impact
from app.services import grid_utils, impact as impact_service, verification, ai_photo


def load_year_rasters(name, years):
    arrays = {}
    for year in years:
        path = config.PROCESSED_DIR / f"{name}_{year}.tif"
        if path.exists():
            with rasterio.open(path) as src:
                arrays[year] = src.read(1).astype(np.float32)
    return arrays


def main():
    with open(config.META_PATH) as f:
        meta = json.load(f)
    with open(config.MANIFEST_PATH) as f:
        manifest = json.load(f)

    years = meta["years"]
    epsg = meta["crs"]
    pixel_size = meta["pixel_size_m"]
    bbox = meta["bbox"]

    print(f"Data source: {meta['source']}  |  years: {years}")

    transform, width, height = grid_utils.bbox_to_utm_grid(bbox, epsg, pixel_size)

    print("Loading rasters into memory...")
    ndvi_by_year = load_year_rasters("ndvi", years)
    mndwi_by_year = load_year_rasters("mndwi", years)
    ndmi_by_year = load_year_rasters("ndmi", years)
    lulc_by_year = load_year_rasters("lulc", years)
    with rasterio.open(config.PROCESSED_DIR / "slope.tif") as src:
        slope_arr = src.read(1).astype(np.float32)
    with rasterio.open(config.PROCESSED_DIR / "water_freq.tif") as src:
        water_freq_arr = src.read(1).astype(np.float32)

    interventions = manifest["interventions"]
    photos_by_iv = {p["intervention_id"]: p for p in manifest["photos"]}

    # Row/col for every intervention, needed both individually and as the
    # exclusion list when picking control pixels for any one of them.
    for iv in interventions:
        iv["_row"], iv["_col"] = grid_utils.latlon_to_rowcol(transform, epsg, iv["lat"], iv["lon"])
    all_rowcols = [(iv["_row"], iv["_col"]) for iv in interventions]

    print("Computing control-area DiD per intervention...")
    raw_results = []  # one dict per intervention, before WII normalisation
    for iv in interventions:
        row, col = iv["_row"], iv["_col"]
        completed_year = int(iv["completed_on"][:4])
        pre_years = [y for y in years if y < completed_year]
        post_years = [y for y in years if y > completed_year]

        # Treated land class from the last pre-completion year (falls back to
        # the earliest available year if the intervention predates our series).
        class_year = max(pre_years) if pre_years else min(years)
        treated_lulc_class = int(lulc_by_year[class_year][row, col])

        control_mask = impact_service.select_control_pixels(
            lulc_by_year[class_year], slope_arr, all_rowcols, row, col,
            treated_lulc_class, pixel_size,
        )

        def zone_series(arr_by_year, yrs, sampler):
            return [sampler(arr_by_year[y]) if y in arr_by_year else np.nan for y in yrs]

        def control_mean(arr, mask=control_mask):
            valid = arr[mask & ~np.isnan(arr)]
            return float(np.mean(valid)) if valid.size else np.nan

        ndvi_treated_series = zone_series(ndvi_by_year, years,
            lambda a: impact_service.sample_context_zone(a, row, col, pixel_size))
        ndvi_control_series = [control_mean(ndvi_by_year[y]) for y in years]

        ndmi_treated_series = zone_series(ndmi_by_year, years,
            lambda a: impact_service.sample_context_zone(a, row, col, pixel_size))
        ndmi_control_series = [control_mean(ndmi_by_year[y]) for y in years]

        water_treated_series = zone_series(mndwi_by_year, years,
            lambda a: impact_service.sample_context_zone_water_fraction(a, row, col, pixel_size))
        water_control_series = [float(np.mean(mndwi_by_year[y][control_mask] > 0)) for y in years]

        def before_after(series, yrs):
            before = [v for y, v in zip(yrs, series) if y in pre_years and not np.isnan(v)]
            after = [v for y, v in zip(yrs, series) if y in post_years and not np.isnan(v)]
            return (float(np.mean(before)) if before else np.nan,
                    float(np.mean(after)) if after else np.nan)

        ndvi_tb, ndvi_ta = before_after(ndvi_treated_series, years)
        ndvi_cb, ndvi_ca = before_after(ndvi_control_series, years)
        ndvi_did = impact_service.compute_did(ndvi_tb, ndvi_ta, ndvi_cb, ndvi_ca)

        water_tb, water_ta = before_after(water_treated_series, years)
        water_cb, water_ca = before_after(water_control_series, years)
        water_did = impact_service.compute_did(water_tb, water_ta, water_cb, water_ca)

        ndmi_tb, ndmi_ta = before_after(ndmi_treated_series, years)
        ndmi_cb, ndmi_ca = before_after(ndmi_control_series, years)
        ndmi_did = impact_service.compute_did(ndmi_tb, ndmi_ta, ndmi_cb, ndmi_ca)

        photo = photos_by_iv.get(iv["id"])
        photo_path = config.PHOTOS_DIR / photo["file"] if photo else None
        ai_result = ai_photo.interpret(photo["file"], photo_path) if photo else ai_photo.DEFAULT_LOW_CONFIDENCE

        # Verification uses the photo's own GPS point (Step 5: link photo to pixel).
        if photo:
            p_row, p_col = grid_utils.latlon_to_rowcol(transform, epsg, photo["lat"], photo["lon"])
        else:
            p_row, p_col = row, col
        latest_year = max(years)
        local_mndwi = impact_service.sample_local_zone(mndwi_by_year[latest_year], p_row, p_col)
        context_mndwi = impact_service.sample_context_zone(mndwi_by_year[latest_year], p_row, p_col, pixel_size)
        water_freq_local = impact_service.sample_local_zone(water_freq_arr, p_row, p_col)
        n_clear_years = len(years)

        verdict, reason = verification.verify(
            ai_result, local_mndwi, context_mndwi, ndvi_did, water_freq_local,
            n_clear_years, ai_result.get("structure_type", iv["type"]),
        )

        raw_results.append({
            "intervention": iv, "photo": photo, "ai_result": ai_result,
            "verdict": verdict, "reason": reason,
            "ndvi_did": ndvi_did, "water_did": water_did, "ndmi_did": ndmi_did,
            "n_clear_scenes": n_clear_years,
            "control_pixel_count": int(control_mask.sum()),
            "series": {
                "years": years,
                "treated_ndvi": ndvi_treated_series, "control_ndvi": ndvi_control_series,
            },
        })

    all_ndvi = [r["ndvi_did"] for r in raw_results]
    all_water = [r["water_did"] for r in raw_results]
    all_ndmi = [r["ndmi_did"] for r in raw_results]

    print("Computing WII and writing to database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    table_rows = []
    for r in raw_results:
        iv = r["intervention"]
        confidence = r["ai_result"].get("confidence", 0.5)
        wii = impact_service.compute_wii(
            r["ndvi_did"], r["water_did"], r["ndmi_did"], confidence,
            all_ndvi, all_water, all_ndmi,
        )

        db_iv = Intervention(
            id=iv["id"], name=iv["name"], type=iv["type"], lat=iv["lat"], lon=iv["lon"],
            completed_on=iv["completed_on"], micro_watershed_id=iv["micro_watershed_id"],
        )
        db.add(db_iv)

        if r["photo"]:
            db.add(Photo(
                intervention_id=iv["id"], file=r["photo"]["file"],
                lat=r["photo"]["lat"], lon=r["photo"]["lon"], taken_on=r["photo"]["taken_on"],
                bearing_deg=r["photo"]["bearing_deg"], ai=r["ai_result"],
                verdict=r["verdict"], verdict_reason=r["reason"], uploaded=False,
            ))

        db.add(Impact(
            intervention_id=iv["id"], ndvi_did=r["ndvi_did"], water_freq_did=r["water_did"],
            ndmi_did=r["ndmi_did"], wii=wii, n_clear_scenes=r["n_clear_scenes"],
            series_json=r["series"], control_pixel_count=r["control_pixel_count"],
        ))

        table_rows.append((iv["name"], iv["type"], r["verdict"], wii,
                            r["ndvi_did"], r["water_did"]))

    db.commit()
    db.close()

    print("\n%-16s %-12s %-14s %6s %9s %9s" % ("Name", "Type", "Verdict", "WII", "NDVI DiD", "WaterDiD"))
    counts = {"corroborated": 0, "mismatch": 0, "inconclusive": 0}
    for name, itype, verdict, wii, ndvi_did, water_did in table_rows:
        counts[verdict] = counts.get(verdict, 0) + 1
        print("%-16s %-12s %-14s %6.1f %9.3f %9.3f" % (name, itype, verdict, wii, ndvi_did, water_did))
    print("\nVerdict counts:", counts)
    print(f"Seeded {len(table_rows)} interventions into {config.DB_PATH}")


if __name__ == "__main__":
    main()
