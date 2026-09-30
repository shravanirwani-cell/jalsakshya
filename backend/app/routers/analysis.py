import json
from functools import lru_cache

import rasterio
from fastapi import APIRouter, HTTPException, Query

from .. import config
from ..services import grid_utils

router = APIRouter()


@lru_cache(maxsize=1)
def _meta():
    with open(config.META_PATH) as f:
        return json.load(f)


@router.get("/pixel")
def pixel_inspector(lat: float = Query(...), lon: float = Query(...)):
    """Index values (NDVI, MNDWI, NDMI) for every processed year at a clicked
    map point. NDMI is a moisture PROXY, not measured soil moisture."""
    meta = _meta()
    transform, width, height = grid_utils.bbox_to_utm_grid(meta["bbox"], meta["crs"], meta["pixel_size_m"])
    row, col = grid_utils.latlon_to_rowcol(transform, meta["crs"], lat, lon)
    if not (0 <= row < height and 0 <= col < width):
        raise HTTPException(status_code=400, detail="Point is outside the processed grid")

    series = []
    for year in meta["years"]:
        entry = {"year": year, "ndvi": None, "mndwi": None, "ndmi": None}
        for name in ("ndvi", "mndwi", "ndmi"):
            path = config.PROCESSED_DIR / f"{name}_{year}.tif"
            if path.exists():
                with rasterio.open(path) as src:
                    val = src.read(1)[row, col]
                    entry[name] = None if val != val else float(val)  # NaN check
        series.append(entry)

    return {
        "lat": lat, "lon": lon, "row": row, "col": col,
        "series": series,
        "note": "ndmi is a moisture PROXY (not measured soil moisture); "
                "values describe the 30m pixel, which may not resolve small structures.",
    }
