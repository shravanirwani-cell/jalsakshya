"""DEM -> drainage network -> watershed boundary, using pysheds.

pysheds 0.5's C-extension code still calls the removed `numpy.in1d`; patch it
to `numpy.isin` (a drop-in replacement) before importing pysheds, so it works
with modern numpy. This patch is applied once, at import time of this module.

Falls back gracefully: if pysheds/DEM processing fails, the caller should
use a simple bbox polygon as the watershed boundary and a synthetic stream
network (see scripts/make_synthetic_data.py), per PROTOTYPE_PLAN.md section 2.
"""
import json

import numpy as np
if not hasattr(np, "in1d"):
    np.in1d = np.isin

import rasterio
import pyproj
from shapely.geometry import shape, mapping, box
from shapely.ops import transform as shapely_transform


def _reproject_geom(geom, src_epsg, dst_epsg="EPSG:4326"):
    transformer = pyproj.Transformer.from_crs(src_epsg, dst_epsg, always_xy=True)
    return shapely_transform(transformer.transform, geom)


def compute_drainage(dem_path, out_flowacc_path, out_streams_path, out_watershed_path,
                      out_slope_path, src_epsg, stream_threshold_percentile=97):
    """Run pysheds pit-fill -> flow direction (D8) -> flow accumulation ->
    slope -> stream extraction -> watershed delineation from the
    highest-accumulation (outlet) cell. Writes flowacc/slope GeoTIFFs and
    streams/watershed GeoJSON reprojected to WGS84.

    Returns a dict with the in-memory arrays (acc, stream_mask, slope,
    transform) so the caller (e.g. the synthetic data generator) can place
    interventions on real stream pixels without re-reading files.

    Raises on failure so the caller can fall back to a bbox polygon.
    """
    from pysheds.grid import Grid

    grid = Grid.from_raster(str(dem_path))
    dem = grid.read_raster(str(dem_path))

    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)

    fdir = grid.flowdir(inflated)
    acc = grid.accumulation(fdir)
    slope = grid.cell_slopes(inflated, fdir)  # radians
    slope_deg = np.degrees(np.asarray(slope))

    with rasterio.open(dem_path) as src:
        profile = src.profile.copy()
    profile.update(dtype="float32", count=1, nodata=-1)
    with rasterio.open(out_flowacc_path, "w", **profile) as dst:
        dst.write(np.asarray(acc, dtype=np.float32), 1)
    with rasterio.open(out_slope_path, "w", **profile) as dst:
        dst.write(slope_deg.astype(np.float32), 1)

    acc_arr = np.asarray(acc)
    threshold = np.nanpercentile(acc_arr, stream_threshold_percentile)
    stream_mask_raster = acc > threshold  # must stay a pysheds Raster, not a plain ndarray
    branches = grid.extract_river_network(fdir, stream_mask_raster)
    stream_mask = np.asarray(stream_mask_raster).astype(bool)

    features_wgs84 = []
    for feat in branches["features"]:
        geom = shape(feat["geometry"])
        geom_wgs84 = _reproject_geom(geom, src_epsg)
        features_wgs84.append({"type": "Feature", "properties": feat.get("properties", {}),
                                "geometry": mapping(geom_wgs84)})
    with open(out_streams_path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features_wgs84}, f)

    # Outlet = highest-accumulation cell (lowest point of the main channel),
    # excluding a border margin: pysheds' catchment traversal breaks down for
    # an outlet sitting exactly on the grid edge (fewer valid flow-direction
    # neighbours there), silently returning a near-empty catchment.
    margin = 5
    interior_acc = acc_arr.copy()
    interior_acc[:margin, :] = -1
    interior_acc[-margin:, :] = -1
    interior_acc[:, :margin] = -1
    interior_acc[:, -margin:] = -1
    row, col = np.unravel_index(np.nanargmax(interior_acc), interior_acc.shape)

    catchment = grid.catchment(x=col, y=row, fdir=fdir, xytype="index")
    watershed_mask = np.asarray(catchment).astype(bool)  # full-grid mask, before clipping
    grid.clip_to(catchment)
    shapes = grid.polygonize()
    polys = [shape(geom) for geom, val in shapes if val == 1]
    if not polys:
        raise RuntimeError("No watershed polygon produced by pysheds")
    watershed_geom = max(polys, key=lambda p: p.area)
    watershed_geom_wgs84 = _reproject_geom(watershed_geom, src_epsg)

    with open(out_watershed_path, "w") as f:
        json.dump({"type": "Feature", "properties": {"name": "watershed"},
                   "geometry": mapping(watershed_geom_wgs84)}, f)

    return {
        "acc": acc_arr,
        "stream_mask": stream_mask,
        "watershed_mask": watershed_mask,
        "slope_deg": slope_deg,
        "transform": grid.affine,
    }


def bbox_watershed_fallback(bbox, out_watershed_path):
    """Simple rectangular watershed boundary from the bbox (WGS84), used when
    DEM-based delineation fails."""
    poly = box(*bbox)
    with open(out_watershed_path, "w") as f:
        json.dump({"type": "Feature", "properties": {"name": "watershed", "source": "bbox_fallback"},
                   "geometry": mapping(poly)}, f)
