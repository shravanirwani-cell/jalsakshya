import json

from fastapi import APIRouter, HTTPException, Query

from .. import config

router = APIRouter()

VALID_LAYERS = {"ndvi", "mndwi", "ndmi", "water_freq", "lulc"}


def _read_json(path):
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{path.name} not found; run prepare_data.py first")
    with open(path) as f:
        return json.load(f)


@router.get("/meta")
def get_meta():
    meta = _read_json(config.META_PATH)
    return meta


@router.get("/watershed")
def get_watershed():
    return _read_json(config.PROCESSED_DIR / "watershed.geojson")


@router.get("/streams")
def get_streams():
    return _read_json(config.PROCESSED_DIR / "streams.geojson")


@router.get("/layers/{name}/{year}")
def get_layer(name: str, year: int):
    if name not in VALID_LAYERS:
        raise HTTPException(status_code=400, detail=f"Unknown layer '{name}'. Valid: {sorted(VALID_LAYERS)}")
    png_path = config.PROCESSED_DIR / f"{name}_{year}.png" if name != "water_freq" \
        else config.PROCESSED_DIR / "water_freq.png"
    if not png_path.exists():
        raise HTTPException(status_code=404, detail=f"No {name} layer for year {year}")
    bounds = _read_json(config.PROCESSED_DIR / "bounds.json")["bounds"]
    return {"url": f"{config.STATIC_LAYERS_URL_PREFIX}/{png_path.name}", "bounds": bounds}
