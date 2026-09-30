"""Pluggable satellite data provider interface.

Any provider must implement get_seasonal_composites(bbox, years, season) and
return, per year, a dict of band-name -> 2D numpy array (surface reflectance,
already scaled), all on the same grid, plus a "transform"/"crs" describing
the grid. See LandsatProvider for the reference implementation and
SrishtiDrishtiProvider for the not-yet-available stub.
"""
from abc import ABC, abstractmethod


class SatelliteProvider(ABC):
    @abstractmethod
    def get_seasonal_composites(self, bbox, years, season):
        """Return {year: {"green":arr, "red":arr, "nir":arr, "swir1":arr,
        "transform":affine.Affine, "crs":str, "cloud_free": bool}}"""
        raise NotImplementedError
