from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class AIInterpretation(BaseModel):
    structure_type: str
    water_present: bool
    vegetation_level: str  # none|sparse|moderate|dense
    land_condition: str    # degraded|stable|improving
    structure_condition: str  # intact|damaged|silted
    confidence: float
    notes: str


class PhotoOut(BaseModel):
    id: int
    intervention_id: Optional[int]
    file: str
    lat: float
    lon: float
    taken_on: Optional[str]
    bearing_deg: Optional[float]
    ai: Optional[Dict[str, Any]]
    verdict: Optional[str]
    verdict_reason: Optional[str]

    class Config:
        from_attributes = True


class ImpactOut(BaseModel):
    ndvi_did: Optional[float]
    water_freq_did: Optional[float]
    ndmi_did: Optional[float]
    wii: Optional[float]
    n_clear_scenes: Optional[int]
    series: Optional[Dict[str, Any]] = None
    control_pixel_count: Optional[int] = None

    class Config:
        from_attributes = True


class InterventionOut(BaseModel):
    id: int
    name: str
    type: str
    lat: float
    lon: float
    completed_on: str
    micro_watershed_id: str
    verdict: Optional[str] = None
    wii: Optional[float] = None

    class Config:
        from_attributes = True


class InterventionDetailOut(InterventionOut):
    photo: Optional[PhotoOut] = None
    impact: Optional[ImpactOut] = None
