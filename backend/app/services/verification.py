"""Photo <-> satellite verification engine.

Compares what the AI photo interpretation claims against satellite evidence
at the photo's location/year, and returns one of exactly three verdicts:
corroborated, mismatch, inconclusive. Never collapse this to pass/fail.

Each verdict comes with a human-readable reason that cites the actual
computed numbers (never a vague sentence).
"""
from .. import config


def verify(ai_result, local_mndwi, context_mndwi, ndvi_did, water_freq_local,
           n_clear_years, structure_type):
    """
    ai_result: dict from ai_photo.interpret() -- water_present, vegetation_level, confidence
    local_mndwi / context_mndwi: satellite MNDWI at the photo's nearest clear year, in the
        local (3x3) and context (~500m) zones
    ndvi_did: NDVI difference-in-differences for this intervention's zone
    water_freq_local: share of clear scenes with MNDWI > 0 in the local zone
    n_clear_years: number of clear satellite years available for this point
    structure_type: from the AI result (check_dam, farm_pond, trench, plantation...)

    Returns (verdict, reason).
    """
    confidence = ai_result.get("confidence", 0.5)
    water_present = ai_result.get("water_present", False)
    vegetation_level = ai_result.get("vegetation_level", "none")

    # Not enough evidence -> always Inconclusive, regardless of what the
    # numbers might otherwise suggest. 30m pixels cannot reliably resolve
    # small structures, so we refuse to force a verdict on weak evidence.
    if n_clear_years < config.MIN_CLEAR_YEARS:
        return "inconclusive", (
            f"Only {n_clear_years} clear satellite year(s) available at this location "
            f"(need at least {config.MIN_CLEAR_YEARS}); evidence is too thin to confirm or "
            f"refute the photo. Zone-level 30m analysis cannot resolve this reliably."
        )
    if confidence < config.MIN_AI_CONFIDENCE:
        return "inconclusive", (
            f"AI photo interpretation confidence is only {confidence:.2f} "
            f"(below the {config.MIN_AI_CONFIDENCE} threshold), so the claim cannot be "
            f"reliably checked against satellite evidence."
        )

    # Water-based check (check dams, farm ponds)
    if structure_type in ("farm_pond", "check_dam"):
        has_water_signal = (local_mndwi is not None and local_mndwi > 0) or \
                            (context_mndwi is not None and context_mndwi > 0)
        if water_present and has_water_signal:
            return "corroborated", (
                f"Photo reports water present; satellite MNDWI is "
                f"{local_mndwi:.3f} in the local zone and {context_mndwi:.3f} in the context "
                f"zone, both consistent with standing water."
            )
        if water_present and not has_water_signal and water_freq_local < config.WATER_FREQ_MISMATCH_THRESHOLD:
            return "mismatch", (
                f"Photo reports water present at a {structure_type.replace('_', ' ')}, but "
                f"satellite MNDWI shows no water signal (local {local_mndwi:.3f}, context "
                f"{context_mndwi:.3f}) and the zone's water frequency is only "
                f"{water_freq_local:.2f} across clear scenes. Recommend a field visit."
            )
        if not water_present:
            return "inconclusive", (
                f"Photo does not report standing water; satellite water frequency in this "
                f"zone is {water_freq_local:.2f}. A dry-season photo of a working structure "
                f"can look this way, so this needs a field check rather than a firm verdict."
            )

    # Vegetation-based check (plantations, trenches)
    if vegetation_level in ("dense", "moderate") and ndvi_did is not None:
        if ndvi_did > 0:
            return "corroborated", (
                f"Photo shows {vegetation_level} vegetation; satellite NDVI difference-in-"
                f"differences (treated vs control) is +{ndvi_did:.3f}, consistent with "
                f"vegetation gain attributable to the intervention rather than rainfall alone."
            )
        else:
            return "mismatch", (
                f"Photo shows {vegetation_level} vegetation, but the satellite NDVI "
                f"difference-in-differences is {ndvi_did:.3f} (no gain relative to the control "
                f"area). Recommend a field visit to confirm the photo date and location."
            )
    if vegetation_level in ("sparse", "none") and ndvi_did is not None:
        if ndvi_did > config.NDVI_DID_MISMATCH_THRESHOLD:
            return "mismatch", (
                f"Photo shows {vegetation_level} vegetation, but satellite NDVI DiD is "
                f"+{ndvi_did:.3f}, a larger vegetation gain than the photo suggests. "
                f"Recommend a field visit to confirm which location/date the photo covers."
            )
        return "inconclusive", (
            f"Photo shows {vegetation_level} vegetation and satellite NDVI DiD is "
            f"{ndvi_did:.3f}; evidence is too weak in either direction for a firm verdict."
        )

    return "inconclusive", (
        "Available photo and satellite evidence do not align with a clear rule; "
        "treat as needing a field check rather than forcing a verdict."
    )
