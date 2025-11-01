#!/usr/bin/env python3
"""
Split Week Devotion DOCX into structured JSON (and CSV) for SoulStart.

Reads a DOCX file containing seven "Day 1"–"Day 7" devotional sections and extracts:
- day number
- title
- first detected Scripture reference
- list of text points

Outputs:
- week_cards.json  (for SoulStart app)
- week_cards.csv   (for spreadsheet/review)
"""

import json, csv, re
from pathlib import Path
from docx import Document

# --- Paths ---
BASE = Path(__file__).resolve().parents[1]
DEV = BASE / "devotions"
DOCX_PATH = DEV / "Week1_Devotion.docx"
JSON_OUT = DEV / "week1_cards.json"
CSV_OUT  = DEV / "week1_cards.csv"

# --- Regex patterns ---
DAY_RE = re.compile(r"^\s*(?:Day|DAY)\s*([1-7])\b[:\-]?\s*(.*)$")
SCRIPTURE_RE = re.compile(r"([1-3]?\s?[A-Za-z]+\s+\d{1,3}:\d{1,3}(?:[-–]\d{1,3})?)")

def split_week_doc(docx_path: Path) -> list[dict]:
    if not docx_path.exists():
        raise FileNotFoundError(f"Missing {docx_path}. Place your DOCX there.")

    doc = Document(str(docx_path))
    days, current = {}, None

    def start_day(num, title):
        nonlocal current
        key = f"Day {num}"
        current = {"day": key, "title": title.strip() or key, "scripture": "", "points": []}
        days[key] = current

    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if not text:
            continue
        m = DAY_RE.match(text)
        if m:
            start_day(m.group(1), m.group(2) or "")
            continue
        if current is None:
            continue  # ignore preface

        # Scripture?
        if not current["scripture"]:
            refs = SCRIPTURE_RE.findall(text)
            if refs:
                current["scripture"] = "; ".join(refs)
                continue
        # Otherwise treat as bullet/point
        current["points"].append(text)

    # Ensure 7 days, fill missing
    out = []
    for i in range(1, 8):
        key = f"Day {i}"
        out.append(days.get(key, {"day": key, "title": key, "scripture": "", "points": []}))

    return out[:7]

def write_outputs(data: list[dict], json_path: Path = JSON_OUT, csv_path: Path = CSV_OUT):
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Day", "Title", "Scripture", "Points"])
        for d in data:
            w.writerow([
                d["day"], d["title"], d["scripture"],
                "; ".join(d.get("points", []))
            ])

    print(f"✅ Wrote {json_path.name} and {csv_path.name} with {len(data)} days.")
    print("— Summary —")
    for d in data:
        print(f"{d['day']}: {d['title']} | {len(d['points'])} points | {d['scripture'] or 'No scripture'}")

def main():
    try:
        data = split_week_doc(DOCX_PATH)
        write_outputs(data)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
