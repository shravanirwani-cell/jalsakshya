import datetime as dt

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean
)
from sqlalchemy.orm import relationship

from .db import Base


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # check_dam | farm_pond | trench | plantation
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    completed_on = Column(String, nullable=False)  # YYYY-MM-DD
    micro_watershed_id = Column(String, nullable=False, default="MW-1")

    photos = relationship("Photo", back_populates="intervention", cascade="all, delete-orphan")
    impact = relationship("Impact", back_populates="intervention", uselist=False, cascade="all, delete-orphan")


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=True)
    file = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    taken_on = Column(String, nullable=True)
    bearing_deg = Column(Float, nullable=True)
    ai = Column(JSON, nullable=True)
    verdict = Column(String, nullable=True)  # corroborated | mismatch | inconclusive
    verdict_reason = Column(String, nullable=True)
    uploaded = Column(Boolean, default=False)  # True if submitted via /api/photos (not demo seed)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    intervention = relationship("Intervention", back_populates="photos")


class Impact(Base):
    __tablename__ = "impacts"

    id = Column(Integer, primary_key=True)
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=False)
    ndvi_did = Column(Float, nullable=True)
    water_freq_did = Column(Float, nullable=True)
    ndmi_did = Column(Float, nullable=True)
    wii = Column(Float, nullable=True)
    n_clear_scenes = Column(Integer, nullable=True)
    series_json = Column(JSON, nullable=True)  # {years:[...], treated_ndvi:[...], control_ndvi:[...], ...}
    control_pixel_count = Column(Integer, nullable=True)

    intervention = relationship("Intervention", back_populates="impact")
