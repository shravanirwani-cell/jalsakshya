"""Real-data pipeline entrypoint (PROTOTYPE_PLAN.md section 2).

Attempts, in order: Copernicus DEM (cop-dem-glo-30) -> pysheds drainage ->
Landsat 8/9 Collection 2 Level-2 seasonal composites via the Microsoft
Planetary Computer STAC API -> spectral indices -> LULC -> water frequency ->
rendered layers, for the watershed bbox/years in config.py.

Interventions are placed on the real stream network the same way the
synthetic generator does (reusing its helpers), since no public dataset of
watershed geo-tagged photos exists either way (PROJECT_CONTEXT.md section 6);
only the satellite layers themselves differ between real and synthetic runs.
Unlike the synthetic generator, no verdict outcome is pre-baked here: with
real satellite data, corroborated/mismatch/inconclusive should emerge
honestly from the actual numbers.

Falls back automatically to make_synthetic_data.py if any step fails
(network unavailable, no clear scenes, missing library, etc.), per the
project's offline-first rule. Use --synthetic to skip straight to the
fallback.

Run:
    python scripts/prepare_data.py              # try real data, else fall back
    python scripts/prepare_data.py --synthetic   # force synthetic demo data
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app import config
from app.services import grid_utils, drainage, indices as idx_service, render
from app.services.providers.landsat import LandsatProvider

import make_synthetic_data as synth  # reuse intervention/photo/AI-cache helpers


def fetch_dem(bbox, epsg, pixel_size):
    """Fetch Copernicus DEM GLO-30 tiles covering bbox and mosaic them onto
    our UTM grid."""
    import planetary_computer
    import rasterio
    from pystac_client import Client
    from rasterio.warp import reproject, Resampling

    transform, width, height = grid_utils.bbox_to_utm_grid(bbox, epsg, pixel_size)
    catalog = Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    items = list(catalog.search(collections=["cop-dem-glo-30"], bbox=bbox).items())
    if not items:
        raise RuntimeError("No Copernicus DEM tiles found for this bbox")

    dem = np.full((height, width), np.nan, dtype=np.float32)
    for item in items:
        href = item.assets["data"].href
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"), rasterio.open(href) as src:
            tile = np.full((height, width), np.nan, dtype=np.float32)
            reproject(source=rasterio.band(src, 1), destination=tile,
                      src_transform=src.transform, src_crs=src.crs,
                      dst_transform=transform, dst_crs=epsg, resampling=Resampling.bilinear)
        valid = ~np.isnan(tile)
        dem[valid] = tile[valid]
    if np.isnan(dem).any():
        dem[np.isnan(dem)] = np.nanmean(dem)
    return dem.astype(np.float32), transform, width, height


def run_real_pipeline():
    print("Attempting real data pipeline (Copernicus DEM + Landsat via Planetary Computer)...")
    bbox, epsg, pixel_size = config.BBOX, config.UTM_EPSG, config.PIXEL_SIZE_M

    print("  fetching Copernicus DEM...")
    dem, transform, width, height = fetch_dem(bbox, epsg, pixel_size)
    dem_path = config.PROCESSED_DIR / "dem.tif"
    render.write_geotiff(dem, transform, epsg, dem_path)

    print("  running drainage analysis...")
    result = drainage.compute_drainage(
        dem_path=dem_path, out_flowacc_path=config.PROCESSED_DIR / "flowacc.tif",
        out_streams_path=config.PROCESSED_DIR / "streams.geojson",
        out_watershed_path=config.PROCESSED_DIR / "watershed.geojson",
        out_slope_path=config.PROCESSED_DIR / "slope.tif", src_epsg=epsg,
    )
    stream_mask = result["stream_mask"] & result["watershed_mask"]

    print("  fetching Landsat seasonal composites (this can take a while)...")
    provider = LandsatProvider(epsg=epsg, pixel_size=pixel_size)
    composites = provider.get_seasonal_composites(bbox, config.YEARS, config.SEASON_WINDOW)
    if len(composites) < 2:
        raise RuntimeError(f"Only {len(composites)} year(s) of usable Landsat composites found")

    layers_by_year = {}
    for year, bands in composites.items():
        layers_by_year[year] = {
            "ndvi": idx_service.ndvi(bands["nir"], bands["red"]).astype(np.float32),
            "mndwi": idx_service.mndwi(bands["green"], bands["swir1"]).astype(np.float32),
            "ndmi": idx_service.ndmi(bands["nir"], bands["swir1"]).astype(np.float32),
        }
    available_years = sorted(layers_by_year.keys())

    mndwi_stack = np.stack([layers_by_year[y]["mndwi"] for y in available_years])
    water_freq = np.nanmean(mndwi_stack > 0, axis=0).astype(np.float32)
    render.write_geotiff(water_freq, transform, epsg, config.PROCESSED_DIR / "water_freq.tif")
    render.render_index_png(water_freq, "water_freq", config.PROCESSED_DIR / "water_freq.png")

    for year, arrs in layers_by_year.items():
        for name in ("ndvi", "mndwi", "ndmi"):
            render.write_geotiff(arrs[name], transform, epsg, config.PROCESSED_DIR / f"{name}_{year}.tif")
            render.render_index_png(arrs[name], name, config.PROCESSED_DIR / f"{name}_{year}.png")
        lulc = idx_service.classify_lulc(arrs["ndvi"], arrs["mndwi"], config.LULC_THRESHOLDS)
        render.write_geotiff(lulc, transform, epsg, config.PROCESSED_DIR / f"lulc_{year}.tif",
                              dtype="uint8", nodata=0)
        render.render_lulc_png(lulc, config.PROCESSED_DIR / f"lulc_{year}.png")

    bounds = render.raster_bounds_wgs84(transform, width, height, epsg)
    render.write_bounds_json(list(bounds), config.PROCESSED_DIR / "bounds.json")

    print(f"  placing {len(synth.DEMO_PLAN)} interventions on real stream pixels...")
    points = synth.pick_intervention_points(stream_mask, n=len(synth.DEMO_PLAN))
    interventions, photos, ai_cache = [], [], {}
    type_counters = {t: 0 for t in synth.TYPE_CYCLE}
    for i, ((itype, _demo_case, completed_on), (row, col)) in enumerate(zip(synth.DEMO_PLAN, points)):
        type_counters[itype] += 1
        lat, lon = grid_utils.rowcol_to_latlon(transform, epsg, row, col)
        iv = {"id": i + 1, "name": f"{synth.TYPE_LABEL[itype]} {type_counters[itype]}",
              "type": itype, "lat": lat, "lon": lon, "completed_on": completed_on,
              "micro_watershed_id": "MW-1"}
        interventions.append(iv)

        photo_lat = lat + synth.RNG.uniform(-0.00008, 0.00008)
        photo_lon = lon + synth.RNG.uniform(-0.00008, 0.00008)
        taken_year = min(int(completed_on[:4]) + int(synth.RNG.integers(1, 3)), available_years[-1])
        taken_on = f"{taken_year}-{synth.RNG.integers(1, 12):02d}-{synth.RNG.integers(1, 28):02d}"
        filename = f"p{iv['id']:02d}.jpg"
        synth.make_placeholder_photo(config.PHOTOS_DIR / filename, itype, iv["name"], "real-data-demo")
        synth.write_gps_exif(config.PHOTOS_DIR / filename, photo_lat, photo_lon, taken_on)
        photos.append({"intervention_id": iv["id"], "file": filename, "lat": photo_lat, "lon": photo_lon,
                        "taken_on": taken_on, "bearing_deg": float(synth.RNG.integers(0, 359))})
        # Generic, non-rigged AI reading: with real satellite data the verdict
        # should come out of the actual pipeline, not be pre-designed like the
        # synthetic demo's deliberate mismatch/inconclusive cases.
        ai_cache[filename] = synth.build_ai_entry("corroborated", itype)

    with open(config.MANIFEST_PATH, "w") as f:
        json.dump({"interventions": interventions, "photos": photos}, f, indent=2)
    with open(config.AI_CACHE_PATH, "w") as f:
        json.dump(ai_cache, f, indent=2)
    with open(config.META_PATH, "w") as f:
        json.dump({
            "source": "real_landsat", "watershed_name": config.WATERSHED_NAME, "bbox": bbox,
            "years": available_years, "crs": epsg, "pixel_size_m": pixel_size,
            "grid": {"width": width, "height": height},
            "layers": ["lulc", "ndvi", "water", "moisture"], "wii_weights": config.WII_WEIGHTS,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }, f, indent=2)
    print("Real data pipeline complete.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true",
                         help="Skip the real pipeline and use synthetic demo data directly")
    args = parser.parse_args()

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    if args.synthetic:
        print("--synthetic flag set; using synthetic fallback data.")
        synth.main()
        return

    try:
        run_real_pipeline()
    except Exception as e:
        print(f"\nReal data pipeline failed: {e}")
        print("Falling back to synthetic demo data (offline-first rule)...\n")
        synth.main()


if __name__ == "__main__":
    main()
