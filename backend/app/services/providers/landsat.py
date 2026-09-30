"""Real satellite data provider: Landsat 8/9 Collection 2 Level-2 via the
Microsoft Planetary Computer STAC API.

This is a best-effort implementation used by prepare_data.py. If it cannot
reach the network, finds no clear scenes, or any library is unavailable,
prepare_data.py catches the failure and falls back to the synthetic
generator, per the project's offline-first rule.
"""
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

from ... import config
from ..grid_utils import bbox_to_utm_grid
from .base import SatelliteProvider

ASSET_MAP = {
    "green": "green",
    "red": "red",
    "nir": "nir08",
    "swir1": "swir16",
}
QA_ASSET = "qa_pixel"


def _read_and_reproject_asset(href, dst_crs, dst_transform, dst_width, dst_height):
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(href) as src:
            dst = np.zeros((dst_height, dst_width), dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=dst,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
            )
            return dst


def _qa_pixel_clear_mask(href, dst_crs, dst_transform, dst_width, dst_height):
    """Bit 1 = dilated cloud, bit 3 = cloud, bit 4 = cloud shadow in QA_PIXEL.
    Returns a boolean array: True = clear."""
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(href) as src:
            dst = np.zeros((dst_height, dst_width), dtype=np.uint16)
            reproject(
                source=rasterio.band(src, 1),
                destination=dst,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.nearest,
            )
    cloud_dilated = (dst & (1 << 1)) != 0
    cloud = (dst & (1 << 3)) != 0
    shadow = (dst & (1 << 4)) != 0
    return ~(cloud_dilated | cloud | shadow)


class LandsatProvider(SatelliteProvider):
    def __init__(self, epsg=None, pixel_size=None, cloud_cover_max=None):
        self.epsg = epsg or config.UTM_EPSG
        self.pixel_size = pixel_size or config.PIXEL_SIZE_M
        self.cloud_cover_max = cloud_cover_max or config.CLOUD_COVER_MAX

    def get_seasonal_composites(self, bbox, years, season):
        import planetary_computer
        from pystac_client import Client

        catalog = Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace,
        )

        dst_transform, width, height = bbox_to_utm_grid(bbox, self.epsg, self.pixel_size)
        results = {}

        for year in years:
            start = f"{year}-{season[0]}"
            end = f"{year}-{season[1]}"
            search = catalog.search(
                collections=["landsat-c2-l2"],
                bbox=bbox,
                datetime=f"{start}/{end}",
                query={"eo:cloud_cover": {"lt": self.cloud_cover_max}, "platform": {"in": ["landsat-8", "landsat-9"]}},
            )
            items = list(search.items())
            if not items:
                continue

            band_stacks = {b: [] for b in ASSET_MAP}
            for item in items:
                try:
                    clear = _qa_pixel_clear_mask(
                        item.assets[QA_ASSET].href, self.epsg, dst_transform, width, height
                    )
                    if clear.mean() < 0.5:
                        continue  # too cloudy over this bbox, skip scene
                    scene_bands = {}
                    for band_key, asset_name in ASSET_MAP.items():
                        dn = _read_and_reproject_asset(
                            item.assets[asset_name].href, self.epsg, dst_transform, width, height
                        )
                        refl = dn * config.LANDSAT_SCALE + config.LANDSAT_OFFSET
                        refl[~clear] = np.nan
                        scene_bands[band_key] = refl
                    for band_key in ASSET_MAP:
                        band_stacks[band_key].append(scene_bands[band_key])
                except Exception:
                    continue  # skip unreadable scene, keep going

            if not band_stacks["red"]:
                continue

            composite = {
                band_key: np.nanmedian(np.stack(arrs), axis=0)
                for band_key, arrs in band_stacks.items()
            }
            composite["transform"] = dst_transform
            composite["crs"] = self.epsg
            composite["n_scenes"] = len(band_stacks["red"])
            results[year] = composite

        return results
