"""
migrate_2025_to_year_json.py

Builds data/devotions/devotions_2025.json by merging
all 2025 Sunrise/Sunset monthly JSON files.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

# -------- Paths --------
BASE_DIR = Path(__file__).resolve().parents[1]

# Prefer devotions_legacy/, else devotions/
LEGACY_ROOT = None
for name in ["devotions_legacy", "devotions"]:
    candidate = BASE_DIR / name
    if candidate.exists():
        LEGACY_ROOT = candidate
        break

if LEGACY_ROOT is None:
    print("No devotions_legacy/ or devotions/ folder found, aborting.")
    raise SystemExit(1)

DATA_DIR = BASE_DIR / "data"
DEV_DIR = DATA_DIR / "devotions"
DEV_DIR.mkdir(parents=True, exist_ok=True)

OUT_FILE = DEV_DIR / "devotions_2025.json"


def normalize_date_str(s: str | None) -> str | None:
    """Normalize many date formats to YYYY-MM-DD."""
    if not s:
        return None
    s = s.strip()
    fmts = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def iter_entries(data) -> list[tuple[str, dict]]:
    """
    Yield (iso_date, entry_dict) from legacy JSON structure.
    """
    results: list[tuple[str, dict]] = []

    if isinstance(data, dict):
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            norm = normalize_date_str(str(k))
            if not norm:
                # Try inside the dict
                dd = (
                    v.get("date")
                    or v.get("DATE")
                    or v.get("Date")
                    or v.get("day")
                    or v.get("Day")
                )
                norm = normalize_date_str(str(dd)) if dd else None
            if norm:
                results.append((norm, v))

    elif isinstance(data, list):
        for v in data:
            if not isinstance(v, dict):
                continue
            dd = (
                v.get("date")
                or v.get("DATE")
                or v.get("Date")
                or v.get("day")
                or v.get("Day")
            )
            norm = normalize_date_str(str(dd)) if dd else None
            if norm:
                results.append((norm, v))

    return results


def map_slot(entry: dict) -> dict:
    """
    Map legacy 2025 entry into a richer slot block,
    preserving declaration-style fields.
    """
    if entry is None:
        return {}

    return {
        "title": (
            entry.get("title")
            or entry.get("Theme")
            or entry.get("theme")
            or ""
        ),
        "verse_ref": entry.get("verse_ref") or entry.get("scripture") or "",
        "verse_text": entry.get("verse_text") or entry.get("verseText") or "",

        # 2025 declaration structure
        "encouragement_intro": (
            entry.get("encouragement_intro")
            or entry.get("intro")
            or ""
        ),
        "point1": entry.get("point1") or "",
        "point2": entry.get("point2") or "",
        "point3": entry.get("point3") or "",

        # Common closing + prayer
        "closing": (
            entry.get("closing")
            or entry.get("reflection")
            or entry.get("note")
            or entry.get("thought")
            or ""
        ),
        "prayer": (
            entry.get("prayer")
            or entry.get("morning_prayer")
            or entry.get("night_prayer")
            or ""
        ),
    }


def main():
    # Find all sunrise/sunset files for 2025 under legacy root
    # Assumes structure like devotions_legacy/August/SoulStart_Sunrise_Aug.json, etc.
    sunrise_files = list(LEGACY_ROOT.rglob("SoulStart_Sunrise_*.json"))
    sunset_files = list(LEGACY_ROOT.rglob("SoulStart_Sunset_*.json"))

    if not sunrise_files and not sunset_files:
        print(f"No Sunrise/Sunset JSON files found under {LEGACY_ROOT}, aborting.")
        raise SystemExit(1)

    sunrise_map: dict[str, dict] = {}
    sunset_map: dict[str, dict] = {}

    # Load Sunrise
    for path in sunrise_files:
        data = load_json(path)
        if not data:
            continue
        for iso, entry in iter_entries(data):
            # Only keep 2025
            if not iso.startswith("2025-"):
                continue
            sunrise_map[iso] = entry

    # Load Sunset
    for path in sunset_files:
        data = load_json(path)
        if not data:
            continue
        for iso, entry in iter_entries(data):
            if not iso.startswith("2025-"):
                continue
            sunset_map[iso] = entry

    all_dates = sorted(set(sunrise_map.keys()) | set(sunset_map.keys()))

    if not all_dates:
        print("No 2025 dates found in legacy files, aborting.")
        raise SystemExit(1)

    records = []
    for iso in all_dates:
        s_entry = sunrise_map.get(iso)
        n_entry = sunset_map.get(iso)

        # Skip dates that have neither side (should not happen)
        if not s_entry and not n_entry:
            continue

        # Use morning theme or fallback to night or blank
        theme = ""
        if s_entry:
            theme = (
                s_entry.get("theme")
                or s_entry.get("Theme")
                or s_entry.get("title")
                or ""
            )
        if not theme and n_entry:
            theme = (
                n_entry.get("theme")
                or n_entry.get("Theme")
                or n_entry.get("title")
                or ""
            )

        record = {
            "date": iso,
            "theme": theme,
            "morning": map_slot(s_entry) if s_entry else None,
            "night": map_slot(n_entry) if n_entry else None,
        }
        records.append(record)

    # Sort by date
    records.sort(key=lambda r: r["date"])

    # Warn if file exists
    if OUT_FILE.exists():
        print(f"WARNING: {OUT_FILE} already exists and will be OVERWRITTEN.")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(records)} days to {OUT_FILE}")


if __name__ == "__main__":
    main()
