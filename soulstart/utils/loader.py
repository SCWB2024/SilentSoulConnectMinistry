# soulstart/utils/loader.py

import json
from pathlib import Path
from datetime import date as Date

# ---- Paths ----
BASE_DIR = Path(__file__).resolve().parent.parent      # /soulstart
DEVOTION_FILE = BASE_DIR / "devotions.json"            # adjust later if needed

# ---- Fallback values ----
FALLBACK = {
    "theme": "Silent Strength — God is Near",
    "verse_ref": "Psalm 46:1",
    "verse_text": "Verse unavailable — but His Word remains true.",
    "meaning": "A quiet reminder that God is still speaking.",
    "body": "Even without today’s devotion, His Word is enough. Stand firm.",
    "prayer": "Lord, anchor my heart today.",
    "share_link": "",
}

REQUIRED_FIELDS = [
    "date",
    "mode",
    "theme",
    "verse_ref",
    "verse_text",
    "meaning",
    "body",
    "prayer",
]


def get_placeholder_devotion(date_str: str, mode: str = "morning") -> dict:
    """Return a safe devotion if something goes wrong."""
    return {
        "date": date_str,
        "mode": mode,
        "theme": "Silent Strength",
        "verse_ref": FALLBACK["verse_ref"],
        "verse_text": FALLBACK["verse_text"],
        "meaning": FALLBACK["meaning"],
        "body": FALLBACK["body"],
        "prayer": FALLBACK["prayer"],
        "share_link": FALLBACK["share_link"],
        "error": True,
    }


def _normalize_devotion(raw: dict, date_str: str, mode: str) -> dict:
    """
    Ensure all required fields exist.
    raw = the dict stored under data[date][mode]
    """
    devo = dict(raw)  # copy so we don't mutate the original

    # Inject date and mode into the devotion
    devo.setdefault("date", date_str)
    devo.setdefault("mode", mode)

    # Validate required fields
    for field in REQUIRED_FIELDS:
        if field not in devo or devo[field] in (None, ""):
            if field in FALLBACK:
                devo[field] = FALLBACK[field]
            else:
                devo[field] = ""

    # share_link is optional but must exist
    if "share_link" not in devo or devo["share_link"] is None:
        devo["share_link"] = FALLBACK["share_link"]

    return devo


def _load_all_devotions():
    """
    Load the devotions.json file.

    Expected structure:
    {
      "2026-01-01": {
         "morning": { ... devotion fields ... },
         "night":   { ... devotion fields ... }
      },
      "2026-01-02": { ... }
    }
    """
    filepath = DEVOTION_FILE

    # Protect against broken or missing files
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[DEVOTION LOADER] Could not load {filepath}: {e}")
        return None

    if not isinstance(data, dict):
        print(f"[DEVOTION LOADER] {filepath} does not contain a dict.")
        return None

    return data


def load_devotion_for_date(target_date: Date, mode: str = "morning") -> dict:
    """
    Main entry point used by routes.py
    Always returns a devotion dict (never None).
    """

    date_str = target_date.isoformat()
    mode = (mode or "morning").lower().strip()

    if mode not in ("morning", "night"):
        # invalid mode -> fallback to morning
        mode = "morning"

    data = _load_all_devotions()
    if not data:
        # File missing or corrupted
        return get_placeholder_devotion(date_str, mode)

    # Protect against missing dates
    if date_str not in data:
        return get_placeholder_devotion(date_str, mode)

    day_record = data[date_str]

    # Protect against missing modes
    if not isinstance(day_record, dict) or mode not in day_record:
        return get_placeholder_devotion(date_str, mode)

    raw_devo = day_record[mode]

    if not isinstance(raw_devo, dict):
        return get_placeholder_devotion(date_str, mode)

    return _normalize_devotion(raw_devo, date_str, mode)

