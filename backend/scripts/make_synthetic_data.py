"""Synthetic fallback data generator for JalSakshya.

Produces the same backend/data/processed/ outputs that a real Landsat run
(prepare_data.py) would, but from procedurally generated plausible rasters,
so the whole app works fully offline when real satellite/DEM downloads are
unavailable (PROTOTYPE_PLAN.md section 2 / PROJECT_CONTEXT.md rule 2).

Also writes the demo intervention/photo manifest (data/manifest.json) and the
AI photo cache (data/ai_cache.json), with deliberately designed corroborated /
mismatch / inconclusive cases so the verification engine has something real
to prove out.

Every output is tagged "source": "synthetic" in meta.json so the frontend can
show the "Demo Data" badge.

Run: python scripts/make_synthetic_data.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy.ndimage import gaussian_filter, distance_transform_edt
from PIL import Image, ImageDraw, ImageFont
import piexif

from app import config
from app.services import grid_utils, drainage, indices as idx_service, render

RNG = np.random.default_rng(42)

TYPE_CYCLE = ["check_dam", "farm_pond", "trench", "plantation"]
# 16 interventions: type, demo_case (corroborated | mismatch | inconclusive), completed_on
DEMO_PLAN = [
    ("check_dam",  "corroborated", "2020-03-15"),
    ("farm_pond",  "corroborated", "2020-11-02"),
    ("trench",     "corroborated", "2021-01-20"),
    ("plantation", "corroborated", "2021-06-10"),
    ("check_dam",  "mismatch",     "2021-09-05"),
    ("farm_pond",  "mismatch",     "2022-02-14"),
    ("trench",     "corroborated", "2020-07-22"),
    ("plantation", "inconclusive", "2021-11-30"),
    ("check_dam",  "mismatch",     "2022-04-18"),
    ("farm_pond",  "corroborated", "2020-05-05"),
    ("trench",     "corroborated", "2021-03-25"),
    ("plantation", "inconclusive", "2022-08-09"),
    ("check_dam",  "corroborated", "2020-12-01"),
    ("farm_pond",  "corroborated", "2021-07-17"),
    ("trench",     "corroborated", "2022-01-10"),
    ("plantation", "corroborated", "2021-10-05"),
]

TYPE_LABEL = {
    "check_dam": "Check Dam", "farm_pond": "Farm Pond",
    "trench": "Trench", "plantation": "Plantation",
}
TYPE_COLOR = {  # placeholder photo background colours by structure type
    "check_dam": (91, 122, 74), "farm_pond": (61, 111, 145),
    "trench": (133, 108, 66), "plantation": (58, 128, 78),
}


# ---------------------------------------------------------------- terrain --

def generate_dem(width, height):
    """A bowl-shaped synthetic terrain draining to one outlet at the south
    edge, with multi-frequency ridge noise so pysheds produces a realistic
    dendritic stream network rather than one straight channel."""
    y, x = np.mgrid[0:height, 0:width]
    outlet_row, outlet_col = height - 1, width // 2
    dist = np.sqrt((y - outlet_row) ** 2 + (x - outlet_col) ** 2)

    xn, yn = x / width, y / height
    ridges = (
        18 * np.sin(xn * 6 * np.pi + 1.3) * np.cos(yn * 5 * np.pi)
        + 12 * np.sin(xn * 13 * np.pi) * np.sin(yn * 9 * np.pi + 0.5)
        + 8 * np.cos(xn * 21 * np.pi + 0.7) * np.sin(yn * 15 * np.pi)
    )
    fine_noise = gaussian_filter(RNG.normal(0, 4, size=(height, width)), sigma=2)

    dem = dist * 0.55 + ridges + fine_noise
    dem -= dem.min()
    return dem.astype(np.float32)


def build_streams_and_watershed(dem, transform, width, height):
    """Try the real pysheds drainage pipeline on the synthetic DEM. If it
    fails for any reason, fall back to a bbox polygon and a simple hand-drawn
    stream line, per PROTOTYPE_PLAN.md section 2."""
    dem_path = config.PROCESSED_DIR / "dem.tif"
    render.write_geotiff(dem, transform, config.UTM_EPSG, dem_path)

    try:
        result = drainage.compute_drainage(
            dem_path=dem_path,
            out_flowacc_path=config.PROCESSED_DIR / "flowacc.tif",
            out_streams_path=config.PROCESSED_DIR / "streams.geojson",
            out_watershed_path=config.PROCESSED_DIR / "watershed.geojson",
            out_slope_path=config.PROCESSED_DIR / "slope.tif",
            src_epsg=config.UTM_EPSG,
        )
        return result["stream_mask"], result["slope_deg"], result["watershed_mask"]
    except Exception as e:
        print(f"  ! pysheds drainage failed ({e}); using bbox/simple-stream fallback")
        drainage.bbox_watershed_fallback(config.BBOX, config.PROCESSED_DIR / "watershed.geojson")

        # Simple diagonal stream line as GeoJSON, and a matching boolean mask
        stream_mask = np.zeros((height, width), dtype=bool)
        col = width // 2
        for row in range(height):
            col = np.clip(col + RNG.integers(-1, 2), 5, width - 5)
            stream_mask[row, max(0, col - 1):col + 2] = True
        pts = [grid_utils.rowcol_to_latlon(transform, config.UTM_EPSG, r, width // 2)
               for r in range(0, height, max(1, height // 20))]
        line = {"type": "Feature", "properties": {"strahler_order": 1},
                "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in pts]}}
        with open(config.PROCESSED_DIR / "streams.geojson", "w") as f:
            json.dump({"type": "FeatureCollection", "features": [line]}, f)

        slope_deg = np.abs(gaussian_filter(RNG.normal(5, 3, size=(height, width)), sigma=3))
        render.write_geotiff(slope_deg.astype(np.float32), transform, config.UTM_EPSG,
                              config.PROCESSED_DIR / "slope.tif")
        return stream_mask, slope_deg, np.ones((height, width), dtype=bool)


def pick_intervention_points(stream_mask, n, margin=12, min_spacing_px=18):
    """Farthest-point sampling of stream pixels, so the 16 interventions are
    spread across the drainage network rather than clustered."""
    candidates = np.argwhere(stream_mask)
    h, w = stream_mask.shape
    candidates = candidates[
        (candidates[:, 0] > margin) & (candidates[:, 0] < h - margin) &
        (candidates[:, 1] > margin) & (candidates[:, 1] < w - margin)
    ]
    if len(candidates) < n:
        raise RuntimeError("Not enough stream pixels to place interventions")

    chosen = [candidates[RNG.integers(len(candidates))]]
    for _ in range(n - 1):
        dists = np.min(
            [np.sqrt(((candidates - c) ** 2).sum(axis=1)) for c in chosen], axis=0
        )
        chosen.append(candidates[np.argmax(dists)])
    return [tuple(c) for c in chosen]


# ------------------------------------------------------------ index fields --

def generate_index_layers(width, height, transform, stream_mask, interventions):
    """Returns {year: {"ndvi":arr, "mndwi":arr, "ndmi":arr}} with a shared
    baseline (vegetation/moisture higher near streams), a per-year rainfall
    shock common to the whole grid (the confound that control-area DiD must
    cancel out), and per-intervention effects starting at completion date."""
    dist_to_stream_m = distance_transform_edt(~stream_mask) * config.PIXEL_SIZE_M

    ndvi_base = 0.15 + 0.35 * np.exp(-dist_to_stream_m / 300) + \
        gaussian_filter(RNG.normal(0, 0.05, size=(height, width)), sigma=3)
    # Streams here are ephemeral/seasonal (semi-arid), so baseline MNDWI does
    # NOT track distance-to-stream -- most of the channel is dry outside
    # monsoon. Water only shows up where an intervention or a pre-existing
    # pond actually holds it; this is what lets the "mismatch" demo cases
    # (photo claims water, satellite shows none) come through cleanly.
    mndwi_base = -0.35 + gaussian_filter(RNG.normal(0, 0.03, size=(height, width)), sigma=2)
    # a couple of small pre-existing ponds, unrelated to interventions
    for (pr, pc) in [(height // 5, width // 4), (2 * height // 3, 3 * width // 4)]:
        yy, xx = np.mgrid[0:height, 0:width]
        d = np.sqrt((yy - pr) ** 2 + (xx - pc) ** 2)
        mndwi_base = np.where(d < 2.5, 0.35, mndwi_base)
    ndmi_base = 0.5 * ndvi_base + 0.3 * np.clip(mndwi_base, 0, None) + \
        gaussian_filter(RNG.normal(0, 0.03, size=(height, width)), sigma=3)

    yy, xx = np.mgrid[0:height, 0:width]
    layers = {}
    for year in config.YEARS:
        rain_shock_veg = RNG.normal(0, 0.04)   # common shock: a wet/dry year
        rain_shock_water = RNG.normal(0, 0.02)

        ndvi = ndvi_base + rain_shock_veg
        mndwi = mndwi_base + rain_shock_water
        ndmi = ndmi_base + rain_shock_veg * 0.7

        for iv in interventions:
            completed_year = int(iv["completed_on"][:4])
            if year < completed_year:
                continue
            r, c = iv["_row"], iv["_col"]
            dist_px = np.sqrt((yy - r) ** 2 + (xx - c) ** 2)
            years_since = year - completed_year

            if iv["demo_case"] == "corroborated" and iv["type"] in ("check_dam", "farm_pond"):
                # sigma wide enough (~60m) that the photo's GPS jitter (a few
                # metres) can't accidentally land the point off the water signal
                bump = 0.55 * np.exp(-dist_px ** 2 / (2 * 2.0 ** 2))
                mndwi = mndwi + bump
                ndmi = ndmi + 0.2 * np.exp(-dist_px ** 2 / (2 * 2.5 ** 2))
            elif iv["demo_case"] == "corroborated" and iv["type"] in ("trench", "plantation"):
                amp = min(0.05 * years_since, 0.22)
                veg_bump = amp * np.exp(-dist_px ** 2 / (2 * 3.0 ** 2))
                ndvi = ndvi + veg_bump
                ndmi = ndmi + 0.5 * veg_bump
            elif iv["demo_case"] == "inconclusive":
                amp = min(0.015 * years_since, 0.03)  # tiny, weak-evidence effect
                ndvi = ndvi + amp * np.exp(-dist_px ** 2 / (2 * 1.0 ** 2))
            # mismatch cases: deliberately no satellite-visible effect baked in,
            # even though the (synthetic) AI photo cache will claim water/veg.

        layers[year] = {
            "ndvi": np.clip(ndvi, -1, 1).astype(np.float32),
            "mndwi": np.clip(mndwi, -1, 1).astype(np.float32),
            "ndmi": np.clip(ndmi, -1, 1).astype(np.float32),
        }
    return layers


# ------------------------------------------------------------------ photos --

def _deg_to_dms_rational(deg_float):
    deg_float = abs(deg_float)
    degrees = int(deg_float)
    minutes_float = (deg_float - degrees) * 60
    minutes = int(minutes_float)
    seconds = round((minutes_float - minutes) * 60 * 100)
    return [(degrees, 1), (minutes, 1), (seconds, 100)]


def write_gps_exif(path, lat, lon, taken_on):
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S",
        piexif.GPSIFD.GPSLatitude: _deg_to_dms_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W",
        piexif.GPSIFD.GPSLongitude: _deg_to_dms_rational(lon),
    }
    exif_ifd = {piexif.ExifIFD.DateTimeOriginal: f"{taken_on.replace('-', ':')} 10:30:00"}
    exif_dict = {"GPS": gps_ifd, "Exif": exif_ifd}
    piexif.insert(piexif.dump(exif_dict), str(path))


def make_placeholder_photo(path, intervention_type, name, demo_case):
    color = TYPE_COLOR[intervention_type]
    img = Image.new("RGB", (800, 600), color)
    draw = ImageDraw.Draw(img)
    # a simple horizon + "structure" block so it reads as a landscape photo, not a flat card
    draw.rectangle([0, 380, 800, 600], fill=(101, 87, 63))
    draw.rectangle([0, 0, 800, 380], fill=tuple(min(255, c + 40) for c in color))
    if intervention_type in ("check_dam", "farm_pond"):
        draw.rectangle([150, 300, 650, 400], fill=(70, 130, 180))
    try:
        font_big = ImageFont.load_default(size=36)
        font_small = ImageFont.load_default(size=22)
    except TypeError:
        font_big = font_small = ImageFont.load_default()
    draw.rectangle([0, 0, 800, 46], fill=(0, 0, 0))
    draw.text((10, 8), "DEMO / PLACEHOLDER PHOTO", fill=(255, 220, 0), font=font_big)
    draw.rectangle([0, 550, 800, 600], fill=(0, 0, 0))
    draw.text((10, 558), f"{name}  |  {TYPE_LABEL[intervention_type]}  |  case: {demo_case}",
               fill=(255, 255, 255), font=font_small)
    img.save(path, "jpeg")


AI_TEMPLATES = {
    ("corroborated", "check_dam"): dict(structure_type="check_dam", water_present=True,
        vegetation_level="moderate", land_condition="improving", structure_condition="intact",
        confidence=0.88, notes="Check dam holding visible water; banks show new vegetation."),
    ("corroborated", "farm_pond"): dict(structure_type="farm_pond", water_present=True,
        vegetation_level="moderate", land_condition="improving", structure_condition="intact",
        confidence=0.9, notes="Farm pond filled with water; surrounding fields look healthier."),
    ("corroborated", "trench"): dict(structure_type="trench", water_present=False,
        vegetation_level="dense", land_condition="improving", structure_condition="intact",
        confidence=0.82, notes="Contour trench with dense grass and shrub growth along the bund."),
    ("corroborated", "plantation"): dict(structure_type="plantation", water_present=False,
        vegetation_level="dense", land_condition="improving", structure_condition="intact",
        confidence=0.85, notes="Plantation rows well established with dense canopy cover."),
    ("mismatch", "check_dam"): dict(structure_type="check_dam", water_present=True,
        vegetation_level="sparse", land_condition="stable", structure_condition="intact",
        confidence=0.8, notes="Photo shows a full check dam reservoir after recent rain."),
    ("mismatch", "farm_pond"): dict(structure_type="farm_pond", water_present=True,
        vegetation_level="sparse", land_condition="stable", structure_condition="intact",
        confidence=0.77, notes="Farm pond appears to hold water at the time of the photo."),
    ("inconclusive", "plantation"): dict(structure_type="plantation", water_present=False,
        vegetation_level="sparse", land_condition="stable", structure_condition="intact",
        confidence=0.4, notes="Sapling stage plantation, hard to assess canopy from this angle."),
}


def build_ai_entry(demo_case, itype):
    key = (demo_case, itype)
    if key in AI_TEMPLATES:
        return dict(AI_TEMPLATES[key])
    # generic inconclusive fallback (low confidence -> verification.py forces Inconclusive)
    return dict(structure_type=itype, water_present=False, vegetation_level="sparse",
                land_condition="stable", structure_condition="intact", confidence=0.35,
                notes="Low-confidence reading; recommend field verification.")


# ------------------------------------------------------------------- main --

def main():
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    print("1/6 Building UTM grid...")
    transform, width, height = grid_utils.bbox_to_utm_grid(
        config.BBOX, config.UTM_EPSG, config.PIXEL_SIZE_M)
    width, height = int(width), int(height)
    print(f"    grid: {width} x {height} pixels at {config.PIXEL_SIZE_M}m")

    print("2/6 Generating terrain + drainage network...")
    dem = generate_dem(width, height)
    stream_mask, slope_deg, watershed_mask = build_streams_and_watershed(dem, transform, width, height)
    print(f"    stream pixels: {int(stream_mask.sum())}, inside watershed: {int((stream_mask & watershed_mask).sum())}")

    print("3/6 Placing 16 interventions on stream pixels inside the watershed...")
    points = pick_intervention_points(stream_mask & watershed_mask, n=len(DEMO_PLAN))
    interventions = []
    type_counters = {t: 0 for t in TYPE_CYCLE}
    for i, ((itype, demo_case, completed_on), (row, col)) in enumerate(zip(DEMO_PLAN, points)):
        type_counters[itype] += 1
        lat, lon = grid_utils.rowcol_to_latlon(transform, config.UTM_EPSG, row, col)
        interventions.append({
            "id": i + 1,
            "name": f"{TYPE_LABEL[itype]} {type_counters[itype]}",
            "type": itype,
            "lat": lat, "lon": lon,
            "completed_on": completed_on,
            "micro_watershed_id": "MW-1",
            "demo_case": demo_case,
            "_row": row, "_col": col,
        })

    print("4/6 Generating synthetic NDVI / MNDWI / NDMI / LULC layers per year...")
    layers_by_year = generate_index_layers(width, height, transform, stream_mask, interventions)

    mndwi_stack = np.stack([layers_by_year[y]["mndwi"] for y in config.YEARS])
    water_freq = np.mean(mndwi_stack > 0, axis=0).astype(np.float32)
    render.write_geotiff(water_freq, transform, config.UTM_EPSG, config.PROCESSED_DIR / "water_freq.tif")
    render.render_index_png(water_freq, "water_freq", config.PROCESSED_DIR / "water_freq.png")

    for year, arrs in layers_by_year.items():
        for name in ("ndvi", "mndwi", "ndmi"):
            render.write_geotiff(arrs[name], transform, config.UTM_EPSG,
                                  config.PROCESSED_DIR / f"{name}_{year}.tif")
            render.render_index_png(arrs[name], name, config.PROCESSED_DIR / f"{name}_{year}.png")
        lulc = idx_service.classify_lulc(arrs["ndvi"], arrs["mndwi"], config.LULC_THRESHOLDS)
        render.write_geotiff(lulc, transform, config.UTM_EPSG,
                              config.PROCESSED_DIR / f"lulc_{year}.tif", dtype="uint8", nodata=0)
        render.render_lulc_png(lulc, config.PROCESSED_DIR / f"lulc_{year}.png")

    bounds = render.raster_bounds_wgs84(transform, width, height, config.UTM_EPSG)
    render.write_bounds_json([bounds[0], bounds[1], bounds[2], bounds[3]], config.PROCESSED_DIR / "bounds.json")

    print("5/6 Generating placeholder photos with GPS EXIF...")
    photos = []
    for iv in interventions:
        photo_lat = iv["lat"] + RNG.uniform(-0.00008, 0.00008)  # within ~10m jitter
        photo_lon = iv["lon"] + RNG.uniform(-0.00008, 0.00008)
        completed = iv["completed_on"]
        taken_year = min(int(completed[:4]) + RNG.integers(1, 3), config.YEARS[-1])
        taken_on = f"{taken_year}-{RNG.integers(1, 12):02d}-{RNG.integers(1, 28):02d}"
        filename = f"p{iv['id']:02d}.jpg"
        make_placeholder_photo(config.PHOTOS_DIR / filename, iv["type"], iv["name"], iv["demo_case"])
        write_gps_exif(config.PHOTOS_DIR / filename, photo_lat, photo_lon, taken_on)
        photos.append({
            "intervention_id": iv["id"], "file": filename,
            "lat": photo_lat, "lon": photo_lon, "taken_on": taken_on,
            "bearing_deg": float(RNG.integers(0, 359)),
        })

    print("6/6 Writing manifest, AI cache, and meta.json...")
    ai_cache = {}
    for iv, photo in zip(interventions, photos):
        ai_cache[photo["file"]] = build_ai_entry(iv["demo_case"], iv["type"])

    manifest = {
        "interventions": [{k: v for k, v in iv.items() if not k.startswith("_")} for iv in interventions],
        "photos": photos,
    }
    with open(config.MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    with open(config.AI_CACHE_PATH, "w") as f:
        json.dump(ai_cache, f, indent=2)
    with open(config.META_PATH, "w") as f:
        json.dump({
            "source": "synthetic",
            "watershed_name": config.WATERSHED_NAME,
            "bbox": config.BBOX,
            "years": config.YEARS,
            "crs": config.UTM_EPSG,
            "pixel_size_m": config.PIXEL_SIZE_M,
            "grid": {"width": width, "height": height},
            "layers": ["lulc", "ndvi", "water", "moisture"],
            "wii_weights": config.WII_WEIGHTS,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }, f, indent=2)

    print("Done. Synthetic demo data written to", config.PROCESSED_DIR)


if __name__ == "__main__":
    main()
