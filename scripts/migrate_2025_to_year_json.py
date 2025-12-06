from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]  # go up from /scripts to project root
DEVOTIONS_ROOT = BASE_DIR / "devotions"
DATA_DIR = BASE_DIR / "data"
DEVOTIONS_DIR = DATA_DIR / "devotions"
DEVOTIONS_DIR.mkdir(exist_ok=True, parents=True)

def normalize_date_str(s: str) -> str | None:
    s = (s or "").strip()
    fmts = [
        "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y",
        "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y",
        "%b %d, %Y", "%B %d, %Y",
        "%d %b %Y", "%d %B %Y",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return None

def load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def iter_entries_with_dates(data):
    """
    Yield (iso_date, entry_dict) pairs from a JSON blob
    using flexible date detection.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            date_str = None
            # date in value first
            for field in ("date", "day", "Day", "DATE", "Date"):
                if field in v:
                    date_str = normalize_date_str(str(v.get(field, "")))
                    if date_str:
                        break
            # if still no date, maybe key is the date
            if not date_str:
                date_str = normalize_date_str(str(k))
            if date_str:
                yield date_str, v
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            date_str = None
            for field in ("date", "day", "Day", "DATE", "Date"):
                if field in item:
                    date_str = normalize_date_str(str(item.get(field, "")))
                    if date_str:
                        break
            if date_str:
                yield date_str, item

def normalize_entry(entry: dict, default_mode: str) -> dict:
    """
    Map old sunrise/sunset entry into a normalized structure.
    This mirrors your app.py normalize_entry.
    """
    if not entry:
        return {}
    out: dict = {}
    out["title"] = entry.get("title") or entry.get("Theme") or entry.get("theme")
    out["verse_ref"] = (
        entry.get("verse_ref")
        or entry.get("verseRef")
        or entry.get("VerseRef")
        or entry.get("scripture")
    )
    out["verse_text"] = (
        entry.get("verse_text")
        or entry.get("verseText")
        or entry.get("VerseText")
    )
    out["closing"] = (
        entry.get("closing")
        or entry.get("reflection")
        or entry.get("note")
        or entry.get("thought")
    )
    out["prayer"] = (
        entry.get("prayer")
        or entry.get("morning_prayer")
        or entry.get("morningPrayer")
        or entry.get("night_prayer")
        or entry.get("nightPrayer")
    )
    out["bg_image"] = entry.get("bg_image")
    t = (entry.get("type") or "").lower()
    out["type"] = (
        "morning"
        if t in ("sunrise", "morning")
        else ("night" if t in ("sunset", "night") else default_mode)
    )
    out["join_text"] = entry.get("join_text")
    out["join_url"] = entry.get("join_url")
    return out

def main():
    # date -> {"date": ..., "theme": "...", "morning": {...}, "night": {...}}
    merged: dict[str, dict] = {}

    # Scan devotions/<Month>/*.json (Sunrise + Sunset)
    if not DEVOTIONS_ROOT.exists():
        print("No devotions/ folder found, aborting.")
        return

    for month_dir in DEVOTIONS_ROOT.iterdir():
        if not month_dir.is_dir():
            continue
        for json_path in month_dir.glob("SoulStart_*.json"):
            name = json_path.name.lower()
            mode = "morning" if "sunrise" in name else "night"
            print(f"Processing {json_path} as {mode}...")
            data = load_json(json_path)
            if not data:
                continue
            for iso_date, raw_entry in iter_entries_with_dates(data):
                norm = normalize_entry(raw_entry, mode)
                # Ensure base container
                if iso_date not in merged:
                    merged[iso_date] = {
                        "date": iso_date,
                        "theme": norm.get("title") or "",
                        "morning": {},
                        "night": {},
                    }
                day = merged[iso_date]

                slot = norm.get("type") or mode
                block = {
                    "title": norm.get("title", ""),
                    "verse_ref": norm.get("verse_ref", ""),
                    "verse_text": norm.get("verse_text", ""),
                    # Use closing as the core heart meaning for legacy:
                    "silent_soul_meaning": norm.get("closing", ""),
                    "prayer": norm.get("prayer", ""),
                    # Keep a place for background image if ever needed:
                    "bg_image": norm.get("bg_image", ""),
                }
                if slot == "morning":
                    day["morning"] = block
                elif slot == "night":
                    day["night"] = block

    # Convert to a sorted list (by date)
    items = [merged[k] for k in sorted(merged.keys())]

    out_path = DEVOTIONS_DIR / "devotions_2025.json"
    out_path.parent.mkdir(exist_ok=True, parents=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(items)} entries to {out_path}")

if __name__ == "__main__":
    main()
