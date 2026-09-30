"""Write GeoTIFFs and pre-rendered colour PNG overlays (+ bounds.json) so the
frontend can display layers as fast Leaflet ImageOverlays without doing any
raster processing in the browser.
"""
import json

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from PIL import Image as PILImage
import matplotlib



CMAPS = {
    "ndvi": ("RdYlGn", -0.2, 0.8),
    "mndwi": ("Blues", -0.5, 0.5),
    "ndmi": ("BrBG", -0.5, 0.5),
    "water_freq": ("Blues", 0.0, 1.0),
    "lulc": (None, None, None),  # categorical, handled separately
}

LULC_COLORS = {
    0: (0, 0, 0, 0),         # nodata, transparent
    1: (49, 130, 189, 255),  # water - blue
    2: (26, 118, 44, 255),   # dense vegetation - dark green
    3: (161, 217, 106, 255), # cropland/moderate - light green
    4: (222, 203, 137, 255), # scrub/sparse - tan
    5: (150, 150, 150, 255), # barren/built - grey
}


def write_geotiff(array, transform, crs, out_path, dtype="float32", nodata=np.nan):
    profile = {
        "driver": "GTiff", "height": array.shape[0], "width": array.shape[1],
        "count": 1, "dtype": dtype, "crs": crs, "transform": transform, "nodata": nodata,
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(array.astype(dtype), 1)


def render_index_png(array, layer_name, out_png_path):
    cmap_name, vmin, vmax = CMAPS[layer_name]
    norm = np.clip((array - vmin) / (vmax - vmin), 0, 1)
    rgba = (matplotlib.colormaps[cmap_name](norm) * 255).astype(np.uint8)
    rgba[np.isnan(array), 3] = 0  # transparent where no data
    PILImage.fromarray(rgba, mode="RGBA").save(out_png_path)


def render_lulc_png(lulc_array, out_png_path):
    rgba = np.zeros((*lulc_array.shape, 4), dtype=np.uint8)
    for cls, color in LULC_COLORS.items():
        rgba[lulc_array == cls] = color
    PILImage.fromarray(rgba, mode="RGBA").save(out_png_path)


def write_bounds_json(bbox, out_path):
    """bbox is [lon_min, lat_min, lon_max, lat_max] in EPSG:4326. Leaflet
    ImageOverlay wants [[south, west], [north, east]]."""
    bounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
    with open(out_path, "w") as f:
        json.dump({"bounds": bounds}, f)


def raster_bounds_wgs84(transform, width, height, crs):
    """Compute the WGS84 bounds of a raster grid, for bounds.json."""
    left, top = transform * (0, 0)
    right, bottom = transform * (width, height)
    minx, miny, maxx, maxy = min(left, right), min(top, bottom), max(left, right), max(top, bottom)
    return transform_bounds(crs, "EPSG:4326", minx, miny, maxx, maxy)
