"""AI photo interpretation: returns a structured JSON reading of a geo-tagged
watershed photo.

Order of resolution (per PROTOTYPE_PLAN.md):
  1. Cached result in data/ai_cache.json, keyed by photo filename -- guarantees
     the demo works fully offline with no API key.
  2. Live Anthropic vision call, only if ANTHROPIC_API_KEY is set.
  3. Safe low-confidence fallback default (routes to Inconclusive downstream).
"""
import base64
import json

from .. import config

SCHEMA_PROMPT = """You are analysing a geo-tagged field photo from a watershed \
development programme (check dams, farm ponds, trenches, plantations). \
Return ONLY a JSON object with exactly these fields, no other text:
{
  "structure_type": "check_dam|farm_pond|trench|plantation|other",
  "water_present": true or false,
  "vegetation_level": "none|sparse|moderate|dense",
  "land_condition": "degraded|stable|improving",
  "structure_condition": "intact|damaged|silted",
  "confidence": 0.0 to 1.0,
  "notes": "one short sentence"
}"""

DEFAULT_LOW_CONFIDENCE = {
    "structure_type": "other",
    "water_present": False,
    "vegetation_level": "sparse",
    "land_condition": "stable",
    "structure_condition": "intact",
    "confidence": 0.3,
    "notes": "No cached AI reading and no live AI call available; low-confidence default used.",
}


def _load_cache():
    if config.AI_CACHE_PATH.exists():
        with open(config.AI_CACHE_PATH) as f:
            return json.load(f)
    return {}


def _call_live_anthropic(photo_path):
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    with open(photo_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    media_type = "image/jpeg" if str(photo_path).lower().endswith((".jpg", ".jpeg")) else "image/png"

    message = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=400,
        temperature=0,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {"type": "text", "text": SCHEMA_PROMPT},
            ],
        }],
    )
    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    return json.loads(text)


def interpret(photo_filename, photo_path=None):
    """Returns the AI interpretation dict for a photo. photo_filename is the
    cache key (e.g. 'p01.jpg'); photo_path is required only for a live call."""
    cache = _load_cache()
    if photo_filename in cache:
        return cache[photo_filename]

    if config.ANTHROPIC_API_KEY and photo_path:
        try:
            result = _call_live_anthropic(photo_path)
            required = {"structure_type", "water_present", "vegetation_level",
                        "land_condition", "structure_condition", "confidence", "notes"}
            if required.issubset(result.keys()):
                return result
        except Exception:
            pass  # fall through to safe default; never raise from here

    return dict(DEFAULT_LOW_CONFIDENCE)
