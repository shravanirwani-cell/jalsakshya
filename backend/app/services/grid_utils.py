"""Shared raster-grid helpers: building the common UTM grid for a bbox, and
converting WGS84 lat/lon points into row/col on that grid. Used by both the
real Landsat provider and the synthetic data generator so every raster in
data/processed shares one consistent grid.
"""
from pyproj import Transformer
from rasterio.warp import calculate_default_transform


def bbox_to_utm_grid(bbox, epsg, pixel_size):
    transform, width, height = calculate_default_transform(
        "EPSG:4326", epsg, 100, 100, *bbox, resolution=pixel_size
    )
    return transform, width, height


def latlon_to_rowcol(transform, epsg, lat, lon):
    transformer = Transformer.from_crs("EPSG:4326", epsg, always_xy=True)
    x, y = transformer.transform(lon, lat)
    col, row = ~transform * (x, y)
    return int(row), int(col)


def rowcol_to_latlon(transform, epsg, row, col):
    x, y = transform * (col, row)
    transformer = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(x, y)
    return lat, lon
