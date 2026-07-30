# -*- coding: utf-8 -*-

import json
from pathlib import Path
from datetime import date, datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEVOTION_FILE = PROJECT_ROOT / "devotions" / "devotions_2026.json"

BASE_URL = "https://soulstart.onrender.com"

SUPPORT_LINES = [
    "🤝 If this message blesses you, support the mission and help us reach more hearts.",
    "🌍 Help us expand this work to the Deaf and beyond — your support makes it possible.",
    "💛 Give what you can, when you can — every seed grows this ministry.",
    "✨ Be part of the impact — support, share, or simply stay connected.",
    "🙏 Your support helps keep these daily messages flowing to those who need it most.",
]


def load_devotions():
    if not DEVOTION_FILE.exists():
        return []

    with open(DEVOTION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_devotion(target_date: str):
    data = load_devotions()

    for item in data:
        if item.get("date") == target_date:
            return item

    return None


def get_support_line(target_date: str):
    try:
        day_index = datetime.strptime(target_date, "%Y-%m-%d").toordinal()
    except ValueError:
        day_index = date.today().toordinal()

    return SUPPORT_LINES[day_index % len(SUPPORT_LINES)]


def build_message(record, mode, target_date):
    section = record.get(mode, {}) or {}

    title = "🌅 SoulStart Sunrise" if mode == "morning" else "🌙 SoulStart Night"
    theme = record.get("theme", "")
    verse_ref = record.get("verse_ref", "")
    verse_text = record.get("verse_text", "")

    meaning = section.get("verse_meaning", "")
    body = section.get("body", [])
    prayer = section.get("prayer", "")

    link = f"{BASE_URL}/today?date={target_date}&mode={mode}"
    support_line = get_support_line(target_date)

    message = []

    message.append(f"{title} — {target_date}")

    if theme:
        message.append(f"\n✨ Theme: {theme}")

    if verse_ref and verse_text:
        message.append(f"\n📖 {verse_ref} — \"{verse_text}\"")

    if meaning:
        message.append(f"\n💡 {meaning}")

    if body:
        message.append("")

        # FIX: handle string vs list
        if isinstance(body, str):
            body_lines = [body]
        else:
            body_lines = body

        for line in body_lines:
            if str(line).strip().startswith("💖"):
                message.append(str(line).strip())
            else:
                message.append(f"💖 {line}")

    if prayer:
        message.append(f"\n🙏 Prayer: {prayer}")

    message.append("\n💬 You are not alone. Stay connected.")
    message.append(f"\n{support_line}")
    message.append(f"\n🔗 Join & Read: {link}")

    message_text = "\n".join(message)
    return message_text.encode("utf-8").decode("utf-8")

def build_whatsapp_message(target_date, mode, topic=""):
    record = get_devotion(target_date)

    if not record:
        return "No devotion found for this date."

    return build_message(record, mode, target_date)


if __name__ == "__main__":
    today_str = date.today().strftime("%Y-%m-%d")
    msg = build_whatsapp_message(today_str, "morning")
    print("\n--- WhatsApp Message ---\n")
    print(msg)