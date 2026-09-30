import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import Intervention, Photo, Impact
from ..services import report as report_service

router = APIRouter()

REPORTS_DIR = config.DATA_DIR / "reports"


def _meta():
    with open(config.META_PATH) as f:
        return json.load(f)


@router.get("/report/watershed.pdf")
def watershed_report(db: Session = Depends(get_db)):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    meta = _meta()

    with open(config.PROCESSED_DIR / "watershed.geojson") as f:
        watershed_geojson = json.load(f)
    with open(config.PROCESSED_DIR / "streams.geojson") as f:
        streams_geojson = json.load(f)

    interventions = []
    for iv in db.query(Intervention).all():
        photo = db.query(Photo).filter(Photo.intervention_id == iv.id).first()
        impact = db.query(Impact).filter(Impact.intervention_id == iv.id).first()
        interventions.append({
            "id": iv.id, "name": iv.name, "type": iv.type, "lat": iv.lat, "lon": iv.lon,
            "verdict": photo.verdict if photo else None, "wii": impact.wii if impact else None,
        })

    out_path = REPORTS_DIR / "watershed_report.pdf"
    try:
        report_service.build_watershed_report(
            out_path, meta["watershed_name"], meta["source"],
            dt.date.today().isoformat(), watershed_geojson, streams_geojson, interventions, {},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    return FileResponse(out_path, media_type="application/pdf", filename="jalsakshya_watershed_report.pdf")


@router.get("/report/{target}.pdf")
def intervention_report(target: str, db: Session = Depends(get_db)):
    if not target.isdigit():
        raise HTTPException(status_code=404, detail="Unknown report target; use 'watershed' or an intervention id")
    intervention_id = int(target)
    iv = db.get(Intervention, intervention_id)
    if not iv:
        raise HTTPException(status_code=404, detail="Intervention not found")

    meta = _meta()
    photo = db.query(Photo).filter(Photo.intervention_id == iv.id).first()
    impact = db.query(Impact).filter(Impact.intervention_id == iv.id).first()

    intervention_dict = {
        "name": iv.name, "type": iv.type,
        "ai": photo.ai if photo else None,
        "verdict": photo.verdict if photo else None,
        "verdict_reason": photo.verdict_reason if photo else None,
        "impact": {
            "ndvi_did": impact.ndvi_did, "water_freq_did": impact.water_freq_did,
            "ndmi_did": impact.ndmi_did, "wii": impact.wii,
        } if impact else None,
    }
    photo_path = config.PHOTOS_DIR / photo.file if photo else None
    series = impact.series_json if impact else None

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"intervention_{intervention_id}_report.pdf"
    try:
        report_service.build_intervention_report(
            out_path, intervention_dict, photo_path, series, dt.date.today().isoformat(), meta["source"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    return FileResponse(out_path, media_type="application/pdf",
                         filename=f"jalsakshya_{iv.name.replace(' ', '_')}_report.pdf")
