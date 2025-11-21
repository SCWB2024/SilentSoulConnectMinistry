# whatsapp_auto.py  (v10.0 — single-run safe, site promo, cleaner env)
# Modes:
#   morning  -> loads SoulStart_Sunrise_<Mon>.json
#   night    -> loads SoulStart_Sunset_<Mon>.json
#   verses   -> loads verses.json (theme + links + 1 NLT line)
#
# Usage examples:
#   python scripts/whatsapp_auto.py --mode morning --dry-run
#   python scripts/whatsapp_auto.py --mode night --send --chat "Silent SoulConnect Ministry"
#   python scripts/whatsapp_auto.py --mode verses --open-only

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import webbrowser
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional

# Force UTF-8 output so emojis don't crash on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------- settings (env-aware) ----------
BASE_DIR = Path(__file__).resolve().parent.parent  # project root
DEVOTIONS_ROOT = Path(os.environ.get("DEVOTIONS_ROOT", str(BASE_DIR / "devotions")))
SITE_URL = os.environ.get("SITE_URL", "https://soulstart.onrender.com/")  # 👈 promote site
WHATSAPP_WEB_URL = "https://web.whatsapp.com/"

# Waits
FOCUS_WAIT_SECONDS = int(os.environ.get("FOCUS_WAIT_SECONDS", "7"))
DEFAULT_PASTE_DELAY = int(os.environ.get("PASTE_DELAY", "8"))
PAGE_BOOT_WAIT = int(os.environ.get("PAGE_BOOT_WAIT", "6"))  # initial load after opening WA Web

# Soft max—WhatsApp supports very long messages, but huge blocks are user-hostile
MAX_RECOMMENDED_CHARS = int(os.environ.get("MAX_RECOMMENDED_CHARS", "4000"))

# ---------- helpers ----------
def is_macos() -> bool:
    return platform.system().lower() == "darwin"

def countdown(label: str, seconds: int) -> None:
    if seconds <= 0:
        return
    for i in range(seconds, 0, -1):
        print(f"{label}: {i:>2}s", end="\r", flush=True)
        time.sleep(1)
    print(" " * 60, end="\r", flush=True)

def open_web() -> None:
    """Open WhatsApp Web and give browser time to render the shell."""
    print(f"[Info] Opening: {WHATSAPP_WEB_URL}")
    webbrowser.open(WHATSAPP_WEB_URL)
    countdown("Waiting for WhatsApp Web to boot", PAGE_BOOT_WAIT)

def read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warn] Could not read JSON: {path} ({e})")
        return None

def month_folder_for(dt: datetime) -> Path:
    return DEVOTIONS_ROOT / dt.strftime("%B")

def month_abbr(dt: datetime) -> str:
    return dt.strftime("%b")

def file_for_mode(dt: datetime, mode: str) -> Path:
    abbr = month_abbr(dt)
    if mode == "morning":
        fname = f"SoulStart_Sunrise_{abbr}.json"
    elif mode == "night":
        fname = f"SoulStart_Sunset_{abbr}.json"
    else:
        fname = f"SoulStart_Sunrise_{abbr}.json"
    return month_folder_for(dt) / fname

def normalize_datestr(s: str) -> Optional[str]:
    s = (s or "").strip()
    fmts = [
        "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y",
        "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y",
        "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None

def parse_today_entry(data, target_iso: str) -> Optional[dict]:
    if isinstance(data, dict):
        for key, val in data.items():
            norm = normalize_datestr(key)
            if norm is None and isinstance(val, dict):
                norm = normalize_datestr(str(val.get("date", "") or ""))
            if norm == target_iso:
                return val if isinstance(val, dict) else {"value": val}
        return None

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            if "date" in item and normalize_datestr(str(item.get("date", ""))) == target_iso:
                return item
            for k in ("day", "Day", "DATE", "Date"):
                if k in item and normalize_datestr(str(item.get(k, ""))) == target_iso:
                    return item
        return None
    return None

def build_message_from_entry(mode: str, entry: dict, dt: datetime) -> str:
    # Promote site instead of WhatsApp community
    promo_label = "🔗 Visit our website"
    promo_url = SITE_URL

    date_line = dt.strftime("%A, %B %d, %Y")

    def add(lines: list[str], val: Optional[str], prefix: str = "") -> None:
        if val:
            lines.append(f"{prefix}{val}" if prefix else val)

    title = entry.get("title") or entry.get("Theme") or entry.get("theme")
    verse_ref = entry.get("verse_ref") or entry.get("verseRef") or entry.get("VerseRef")
    verse_text = entry.get("verse_text") or entry.get("verseText") or entry.get("VerseText")
    pts = [p for p in (entry.get("point1"), entry.get("point2"), entry.get("point3")) if p]
    closing = entry.get("closing")
    prayer = entry.get("prayer")

    scripture = entry.get("scripture") or entry.get("Scripture") or entry.get("verse")
    reflection = entry.get("reflection") or entry.get("note") or entry.get("thought")
    declaration = entry.get("declaration")
    blessing = entry.get("blessing")
    morning_pr = entry.get("morning_prayer") or entry.get("morningPrayer")
    night_pr = entry.get("night_prayer") or entry.get("nightPrayer")

    sunrise = entry.get("sunrise") or entry.get("Sunrise") or entry.get("sun_rise")
    sunset = entry.get("sunset") or entry.get("Sunset") or entry.get("sun_set")

    is_new = any([title, verse_ref, verse_text, pts, closing, prayer])
    is_legacy = any([scripture, reflection, declaration, blessing, morning_pr, night_pr])

    header = "🌅 Sunrise Devotion" if mode == "morning" else "🌙 Sunset Devotion"
    lines: list[str] = [f"{header} — {date_line}"]

    if sunrise:
        add(lines, f"🕕 Sunrise: {sunrise}")
    if sunset:
        add(lines, f"🌇 Sunset: {sunset}")

    if is_new:
        if title:
            add(lines, f"\n*{title}*")
        if verse_ref or verse_text:
            vv = verse_ref or ""
            if verse_text:
                vv = f"{vv} — {verse_text}" if vv else verse_text
            add(lines, f"\n📖 {vv}")
        if pts:
            lines.append("")
            for i, p in enumerate(pts, 1):
                lines.append(f"{i}. {p}")
        if closing:
            add(lines, f"\n✍️ {closing}")
        add(lines, f"\n🙏 {prayer or ('Lord, order my steps today. Amen.' if mode == 'morning' else 'Lord, quiet my mind and keep me in Your care. Amen.')}")
        if promo_url:
            add(lines, f"\n{promo_label}\n{promo_url}")

    elif is_legacy:
        theme_or_title = title or entry.get("theme")
        if theme_or_title:
            add(lines, f"\n*{theme_or_title}*")
        if scripture:
            add(lines, f"\n📖 {scripture}")
        if reflection:
            add(lines, f"\n✍️ {reflection}")
        if declaration:
            add(lines, f"\n💬 {declaration}")
        if blessing:
            add(lines, f"\n🕊️ {blessing}")
        add(lines, f"\n🙏 {(morning_pr if mode == 'morning' else night_pr) or ('Lord, order my steps today. Amen.' if mode == 'morning' else 'Lord, quiet my mind and keep me in Your care. Amen.')}")
        if promo_url:
            add(lines, f"\n{promo_label}\n{promo_url}")

    else:
        verse_only = entry.get("verse")
        note_only = entry.get("note")
        if verse_only:
            add(lines, f"\n📖 {verse_only}")
        if note_only:
            add(lines, f"\n✍️ {note_only}")
        add(lines, f"\n🙏 {'Lord, order my steps today. Amen.' if mode == 'morning' else 'Lord, quiet my mind and keep me in Your care. Amen.'}")
        if promo_url:
            add(lines, f"\n{promo_label}\n{promo_url}")

    msg = "\n".join(lines).strip()
    if len(msg) > MAX_RECOMMENDED_CHARS:
        print(f"[Warn] Message is {len(msg)} chars (> {MAX_RECOMMENDED_CHARS}). Consider trimming.")
    return msg

def fallback_message(mode: str, dt: datetime) -> str:
    date_line = dt.strftime("%A, %B %d, %Y")
    base = (
        f"🌅 Good morning! {date_line}\n\n"
        "“This is the day the Lord has made; we will rejoice and be glad in it.” (Ps 118:24)\n\n"
        "Lord, order my steps today. Amen."
    ) if mode == "morning" else (
        f"🌙 Good night! {date_line}\n\n"
        "“In peace I will lie down and sleep…” (Ps 4:8)\n\n"
        "Lord, quiet my mind and keep me in Your care. Amen."
    )
    if SITE_URL:
        base += f"\n\n🔗 Visit our website\n{SITE_URL}"
    return base

def get_message_from_json(mode: str, dt: datetime) -> str:
    if mode in ("morning", "night"):
        json_path = file_for_mode(dt, mode)
        print(f"[Info] Looking for JSON: {json_path}")
        data = read_json(json_path)
        if data is None:
            try:
                entries = ", ".join(os.listdir(month_folder_for(dt)))
                print(f"[Hint] Files in {month_folder_for(dt)}: {entries}")
            except Exception:
                pass
            return fallback_message(mode, dt)

        iso_today = dt.strftime("%Y-%m-%d")
        entry = parse_today_entry(data, iso_today)
        if entry:
            msg = build_message_from_entry(mode, entry, dt).strip()
            if msg:
                return msg
        print(f"[Warn] No entry for {iso_today}. Using fallback.")
        return fallback_message(mode, dt)

    if mode == "verses":
        vfile = DEVOTIONS_ROOT / "verses.json"
        print(f"[Info] Loading verses from: {vfile}")
        data = read_json(vfile) or {}
        theme = data.get("theme") or "Theme Verses"
        videos = data.get("videos") or []
        texts = data.get("texts") or []

        lines: list[str] = [f"📖 SoulStart — {theme}"]

        for v in videos[:2]:
            url = (v or {}).get("url")
            label = (v or {}).get("label") or "Video"
            if url:
                lines.append(f"▪️ {label}: {url}")

        if texts:
            t = texts[0] or {}
            ref = t.get("ref")
            line = t.get("line")
            if ref:
                lines.append(f"▪️ {ref}: {line or ''}".strip())

        if SITE_URL:
            lines.append(f"🔗 Visit our website: {SITE_URL}")

        return "\n".join(lines).strip()

    return fallback_message("morning", dt)

def ensure_autogui():
    try:
        import pyautogui  # type: ignore
        import pyperclip  # type: ignore
        return pyautogui, pyperclip
    except Exception as e:
        print("[Error] Missing deps (install): pip install pyautogui pyperclip")
        print(f"        Details: {e}")
        sys.exit(2)

def quick_search_chat(pyautogui, chat: str) -> None:
    """
    Use WhatsApp Web quick search to jump to a chat by name.
    Ctrl/Cmd+K is the current quick search; fallback to Ctrl/Cmd+F.
    """
    print(f"[Info] Selecting chat: {chat!r}")
    meta_key = "command" if is_macos() else "ctrl"
    try:
        pyautogui.hotkey(meta_key, "k")
        time.sleep(0.2)
        pyautogui.typewrite(chat, interval=0.02)
        time.sleep(0.6)
        pyautogui.press("enter")
    except Exception:
        pyautogui.hotkey(meta_key, "f")
        time.sleep(0.2)
        pyautogui.typewrite(chat, interval=0.02)
        time.sleep(0.6)
        pyautogui.press("down")
        pyautogui.press("enter")

def do_paste(text: str, paste_delay: int, auto_send: bool) -> None:
    pyautogui, pyperclip = ensure_autogui()

    print("Click into the WhatsApp chat input now (or use --chat).")
    countdown("Focusing input in", FOCUS_WAIT_SECONDS)

    pyperclip.copy(text)
    if paste_delay and paste_delay > 0:
        time.sleep(paste_delay)

    # Paste
    meta_key = "command" if is_macos() else "ctrl"
    pyautogui.hotkey(meta_key, "v")
    time.sleep(0.15)

    if auto_send:
        pyautogui.press("enter")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open WhatsApp Web and paste SoulStart message (morning/night/verses)."
    )
    parser.add_argument("--mode", choices=["morning", "night", "verses", "custom"], default="morning")
    parser.add_argument("--date", type=str, default=None, help="Override date (YYYY-MM-DD) for testing.")
    parser.add_argument("--open-only", action="store_true", help="Open WhatsApp Web and exit (no paste).")
    parser.add_argument("--paste-delay", type=int, default=DEFAULT_PASTE_DELAY, help="Extra seconds before paste.")
    parser.add_argument("--dry-run", action="store_true", help="Print the message instead of opening/pasting.")
    parser.add_argument("--send", action="store_true", help="Auto-press Enter after pasting.")
    parser.add_argument("--chat", type=str, default=None, help="Quick-search and select a chat by name.")
    args = parser.parse_args()

    # Pick date
    if args.date:
        try:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print("[Error] --date must be YYYY-MM-DD. Using today instead.")
            dt = datetime.now()
    else:
        dt = datetime.now()

    effective_mode = "morning" if args.mode == "custom" else args.mode
    msg = get_message_from_json(effective_mode, dt)

    # Safety: never auto-send without an explicit --send
    if args.dry_run:
        print("\n----- DRY RUN: WhatsApp message preview -----\n")
        print(msg)
        print("\n----- END PREVIEW -----\n")
        sys.exit(0)

    # Open WhatsApp Web
    open_web()
    if args.open_only:
        sys.exit(0)

    # Optional: aim the chat before pasting
    if args.chat:
        pyautogui, _ = ensure_autogui()

        # Wait for WA UI to settle
        time.sleep(2)
        print("[Info] Focusing WhatsApp Web window…")
        # Click somewhere in the page to ensure focus (adjust if needed)
        pyautogui.click(300, 600)
        time.sleep(0.5)

        quick_search_chat(pyautogui, args.chat)

    do_paste(msg, args.paste_delay, args.send)
    print("✅ Message pasted" + (" and sent." if args.send else ". (Press Enter to send)"))
    sys.exit(0)


if __name__ == "__main__":
    main()
