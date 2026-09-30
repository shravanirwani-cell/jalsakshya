"""Spectral index formulas. Keep these exact - do not silently change them
(see PROJECT_CONTEXT.md section 4 / 9).
"""
import numpy as np


def ndvi(nir, red):
    """(NIR - Red) / (NIR + Red) -> vegetation greenness."""
    denom = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denom != 0, (nir - red) / denom, np.nan)
    return out


def mndwi(green, swir1):
    """(Green - SWIR1) / (Green + SWIR1) -> open water."""
    denom = green + swir1
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denom != 0, (green - swir1) / denom, np.nan)
    return out


def ndmi(nir, swir1):
    """(NIR - SWIR1) / (NIR + SWIR1) -> moisture PROXY (not measured soil
    moisture - never label it as such in the UI or reports)."""
    denom = nir + swir1
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denom != 0, (nir - swir1) / denom, np.nan)
    return out


def classify_lulc(ndvi_arr, mndwi_arr, thresholds):
    """Simple rule-based LULC classes from indices. Classes (config.LULC_CLASSES):
    1 water, 2 dense_vegetation, 3 cropland_moderate, 4 scrub_sparse, 5 barren_built.
    """
    out = np.full(ndvi_arr.shape, 5, dtype=np.uint8)  # default: barren/built
    out[ndvi_arr > thresholds["sparse_veg_ndvi"]] = 4
    out[ndvi_arr > thresholds["moderate_veg_ndvi"]] = 3
    out[ndvi_arr > thresholds["dense_veg_ndvi"]] = 2
    out[mndwi_arr > thresholds["water_mndwi"]] = 1  # water overrides vegetation class
    nodata = np.isnan(ndvi_arr) | np.isnan(mndwi_arr)
    out = out.astype(np.uint8)
    out[nodata] = 0
    return out
