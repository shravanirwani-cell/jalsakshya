from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Intervention, Photo, Impact

router = APIRouter()

VERDICT_ORDER = {"mismatch": 0, "inconclusive": 1, "corroborated": 2, None: 1}


def _photo_out(photo: Photo | None):
    if not photo:
        return None
    return {
        "id": photo.id, "intervention_id": photo.intervention_id, "file": photo.file,
        "lat": photo.lat, "lon": photo.lon, "taken_on": photo.taken_on,
        "bearing_deg": photo.bearing_deg, "ai": photo.ai,
        "verdict": photo.verdict, "verdict_reason": photo.verdict_reason,
    }


def _impact_out(impact: Impact | None):
    if not impact:
        return None
    return {
        "ndvi_did": impact.ndvi_did, "water_freq_did": impact.water_freq_did,
        "ndmi_did": impact.ndmi_did, "wii": impact.wii,
        "n_clear_scenes": impact.n_clear_scenes, "series": impact.series_json,
        "control_pixel_count": impact.control_pixel_count,
    }


@router.get("/interventions")
def list_interventions(db: Session = Depends(get_db)):
    """GeoJSON FeatureCollection of all interventions, with verdict and WII,
    for map markers."""
    features = []
    for iv in db.query(Intervention).all():
        photo = db.query(Photo).filter(Photo.intervention_id == iv.id).first()
        impact = db.query(Impact).filter(Impact.intervention_id == iv.id).first()
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [iv.lon, iv.lat]},
            "properties": {
                "id": iv.id, "name": iv.name, "type": iv.type,
                "completed_on": iv.completed_on, "micro_watershed_id": iv.micro_watershed_id,
                "verdict": photo.verdict if photo else None,
                "wii": impact.wii if impact else None,
            },
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/interventions/{intervention_id}")
def get_intervention(intervention_id: int, db: Session = Depends(get_db)):
    iv = db.get(Intervention, intervention_id)
    if not iv:
        raise HTTPException(status_code=404, detail="Intervention not found")
    photo = db.query(Photo).filter(Photo.intervention_id == iv.id).first()
    impact = db.query(Impact).filter(Impact.intervention_id == iv.id).first()
    return {
        "id": iv.id, "name": iv.name, "type": iv.type, "lat": iv.lat, "lon": iv.lon,
        "completed_on": iv.completed_on, "micro_watershed_id": iv.micro_watershed_id,
        "photo": _photo_out(photo), "impact": _impact_out(impact),
        "verdict": photo.verdict if photo else None,
        "wii": impact.wii if impact else None,
    }


@router.get("/ranking")
def ranking(db: Session = Depends(get_db)):
    """Interventions sorted so the ones most needing a field visit come
    first: mismatch, then inconclusive, then corroborated; ties broken by
    lower WII first."""
    rows = []
    for iv in db.query(Intervention).all():
        photo = db.query(Photo).filter(Photo.intervention_id == iv.id).first()
        impact = db.query(Impact).filter(Impact.intervention_id == iv.id).first()
        verdict = photo.verdict if photo else None
        wii = impact.wii if impact else 0
        rows.append({
            "id": iv.id, "name": iv.name, "type": iv.type,
            "verdict": verdict, "verdict_reason": photo.verdict_reason if photo else None,
            "wii": wii, "ndvi_did": impact.ndvi_did if impact else None,
            "water_freq_did": impact.water_freq_did if impact else None,
            "lat": iv.lat, "lon": iv.lon,
        })
    rows.sort(key=lambda r: (VERDICT_ORDER.get(r["verdict"], 1), r["wii"] if r["wii"] is not None else 0))
    return rows
