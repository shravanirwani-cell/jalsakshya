from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .db import Base, engine
from .routers import layers, interventions, photos, analysis, reports

Base.metadata.create_all(bind=engine)

app = FastAPI(title="JalSakshya API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
config.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

app.mount(config.STATIC_LAYERS_URL_PREFIX, StaticFiles(directory=str(config.PROCESSED_DIR)), name="layers")
app.mount(config.STATIC_PHOTOS_URL_PREFIX, StaticFiles(directory=str(config.PHOTOS_DIR)), name="photos")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "jalsakshya-backend"}


app.include_router(layers.router, prefix="/api")
app.include_router(interventions.router, prefix="/api")
app.include_router(photos.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
