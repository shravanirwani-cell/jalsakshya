from .base import SatelliteProvider


class SrishtiDrishtiProvider(SatelliteProvider):
    """Stub for the government SRISHTI-DRISHTI satellite platform.

    Public API/download access for SRISHTI-DRISHTI was not confirmed during
    this prototype's build. This class documents the intended integration
    point: once access is available, implement get_seasonal_composites() the
    same way LandsatProvider does, and the rest of the pipeline (indices,
    impact, verification) needs no changes because it only depends on this
    interface, not on Landsat specifically.
    """

    def get_seasonal_composites(self, bbox, years, season):
        raise NotImplementedError(
            "SrishtiDrishtiProvider is a stub: SRISHTI-DRISHTI public API/download "
            "access was not confirmed for this prototype. Use LandsatProvider "
            "(real, open Landsat 8/9 data) instead, or implement this class "
            "once SRISHTI-DRISHTI access is available."
        )
