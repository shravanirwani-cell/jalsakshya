"""Central configuration for JalSakshya backend.

Keep weights, thresholds and paths here so they are visible and easy to tune,
per the project rule that methodology must not be hidden inside code.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PHOTOS_DIR = DATA_DIR / "photos"
DB_PATH = DATA_DIR / "jalsakshya.db"
MANIFEST_PATH = DATA_DIR / "manifest.json"
AI_CACHE_PATH = DATA_DIR / "ai_cache.json"
META_PATH = PROCESSED_DIR / "meta.json"

# Sample watershed: Ralegan Siddhi, Ahmednagar, Maharashtra (well-known watershed
# success story). bbox is WGS84 (lon_min, lat_min, lon_max, lat_max), roughly 10km x 10km.
WATERSHED_NAME = "Ralegan Siddhi Watershed (Demo)"
BBOX = [74.86, 18.90, 74.96, 19.00]  # lon_min, lat_min, lon_max, lat_max
UTM_EPSG = "EPSG:32643"  # UTM zone 43N, covers this longitude range
YEARS = list(range(2018, 2026))
SEASON_WINDOW = ("10-01", "12-15")  # post-monsoon, matched season across years
CLOUD_COVER_MAX = 30

# Landsat Collection 2 Level-2 surface reflectance scaling
LANDSAT_SCALE = 0.0000275
LANDSAT_OFFSET = -0.2

# Band mapping for Landsat 8/9 C2L2 (common_name aliases used by stackstac/pystac)
BAND_GREEN = "green"   # B3
BAND_RED = "red"       # B4
BAND_NIR = "nir08"     # B5
BAND_SWIR1 = "swir16"  # B6

PIXEL_SIZE_M = 30

# LULC classes derived from index thresholds (config, not hidden in code)
LULC_CLASSES = {
    1: "water",
    2: "dense_vegetation",
    3: "cropland_moderate",
    4: "scrub_sparse",
    5: "barren_built",
}
LULC_THRESHOLDS = {
    "water_mndwi": 0.0,       # MNDWI > 0 -> water
    "dense_veg_ndvi": 0.5,    # NDVI > 0.5 -> dense vegetation
    "moderate_veg_ndvi": 0.25,  # NDVI > 0.25 -> cropland/moderate
    "sparse_veg_ndvi": 0.1,   # NDVI > 0.1 -> scrub/sparse, else barren/built
}

# Zone definitions
LOCAL_ZONE_PIXELS = 3        # 3x3 pixels (~90m) around a point
CONTEXT_ZONE_RADIUS_M = 500  # ~500m buffer, downstream-biased

# Control-pixel selection rules
CONTROL_MIN_DISTANCE_M = 500   # must be >500m from any intervention
CONTROL_SLOPE_TOLERANCE_DEG = 3
CONTROL_MIN_PIXELS = 30

# Watershed Impact Index (WII) weights - must sum to 1.0, visible & configurable
WII_WEIGHTS = {
    "ndvi": 0.35,
    "water": 0.35,
    "ndmi": 0.15,
    "photo_confidence": 0.15,
}

# Verification thresholds
MIN_CLEAR_YEARS = 2         # fewer clear years -> inconclusive
MIN_AI_CONFIDENCE = 0.5     # below this -> inconclusive
WATER_FREQ_MISMATCH_THRESHOLD = 0.1
NDVI_DID_MISMATCH_THRESHOLD = 0.05  # "large positive DiD" while AI says sparse/none

# Photo -> nearest intervention search radius
PHOTO_MATCH_RADIUS_M = 300

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

STATIC_LAYERS_URL_PREFIX = "/static/layers"
STATIC_PHOTOS_URL_PREFIX = "/static/photos"
