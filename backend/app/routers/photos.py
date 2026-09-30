import json
import math
import uuid
from functools import lru_cache
from pathlib import Path

import numpy as np
import piexif
import rasterio
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from fastapi.responses import FileResponse
from shapely.geometry import shape, Point
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import Intervention, Photo, Impact
from ..services import ai_photo, grid_utils, impact as impact_service, verification

router = APIRouter()


@lru_cache(maxsize=1)
def _meta():
    with open(config.META_PATH) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _watershed_polygon():
    with open(config.PROCESSED_DIR / "watershed.geojson") as f:
        geojson = json.load(f)
    return shape(geojson["geometry"])


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _dms_to_deg(dms, ref):
    degrees = dms[0][0] / dms[0][1]
    minutes = dms[1][0] / dms[1][1]
    seconds = dms[2][0] / dms[2][1]
    value = degrees + minutes / 60 + seconds / 3600
    if ref in (b"S", b"W", "S", "W"):
        value = -value
    return value


def _extract_gps_and_date(path):
    try:
        exif_dict = piexif.load(str(path))
    except Exception:
        return None, None, None
    gps = exif_dict.get("GPS", {})
    if piexif.GPSIFD.GPSLatitude not in gps or piexif.GPSIFD.GPSLongitude not in gps:
        return None, None, None
    lat = _dms_to_deg(gps[piexif.GPSIFD.GPSLatitude], gps.get(piexif.GPSIFD.GPSLatitudeRef, b"N"))
    lon = _dms_to_deg(gps[piexif.GPSIFD.GPSLongitude], gps.get(piexif.GPSIFD.GPSLongitudeRef, b"E"))
    bearing = None
    if piexif.GPSIFD.GPSImgDirection in gps:
        num, den = gps[piexif.GPSIFD.GPSImgDirection]
        bearing = num / den if den else None
    exif_ifd = exif_dict.get("Exif", {})
    taken_on = None
    raw_date = exif_ifd.get(piexif.ExifIFD.DateTimeOriginal)
    if raw_date:
        try:
            date_str = raw_date.decode() if isinstance(raw_date, bytes) else raw_date
            taken_on = date_str.split(" ")[0].replace(":", "-")
        except Exception:
            pass
    return (lat, lon), bearing, taken_on


def _read_year_raster(name, year):
    path = config.PROCESSED_DIR / f"{name}_{year}.tif"
    if not path.exists():
        return None
    with rasterio.open(path) as src:
        return src.read(1).astype(np.float32)


def _photo_detail(photo: Photo, intervention: Intervention | None, impact: Impact | None):
    return {
        "id": photo.id, "intervention_id": photo.intervention_id, "file": photo.file,
        "lat": photo.lat, "lon": photo.lon, "taken_on": photo.taken_on,
        "bearing_deg": photo.bearing_deg, "ai": photo.ai,
        "verdict": photo.verdict, "verdict_reason": photo.verdict_reason,
        "intervention": None if not intervention else {
            "id": intervention.id, "name": intervention.name, "type": intervention.type,
            "lat": intervention.lat, "lon": intervention.lon,
            "completed_on": intervention.completed_on,
        },
        "impact": None if not impact else {
            "ndvi_did": impact.ndvi_did, "water_freq_did": impact.water_freq_did,
            "ndmi_did": impact.ndmi_did, "wii": impact.wii,
            "n_clear_scenes": impact.n_clear_scenes, "series": impact.series_json,
        },
    }


@router.get("/photos/{photo_id}/file")
def get_photo_file(photo_id: int, db: Session = Depends(get_db)):
    photo = db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = config.PHOTOS_DIR / photo.file
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo file missing on disk")
    return FileResponse(path)


@router.post("/photos")
async def upload_photo(file: UploadFile = File(...), intervention_id: int | None = Form(None),
                        db: Session = Depends(get_db)):
    meta = _meta()
    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    filename = f"upload_{uuid.uuid4().hex[:10]}{suffix}"
    dest = config.PHOTOS_DIR / filename
    contents = await file.read()
    with open(dest, "wb") as f:
        f.write(contents)

    gps, bearing, taken_on = _extract_gps_and_date(dest)
    if gps is None:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="This photo does not contain GPS coordinates. Please upload a geo-tagged image.",
        )
    lat, lon = gps

    if not _watershed_polygon().contains(Point(lon, lat)):
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="This photo's location is outside the watershed boundary.",
        )

    # find nearest intervention within PHOTO_MATCH_RADIUS_M, unless caller specified one
    matched = None
    if intervention_id:
        matched = db.get(Intervention, intervention_id)
    else:
        best_dist, best_iv = None, None
        for iv in db.query(Intervention).all():
            d = _haversine_m(lat, lon, iv.lat, iv.lon)
            if d <= config.PHOTO_MATCH_RADIUS_M and (best_dist is None or d < best_dist):
                best_dist, best_iv = d, iv
        matched = best_iv

    ai_result = ai_photo.interpret(filename, dest)

    transform, width, height = grid_utils.bbox_to_utm_grid(meta["bbox"], meta["crs"], meta["pixel_size_m"])
    row, col = grid_utils.latlon_to_rowcol(transform, meta["crs"], lat, lon)
    latest_year = max(meta["years"])
    mndwi_arr = _read_year_raster("mndwi", latest_year)
    water_freq_path = config.PROCESSED_DIR / "water_freq.tif"

    local_mndwi = context_mndwi = water_freq_local = np.nan
    if mndwi_arr is not None:
        local_mndwi = impact_service.sample_local_zone(mndwi_arr, row, col)
        context_mndwi = impact_service.sample_context_zone(mndwi_arr, row, col, meta["pixel_size_m"])
    if water_freq_path.exists():
        with rasterio.open(water_freq_path) as src:
            water_freq_local = impact_service.sample_local_zone(src.read(1).astype(np.float32), row, col)

    matched_impact = None
    ndvi_did = None
    if matched:
        matched_impact = db.query(Impact).filter(Impact.intervention_id == matched.id).first()
        ndvi_did = matched_impact.ndvi_did if matched_impact else None

    verdict, reason = verification.verify(
        ai_result, local_mndwi, context_mndwi, ndvi_did,
        water_freq_local if not np.isnan(water_freq_local) else 0.0,
        len(meta["years"]), ai_result.get("structure_type", matched.type if matched else "other"),
    )

    photo = Photo(
        intervention_id=matched.id if matched else None, file=filename, lat=lat, lon=lon,
        taken_on=taken_on, bearing_deg=bearing, ai=ai_result, verdict=verdict,
        verdict_reason=reason, uploaded=True,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)

    return _photo_detail(photo, matched, matched_impact)
