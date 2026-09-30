"""Control-area difference-in-differences impact analysis.

For each intervention:
  1. Sample the local zone (3x3 pixels ~90m) and context zone (~500m buffer)
     around its point.
  2. Select control pixels: same watershed, same LULC class, similar slope
     (within +-3 deg), >500m from any intervention, at least 30 pixels.
  3. Compute mean pre/post index values (pre = years before completion year,
     post = years after) for treated and control.
  4. DiD = (treated_after - treated_before) - (control_after - control_before).
     This cancels out a good/bad monsoon that hit both areas equally.
"""
import numpy as np

from .. import config


def _pixel_indices(transform, lat, lon):
    """WGS84 lat/lon -> (row, col) in a raster given its affine transform
    (transform is defined in the raster's own CRS; caller must pass a
    transform that already accounts for reprojection of the point, i.e. we
    expect x, y in the raster's CRS units, not lat/lon, unless the raster is
    in EPSG:4326). This project keeps rasters in the UTM grid, so callers
    must reproject (lat, lon) to UTM before calling."""
    col, row = ~transform * (lon, lat)
    return int(row), int(col)


def sample_local_zone(arr, row, col, size=None):
    size = size or config.LOCAL_ZONE_PIXELS
    half = size // 2
    r0, r1 = max(0, row - half), min(arr.shape[0], row + half + 1)
    c0, c1 = max(0, col - half), min(arr.shape[1], col + half + 1)
    window = arr[r0:r1, c0:c1]
    valid = window[~np.isnan(window)]
    return float(np.mean(valid)) if valid.size else np.nan


def sample_context_zone(arr, row, col, pixel_size, radius_m=None):
    radius_m = radius_m or config.CONTEXT_ZONE_RADIUS_M
    radius_px = int(round(radius_m / pixel_size))
    r0, r1 = max(0, row - radius_px), min(arr.shape[0], row + radius_px + 1)
    c0, c1 = max(0, col - radius_px), min(arr.shape[1], col + radius_px + 1)
    yy, xx = np.mgrid[r0:r1, c0:c1]
    dist = np.sqrt((yy - row) ** 2 + (xx - col) ** 2)
    window = arr[r0:r1, c0:c1]
    mask = (dist <= radius_px) & (~np.isnan(window))
    valid = window[mask]
    return float(np.mean(valid)) if valid.size else np.nan


def sample_context_zone_water_fraction(mndwi_arr, row, col, pixel_size, radius_m=None):
    """Fraction of context-zone pixels with MNDWI > 0 in a single year's
    composite -- used to build a before/after water-frequency DiD."""
    radius_m = radius_m or config.CONTEXT_ZONE_RADIUS_M
    radius_px = int(round(radius_m / pixel_size))
    r0, r1 = max(0, row - radius_px), min(mndwi_arr.shape[0], row + radius_px + 1)
    c0, c1 = max(0, col - radius_px), min(mndwi_arr.shape[1], col + radius_px + 1)
    yy, xx = np.mgrid[r0:r1, c0:c1]
    dist = np.sqrt((yy - row) ** 2 + (xx - col) ** 2)
    window = mndwi_arr[r0:r1, c0:c1]
    mask = (dist <= radius_px) & (~np.isnan(window))
    valid = window[mask]
    return float(np.mean(valid > 0)) if valid.size else np.nan


def select_control_pixels(lulc_arr, slope_arr, intervention_rowcols, treated_row, treated_col,
                           treated_lulc_class, pixel_size, min_pixels=None):
    """Boolean mask of eligible control pixels: same LULC class as treated,
    similar slope, and far enough from every intervention point."""
    min_pixels = min_pixels or config.CONTROL_MIN_PIXELS
    treated_slope = slope_arr[treated_row, treated_col]

    same_class = lulc_arr == treated_lulc_class
    similar_slope = np.abs(slope_arr - treated_slope) <= config.CONTROL_SLOPE_TOLERANCE_DEG

    min_dist_px = config.CONTROL_MIN_DISTANCE_M / pixel_size
    yy, xx = np.mgrid[0:lulc_arr.shape[0], 0:lulc_arr.shape[1]]
    far_enough = np.ones(lulc_arr.shape, dtype=bool)
    for (r, c) in intervention_rowcols:
        dist = np.sqrt((yy - r) ** 2 + (xx - c) ** 2)
        far_enough &= dist > min_dist_px

    mask = same_class & similar_slope & far_enough
    if mask.sum() < min_pixels:
        # relax slope constraint if we can't find enough control pixels
        mask = same_class & far_enough
    return mask


def compute_did(treated_before, treated_after, control_before, control_after):
    if any(np.isnan(v) for v in [treated_before, treated_after, control_before, control_after]):
        return np.nan
    return (treated_after - treated_before) - (control_after - control_before)


def mean_over_years(arr_by_year, years, sampler_fn):
    """Average a per-year sampled value (e.g. context-zone mean) over a set
    of years, skipping years with no data."""
    vals = [sampler_fn(arr_by_year[y]) for y in years if y in arr_by_year]
    vals = [v for v in vals if not np.isnan(v)]
    return float(np.mean(vals)) if vals else np.nan


def normalize_wii_component(value, all_values):
    """Min-max normalise a DiD value against the full set of intervention
    DiD values, to 0-1, for combining into the WII."""
    all_values = np.array([v for v in all_values if not np.isnan(v)])
    if all_values.size == 0 or np.isnan(value):
        return 0.5  # neutral when no data
    lo, hi = all_values.min(), all_values.max()
    if hi == lo:
        return 0.5
    return float(np.clip((value - lo) / (hi - lo), 0, 1))


def compute_wii(ndvi_did, water_did, ndmi_did, photo_confidence,
                 all_ndvi_dids, all_water_dids, all_ndmi_dids):
    """Watershed Impact Index, 0-100. Weighted sum of min-max normalised DiD
    values across all interventions, plus AI photo confidence.
    Weights come from config.WII_WEIGHTS and are visible/configurable."""
    n_ndvi = normalize_wii_component(ndvi_did, all_ndvi_dids)
    n_water = normalize_wii_component(water_did, all_water_dids)
    n_ndmi = normalize_wii_component(ndmi_did, all_ndmi_dids)
    n_photo = float(np.clip(photo_confidence, 0, 1)) if photo_confidence is not None else 0.5

    w = config.WII_WEIGHTS
    score = (
        w["ndvi"] * n_ndvi +
        w["water"] * n_water +
        w["ndmi"] * n_ndmi +
        w["photo_confidence"] * n_photo
    )
    return round(score * 100, 1)
