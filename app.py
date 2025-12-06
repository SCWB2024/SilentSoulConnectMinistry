# app.py — SoulStart Devotion (HTTP dev, upgraded study routes) — v13 Full
from __future__ import annotations

import os
import json
import secrets
import logging
import subprocess
import sys
import webbrowser
from threading import Timer
from datetime import datetime, date
from pathlib import Path

from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]
from flask import (  # pyright: ignore[reportMissingImports]
    Flask, current_app, request, session, render_template, redirect,
    url_for, jsonify, send_from_directory, g, flash, abort
)
from functools import wraps
from flask_wtf import CSRFProtect  # pyright: ignore[reportMissingImports]
from flask_limiter import Limiter  # pyright: ignore[reportMissingImports]
from flask_limiter.util import get_remote_address  # pyright: ignore[reportMissingImports]
try:
    from flask_talisman import Talisman  # pyright: ignore[reportMissingImports]
except Exception:
    Talisman = None  # type: ignore

from logging.handlers import RotatingFileHandler


def is_authed() -> bool:
    return bool(session.get("authed"))

def require_auth(f):
    """Redirect to login if session is not authed."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_authed():
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

APP_VERSION = "v13"

# =============================================================================
# Env & paths
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "soulstart" / "static"

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

DEVOTIONS_ROOT = Path(
    os.environ.get("DEVOTIONS_ROOT", str(BASE_DIR / "devotions"))
)

# ---- Now safe to define files ----
VERSES_FILE = DATA_DIR / "verses.json"
DONATIONS_FILE = DATA_DIR / "donations.json"
REQUESTS_FILE = DATA_DIR / "requests.json"
VOLUNTEERS_FILE = DATA_DIR / "volunteers.json"
FEEDBACK_FILE = DATA_DIR / "feedback.json"

# Devotions: year-based JSON files under data/devotions/
DEVOTIONS_DIR = DATA_DIR / "devotions"
DEVOTIONS_DIR.mkdir(exist_ok=True)

# Load .env locally; on Render, env vars come from the dashboard
load_dotenv(BASE_DIR / ".env")

ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
IS_PROD = ENV == "production"
IS_HTTPS = os.environ.get("FORCE_HTTPS", "0").lower() in ("1", "true", "yes")

JOIN_URL = os.environ.get(
    "JOIN_URL",
    "https://chat.whatsapp.com/CdkN2V0h8vCDg2AP4saYfG"
)

WHATSAPP_GROUP_LINK = os.environ.get(
    "WHATSAPP_GROUP_LINK",
    JOIN_URL, 
)

SITE_THEME = os.environ.get("SITE_THEME", "Faith to Rise, Grace to Rest")
PAYPAL_LINK = os.environ.get("PAYPAL_LINK", "https://www.paypal.com/donate/?hosted_button_id=21H73722ER303860GND5CN2Y")

# ---------------- Admin credentials ----------------
# These MUST be set in .env locally and in Render's Environment tab.
ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL", "sscministry@outlook.com") or "").strip().lower()
ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD", "YourStrongPass") or "").strip()
ADMIN_BOOTSTRAP_TOKEN = os.environ.get(
    "ADMIN_BOOTSTRAP_TOKEN",
    "soulstart-2025-bootstrap",
)

# Backwards-compat for any old code still using ADMIN_PASS
ADMIN_PASS = ADMIN_PASSWORD

SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:5000")
PORT = int(os.environ.get("PORT", "5000"))
AUTO_OPEN = os.environ.get("AUTO_OPEN", "1").lower() in ("1", "true", "yes")
HOST = os.environ.get("HOST", "127.0.0.1")


def verify_admin_credentials(email: str, password: str) -> bool:
    """
    Compare submitted credentials with the configured admin account.
    Uses plain env values for now (no hashing) to keep behaviour simple.
    """
    if not ADMIN_PASSWORD:
        # No password configured on the server
        return False

    return (
        email.strip().lower() == ADMIN_EMAIL
        and password.strip() == ADMIN_PASSWORD
    )

# =============================================================================
# App init (single Flask app)
# =============================================================================
app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),      # points to soulstart/static
    static_url_path="/static",          # URL base for static files
    template_folder=str(TEMPLATES_DIR),
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-insecure")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config.update(
    SESSION_COOKIE_SECURE=IS_PROD or IS_HTTPS,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


# -----------------------------------------------------------------------------
# Security & middleware
# -----------------------------------------------------------------------------
if Talisman:
    csp = {
        "default-src": ["'self'"],
        "style-src":   ["'self'", "'unsafe-inline'"],
        "script-src":  ["'self'", "'unsafe-inline'"],
        "img-src":     ["'self'", "data:"],
        "connect-src": ["'self'"],
    }
    Talisman(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=["script", "style"],
        force_https=IS_PROD or IS_HTTPS,
    )

csrf = CSRFProtect(app)
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["200/day", "50/hour"])

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logs_dir = BASE_DIR / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
handler = RotatingFileHandler(logs_dir / "app.log", maxBytes=1_000_000, backupCount=5)
handler.setLevel(logging.INFO)
handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s: %(message)s [%(pathname)s:%(lineno)d]")
)
app.logger.addHandler(handler)
app.logger.info("App startup — %s", APP_VERSION)

# =============================================================================
# CSP (nonce) + HTTPS policy
# =============================================================================
def _gen_nonce(length: int = 16) -> str:
    return secrets.token_urlsafe(length)

@app.before_request
def _set_nonce():
    g.csp_nonce = _gen_nonce() if IS_PROD else ""

@app.context_processor
def _inject_nonce():
    return {"csp_nonce": lambda: g.get("csp_nonce", ""), "app_version": APP_VERSION}

if IS_PROD:
    csp = {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "https:"],
        "style-src":   ["'self'", "'unsafe-inline'"],
        "script-src":  ["'self'", "'unsafe-inline'"],
        "media-src": ["'self'", "data:", "blob:"],
        "font-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'self'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    }
    talisman = Talisman(
        app,
        content_security_policy=csp,
        force_https=True,
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        frame_options="SAMEORIGIN",
        referrer_policy="strict-origin-when-cross-origin",
    )

    @app.after_request
    def _apply_nonce(resp):
        # inject nonce into CSP header
        nonce = g.get("csp_nonce", "")
        if nonce:
            csp_header = resp.headers.get("Content-Security-Policy", "")
            csp_header = csp_header.replace("script-src 'self'", f"script-src 'self' 'nonce-{nonce}'")
            csp_header = csp_header.replace("style-src 'self'", f"style-src 'self' 'nonce-{nonce}'")
            resp.headers["Content-Security-Policy"] = csp_header
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return resp
else:
    csp = {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "blob:", "https:"],
        "style-src": ["'self'", "'unsafe-inline'"],  # dev convenience
        "script-src": ["'self'", "'unsafe-inline'"],  # dev convenience
        "media-src": ["'self'", "data:", "blob:"],
        "font-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'self'"],
    }
    talisman = Talisman(
        app,
        content_security_policy=csp,
        force_https=False,
        strict_transport_security=False,
        frame_options="SAMEORIGIN",
        referrer_policy="no-referrer-when-downgrade",
    )

# Dev: prevent stale template caching while iterating
@app.after_request
def add_no_cache(resp):
    if not IS_PROD:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
    return resp

@app.get("/health")
def health():
    return "ok", 200

# ---------------------------------------------------------------------------
# Donation log helpers
# ---------------------------------------------------------------------------

DONATIONS_FILE = DATA_DIR / "donations.json"


def load_json_list(path: Path):
    """Load a JSON list from file; return [] on error/missing."""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return [data]
    except Exception:
        return []


def append_json_list(path: Path, record: dict) -> None:
    """Append a record to a JSON list file."""
    items = load_json_list(path)
    items.append(record)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        # In worst case, do nothing rather than crash admin
        pass

# =============================================================================
# Helpers
# =============================================================================
def static_exists(rel_path: str) -> bool:
    rel_path = (rel_path or "").lstrip("/\\")
    return (STATIC_DIR / rel_path).exists()

def month_folder_for(d: date) -> Path:
    return DEVOTIONS_ROOT / d.strftime("%B")

def filename_for(d: date, mode: str) -> str:
    abbr = d.strftime("%b")
    return f"SoulStart_Sunrise_{abbr}.json" if mode == "morning" else f"SoulStart_Sunset_{abbr}.json"

def normalize_date_str(s: str) -> str | None:
    s = (s or "").strip()
    fmts = [
        "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y",
        "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return None

def load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
    
def _ctx(**kw):
    """Common context sent to templates."""
    base = dict(
        theme=SITE_THEME,
        join_url=JOIN_URL,
        today=datetime.now(),
        is_authed=("admin" in request.cookies if request else False),
    )
    base.update(kw)
    return base

def template_exists(rel_path: str) -> bool:
    return (TEMPLATES_DIR / rel_path).exists()

def find_entry_for_date(data, iso: str):
    if isinstance(data, dict):
        for k, v in data.items():
            norm = normalize_date_str(k)
            if norm is None and isinstance(v, dict):
                norm = normalize_date_str(str(v.get("date", "") or ""))
            if norm == iso:
                return v if isinstance(v, dict) else {"value": v}
        return None
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            if "date" in item and normalize_date_str(str(item.get("date", ""))) == iso:
                return item
            for key in ("day", "Day", "DATE", "Date"):
                if key in item and normalize_date_str(str(item.get(key, ""))) == iso:
                    return item
    return None

def normalize_entry(entry: dict, default_mode: str) -> dict:
    if not entry:
        return {}
    out: dict = {}
    out["title"] = entry.get("title") or entry.get("Theme") or entry.get("theme")
    out["verse_ref"] = entry.get("verse_ref") or entry.get("verseRef") or entry.get("VerseRef") or entry.get("scripture")
    out["verse_text"] = entry.get("verse_text") or entry.get("verseText") or entry.get("VerseText")
    out["points"] = [p for p in [entry.get("point1"), entry.get("point2"), entry.get("point3")] if p]
    out["closing"] = entry.get("closing") or entry.get("reflection") or entry.get("note") or entry.get("thought")
    out["prayer"] = (
        entry.get("prayer")
        or entry.get("morning_prayer")
        or entry.get("morningPrayer")
        or entry.get("night_prayer")
        or entry.get("nightPrayer")
    )
    out["bg_image"] = entry.get("bg_image")
    t = (entry.get("type") or "").lower()
    out["type"] = "morning" if t in ("sunrise", "morning") else ("night" if t in ("sunset", "night") else default_mode)
    out["join_text"] = entry.get("join_text")
    out["join_url"] = entry.get("join_url")
    return out

def _find_verse_image_url(fname: str) -> str | None:
    if not fname:
        return None
    bases = [STATIC_DIR / "img" / "verses", STATIC_DIR / "images", STATIC_DIR / "img"]
    for base in bases:
        if not base.exists():
            continue
        p = base / fname
        if p.exists():
            rel = p.relative_to(STATIC_DIR)
            return url_for("static", filename=str(rel).replace("\\", "/"))
        # case-insensitive match
        for entry in base.iterdir():
            if entry.is_file() and entry.name.lower() == fname.lower():
                rel = entry.relative_to(STATIC_DIR)
                return url_for("static", filename=str(rel).replace("\\", "/"))
    return None

# ---------- Devotions loader (year-based JSON: list OR dict) ----------

def _devotions_file_for_year(year: int) -> Path:
    """Return path like data/devotions/devotions_2026.json."""
    return DEVOTIONS_DIR / f"devotions_{year}.json"


def load_devotions_for_year(year: int) -> dict:
    """
    Load all devotions for a given year and normalize them into:
      { "YYYY-MM-DD": { ... } }

    Supports:
    - New 2026 format:
        [
          { "date": "2026-01-01", "theme": "...", "morning": {...}, "night": {...} },
          ...
        ]
    - Future dict format:
        {
          "2026-01-01": { "theme": "...", "morning": {...}, "night": {...} },
          ...
        }
    """
    path = _devotions_file_for_year(year)
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    # Case 1: already dict keyed by date
    if isinstance(data, dict):
        return data

    # Case 2: list of entries with "date"
    if isinstance(data, list):
        result: dict[str, dict] = {}
        for entry in data:
            if not isinstance(entry, dict):
                continue
            raw_date = entry.get("date", "")
            if not raw_date:
                continue
            norm = normalize_date_str(str(raw_date)) or str(raw_date)
            result[norm] = entry
        return result

    return {}


def load_devotion_for(target_date: date, slot: str = "morning") -> dict | None:
    """
    Get devotion record for a given date and slot ('morning' or 'night').

    Handles:
    - New form:
        { "date":"...", "theme":"...", "morning":{...}, "night":{...} }
    - Legacy form where the day-block itself is the devotion content.

    Returns a dict with normalized keys for the template:
      title, theme, verse_ref, body, verse_text,
      heart_picture, silent_soul_meaning, prayer, tags
    """
    all_for_year = load_devotions_for_year(target_date.year)
    day_key = target_date.isoformat()
    day_block = all_for_year.get(day_key)

    if not isinstance(day_block, dict):
        return None

    # Detect if we have the new "morning"/"night" slots structure
    has_slots = isinstance(day_block.get("morning"), dict) or isinstance(day_block.get("night"), dict)

    if has_slots:
        # New 2026-style structure
        theme = day_block.get("theme", "")
        slot_block = day_block.get(slot) or {}
    else:
        # Legacy: the whole entry is one devotion (no separate morning/night keys)
        theme = day_block.get("theme") or day_block.get("Theme") or ""
        slot_block = day_block

    if not isinstance(slot_block, dict):
        return None

    # Choose a good "body" text: quiet soul meaning > closing > verse_text > body
    body_text = (
        slot_block.get("silent_soul_meaning")
        or slot_block.get("closing")
        or slot_block.get("verse_text")
        or slot_block.get("body")
        or ""
    )

    return {
        "title": (
            slot_block.get("title")
            or slot_block.get("Theme")
            or slot_block.get("theme")
            or ""
        ),
        "theme": theme,
        "verse_ref": (
            slot_block.get("verse_ref")
            or slot_block.get("scripture")
            or ""
        ),
        "body": body_text,
        "verse_text": slot_block.get("verse_text", ""),
        "heart_picture": slot_block.get("heart_picture", ""),
        "silent_soul_meaning": slot_block.get("silent_soul_meaning", ""),
        "prayer": (
            slot_block.get("prayer")
            or slot_block.get("morning_prayer")
            or slot_block.get("night_prayer")
            or ""
        ),
        "tags": slot_block.get("tags") or [],
    }


# =============================================================================
# Routes
# =============================================================================

# ---------- Home ----------
@app.route("/", endpoint="home")
def home():
    return render_template(
        "home.html",
        theme=SITE_THEME,
        join_url=JOIN_URL,
        active="home",
        hero_bg=None,
        hero_class="",
        hero_title="",
    )

from datetime import datetime, date
from pathlib import Path
import json, os

# ---------- Today ----------
# ---------- Today (Sunrise / Sunset devotions) ----------

@app.route("/today", endpoint="today")
def today_view():
    today = datetime.now().date()

    # Default placeholders if a devotion is missing
    morning = {
        "title": "Morning Mercies",
        "verse_ref": "Lamentations 3:22–23",
        "body": "His mercies are new every morning; great is Your faithfulness.",
    }
    night = {
        "title": "Quiet Rest",
        "verse_ref": "Psalm 4:8",
        "body": "In peace I will both lie down and sleep; for You alone, O Lord, make me dwell in safety.",
    }

    m = load_devotion_for(today, "morning")
    if m:
        morning = m

    n = load_devotion_for(today, "night")
    if n:
        night = n

    return render_template(
        "today.html",
        today=today,
        morning=morning,
        night=night,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        active="today",
    )

    # ---------- LOAD FROM devotions/<Month>/SoulStart_Sunrise_XXX.json ----------
    root = Path(app.root_path)
    devo_dir = root / "devotions" / month_full

    sunrise_file = devo_dir / f"SoulStart_Sunrise_{month_abbr}.json"
    sunset_file = devo_dir / f"SoulStart_Sunset_{month_abbr}.json"

    def load_for_today(path: Path):
        """Return the entry for today's date from a JSON file, or None."""
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            app.logger.exception("Error reading %s: %s", path, e)
            return None

        # file can be list or single dict
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("date") == today_iso:
                    return item
        elif isinstance(data, dict):
            # either one devotion per file, or grouped by date
            if data.get("date") == today_iso:
                return data
            if today_iso in data and isinstance(data[today_iso], dict):
                return data[today_iso]
        return None

    sunrise = load_for_today(sunrise_file)
    sunset = load_for_today(sunset_file)

    if sunrise:
        tmp = morning.copy()
        tmp.update(sunrise)
        morning = tmp

    if sunset:
        tmp = night.copy()
        tmp.update(sunset)
        night = tmp

    # ---------- Build WhatsApp share text from MORNING ----------
    date_str = today.strftime("%A, %B %d, %Y")
    whatsapp_share_text = ""
    if morning:
        lines = [
            f"🌅 SoulStart Sunrise – {date_str}",
            "",
            f"Theme {morning.get('title', '')}",
            f"📖 Scripture: {morning.get('verse_ref', '')}-- "
            f"\"{(morning.get('verse_text') or '').strip()}\"",
            "",
            (morning.get("encouragement_intro") or "").strip(),
            "",
            (morning.get("point1") or "").strip(),
            (morning.get("point2") or "").strip(),
            (morning.get("point3") or "").strip(),
            (morning.get("closing") or "").strip(),
            "",
            f"🙏 Prayer:  {(morning.get('prayer') or '').strip()}",
            "",
            f"🔗 Share Us:  {WHATSAPP_GROUP_LINK}",
        ]
        whatsapp_share_text = "\n".join([l for l in lines if l])

    return render_template(
        "today.html",
        today=today,
        morning=morning,
        night=night,
        whatsapp_share_text=whatsapp_share_text,
        whatsapp_group_link=WHATSAPP_GROUP_LINK,
        theme=SITE_THEME,
        active="today",
    )

# ---------- Verses (Promise Cards) ----------
def _safe_static(filename: str) -> str | None:
    """Return static URL if file exists; else None."""
    path = Path(app.static_folder) / filename
    if path.exists():
        return url_for("static", filename=filename)
    return None


def load_verses() -> list[dict]:
    """
    Load verse cards from data/verses.json if present.
    Fallback to built-in defaults if missing or invalid.
    """
    fallback = [
        {
            "image": "Firelight.jpg",
            "ref": "Isaiah 60:1 (NLV)",
            "title": "Firelight",
            "note": "God is calling you to rise and shine, even when life feels dark."
        },
        {
            "image": "Stillness.jpg",
            "ref": "Psalm 46:10 (NLV)",
            "title": "Stillness",
            "note": "A reminder to pause, breathe, and know that God is in control."
        },
        {
            "image": "Restoration.jpg",
            "ref": "Joel 2:25 (NLV)",
            "title": "Restoration",
            "note": "God can restore the years and moments that feel wasted or broken."
        },
        {
            "image": "Delight.jpg",
            "ref": "Isaiah 58:13–14",
            "title": "Delight",
            "note": "There is joy and freedom when we delight ourselves in the Lord."
        },
        {
            "image": "Presence.jpg",
            "ref": "Exodus 33:14",
            "title": "Presence",
            "note": "His presence brings rest to a tired mind and a heavy heart."
        },
        {
            "image": "Refuge.jpg",
            "ref": "Psalm 62:8",
            "title": "Refuge",
            "note": "You can pour out your heart; God is a safe place, not a harsh judge."
        },
        {
            "image": "Overflow.jpg",
            "ref": "Psalm 23:5",
            "title": "Overflow",
            "note": "Even in hard seasons, God can cause your cup to overflow with grace."
        }
    ]

    if not VERSES_FILE.exists():
        return fallback

    try:
        with VERSES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return fallback
    except Exception:
        return fallback


@app.route("/verses")
def verses():
    """Grid of theme verses."""
    today = datetime.now().date()
    verses_data = load_verses()

    cards = []
    for idx, v in enumerate(verses_data):
        image = v.get("image", "")
        src = _safe_static(f"img/verses/{image}") if image else None

        cards.append({
            "id": idx,
            "src": src,
            "ref": v.get("ref", "Untitled"),
            "caption": v.get("title", ""),
            "note": v.get("note", ""),
            "alt": f"Theme verse — {v.get('ref', '')}"
        })

    return render_template(
        "verses.html",
        today=today,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        cards=cards,
        page_bg_class="",
        active="verses"
    )


@app.route("/verses/<int:card_id>")
def verse_detail(card_id: int):
    """Detail view for a single verse card."""
    verses_data = load_verses()

    if card_id < 0 or card_id >= len(verses_data):
        abort(404)

    v = verses_data[card_id]
    image = v.get("image", "")
    src = _safe_static(f"img/verses/{image}") if image else None

    card = {
        "id": card_id,
        "src": src,
        "ref": v.get("ref", "Untitled"),
        "title": v.get("title", ""),
        "note": v.get("note", ""),
        "alt": f"Theme verse — {v.get('ref', '')}"
    }

    return render_template(
        "verse_detail.html",
        card=card,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        active="verses"
    )


# ---------- Prayer ----------
@app.route("/prayer", methods=["GET", "POST"])
def prayer():
    if request.method == "POST":
        flash("🙏 Your prayer request was received.", "success")
        return redirect(url_for("prayer"))
    return render_template("prayer.html", theme=SITE_THEME, join_url=JOIN_URL, active="prayer")

# ---------- About ----------
@app.route("/about")
def about():
    return render_template("about.html", theme=SITE_THEME, join_url=JOIN_URL, active="about")

# ---------- Volunteer ----------
@app.route("/volunteer", methods=["GET", "POST"])
def volunteer():
    if request.method == "POST":
        flash("💚 Thank you for offering your skills!", "success")
        return redirect(url_for("volunteer"))
    return render_template("volunteer.html", theme=SITE_THEME, join_url=JOIN_URL, active="volunteer")

# ---------- Donation ----------
@app.route("/admin/donations", methods=["GET", "POST"])
@require_auth
def admin_donations():
    error = None
    success = None

    if request.method == "POST":
        donor_name = (request.form.get("donor_name") or "").strip()
        amount_raw = (request.form.get("amount") or "").strip()
        currency = (request.form.get("currency") or "USD").strip().upper()
        note = (request.form.get("note") or "").strip()
        date_str = (request.form.get("date") or "").strip()

        if not date_str:
            # default to today if not provided
            date_str = datetime.now().date().isoformat()

        try:
            amount = float(amount_raw)
        except ValueError:
            amount = None

        if amount is None or amount <= 0:
            error = "Please enter a valid donation amount."
        else:
            record = {
                "date": date_str,
                "donor_name": donor_name,
                "amount": amount,
                "currency": currency,
                "note": note,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            append_json_list(DONATIONS_FILE, record)
            success = "Donation recorded successfully."

    # Always load current list
    items = load_json_list(DONATIONS_FILE)

    # Sort newest first by date/created_at
    try:
        items.sort(
            key=lambda r: (r.get("date") or "", r.get("created_at") or ""),
            reverse=True,
        )
    except Exception:
        pass

    total_amount = sum(
        (r.get("amount") or 0) for r in items if isinstance(r.get("amount"), (int, float))
    )

    return render_template(
        "admin_donations.html",
        title="Donation Log",
        items=items,
        total_amount=total_amount,
        active="admin",
        error=error,
        success=success,
    )

@app.route("/donation")
def donation():
    """
    Public donation page used by the floating 💚 button.
    Shows a PayPal button if PAYPAL_LINK is configured.
    """
    return render_template(
        "donation.html",
        theme=SITE_THEME,
        join_url=JOIN_URL,
        active="donation",
        paypal_link=PAYPAL_LINK,
    )



# ---------- Feedback ----------
@app.route("/feedback", methods=["GET", "POST"])
def feedback_view():
    if request.method == "POST":
        flash("📝 Feedback submitted. Thank you!", "success")
        return redirect(url_for("feedback_view"))
    return render_template("feedback.html", theme=SITE_THEME, join_url=JOIN_URL, active="feedback")

# ---------- Study (Hub + series pages) ----------

STUDIES_META_FILE = DATA_DIR / "studies.json"


def load_study_meta() -> dict:
    """
    Optional metadata for study series from data/studies.json.

    Expected (recommended) shape:
      {
        "series1": {"title": "Series 1 – New Life", "tagline": "..."},
        "series2": {"title": "Series 2 – Growing in Grace", ...}
      }

    If the file is missing or in a different shape, we just return {} and
    fall back to filename-based titles, so nothing crashes.
    """
    if not STUDIES_META_FILE.exists():
        return {}
    try:
        with STUDIES_META_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # If someone made it a list instead of dict, ignore and use default titles
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@app.route("/study", endpoint="study")
@app.route("/studies", endpoint="study_index")
def study_index():
    """List all available study series (Series 1, Series 2, etc.)."""
    templates_root = Path(app.template_folder or "templates")
    study_dir = templates_root / "study"
    meta = load_study_meta()

    items: list[dict] = []
    if study_dir.exists():
        for p in sorted(study_dir.glob("series*.html")):
            key = p.stem  # e.g., "series1"
            # Base title from filename
            default_title = key.replace("series", "Series ").title()
            # If metadata exists for this key, use that title instead
            m = meta.get(key, {})
            title = m.get("title", default_title)
            tagline = m.get("tagline", "")
            items.append({"key": key, "title": title, "tagline": tagline})

    return render_template(
        "study/index.html",
        title="Study Series",
        series=items,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        active="study",
    )


@app.route("/study/<series_name>", endpoint="study_detail")
def study_detail(series_name: str):
    """
    Render a specific study series template (series1.html, series2.html, etc).
    Uses optional metadata from studies.json for a nicer page title.
    """
    if not series_name.startswith("series"):
        abort(404)

    rel = Path("study") / f"{series_name}.html"
    abs_path = Path(app.template_folder or "templates") / rel
    if not abs_path.exists():
        abort(404)

    meta = load_study_meta()
    default_title = series_name.replace("series", "Series ").title()
    page_title = meta.get(series_name, {}).get("title", default_title)

    return render_template(
        str(rel).replace("\\", "/"),
        title=page_title,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        active="study",
    )


# ---------- Auth (simple) ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if is_authed():
        return redirect(url_for("admin"))

    error = None

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        # Debug (optional; safe to remove later)
    
        if not ADMIN_PASSWORD:
            error = "Admin login is not configured on the server."
        elif verify_admin_credentials(email, password):
            session["authed"] = True
            flash("Welcome back, Admin.", "success")
            return redirect(url_for("admin"))
        else:
            error = "Incorrect email or password."

    return render_template("login.html", error=error, active="login")


@app.route("/logout")
def logout():
    session.pop("authed", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/admin")
@require_auth
def admin():
    return render_template(
        "admin.html",
        theme=SITE_THEME,
        join_url=JOIN_URL,
        active="admin",
        today_str=date.today().isoformat(),
    )

# ---------- Admin: Manage Theme Verses ----------
# ---------- Admin: Manage Theme Verses ----------

@app.route("/admin/verses", methods=["GET", "POST"])
@require_auth
def admin_verses():
    error: str | None = None
    success: str | None = None

    # List available images from the verses directory for the dropdown
    verses_img_dir = Path(app.static_folder) / "img" / "verses"
    try:
        image_files = sorted([
            f.name for f in verses_img_dir.iterdir()
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")
        ])
    except Exception:
        image_files = []

    # Load current verses
    verses = load_verses()

    action = request.form.get("action") if request.method == "POST" else None

    if request.method == "POST":
        # ---------- DELETE ----------
        if action == "delete":
            idx_str = (request.form.get("index") or "").strip()
            try:
                idx = int(idx_str)
            except ValueError:
                error = "Invalid verse index."
            else:
                if 0 <= idx < len(verses):
                    removed = verses.pop(idx)
                    try:
                        with VERSES_FILE.open("w", encoding="utf-8") as f:
                            json.dump(verses, f, ensure_ascii=False, indent=2)
                        ref = removed.get("ref", "")
                        success = f"Deleted verse #{idx} ({ref})."
                    except Exception as e:
                        error = f"Could not save verses.json: {e}"
                else:
                    error = "Verse index out of range."

        # ---------- UPDATE (EDIT) ----------
        elif action == "update":
            idx_str = (request.form.get("index") or "").strip()
            try:
                idx = int(idx_str)
            except ValueError:
                error = "Invalid verse index."
            else:
                if 0 <= idx < len(verses):
                    rec = verses[idx]
                    image = (request.form.get("image") or rec.get("image", "")).strip()
                    ref = (request.form.get("ref") or rec.get("ref", "")).strip()
                    title = (request.form.get("title") or rec.get("title", "")).strip()
                    note = (request.form.get("note") or rec.get("note", "")).strip()

                    rec["image"] = image
                    rec["ref"] = ref
                    rec["title"] = title
                    rec["note"] = note

                    try:
                        with VERSES_FILE.open("w", encoding="utf-8") as f:
                            json.dump(verses, f, ensure_ascii=False, indent=2)
                        success = f"Updated verse #{idx}."
                    except Exception as e:
                        error = f"Could not save verses.json: {e}"
                else:
                    error = "Verse index out of range."

        # ---------- ADD (DEFAULT) ----------
        else:
            image = (request.form.get("image") or "").strip()
            ref = (request.form.get("ref") or "").strip()
            title = (request.form.get("title") or "").strip()
            note = (request.form.get("note") or "").strip()

            if not image or not ref:
                error = "Image filename and Scripture reference are required."
            else:
                if not title:
                    title = ref

                record = {
                    "image": image,
                    "ref": ref,
                    "title": title,
                    "note": note,
                }
                verses.append(record)
                try:
                    with VERSES_FILE.open("w", encoding="utf-8") as f:
                        json.dump(verses, f, ensure_ascii=False, indent=2)
                    success = "Verse added successfully."
                except Exception as e:
                    error = f"Could not save verses.json: {e}"

    # Build preview cards
    cards = []
    for idx, v in enumerate(verses):
        image = v.get("image", "")
        src = _safe_static(f"img/verses/{image}") if image else None
        cards.append({
            "index": idx,
            "src": src,
            "image": image,
            "ref": v.get("ref", ""),
            "title": v.get("title", ""),
            "note": v.get("note", ""),
        })

    return render_template(
        "admin_verses.html",
        cards=cards,
        error=error,
        success=success,
        active="admin",
        theme=SITE_THEME,
        join_url=JOIN_URL,
        image_files=image_files,
    )



@app.route("/admin/requests")
def admin_requests():
    """Admin view: prayer requests"""
    file = DATA_DIR / "prayer_requests.json"
    items = []
    if file.exists():
        with file.open("r", encoding="utf-8") as f:
            try:
                items = json.load(f)
            except Exception:
                items = []
    return render_template(
        "admin_requests.html",
        items=items,
        theme=SITE_THEME,
        active="admin",
    )


@app.route("/admin/feedback")
def admin_feedback():
    """Admin view: feedback messages"""
    file = DATA_DIR / "feedback.json"
    items = []
    if file.exists():
        with file.open("r", encoding="utf-8") as f:
            try:
                items = json.load(f)
            except Exception:
                items = []
    return render_template(
        "admin_feedback.html",
        items=items,
        theme=SITE_THEME,
        active="admin",
    )


@app.route("/admin/volunteers")
def admin_volunteers():
    """Admin view: volunteer submissions"""
    file = DATA_DIR / "volunteers.json"
    rows = []
    if file.exists():
        with file.open("r", encoding="utf-8") as f:
            try:
                rows = json.load(f)
            except Exception:
                rows = []
    return render_template(
        "admin_volunteers.html",
        rows=rows,
        theme=SITE_THEME,
        active="admin",
    )


@app.route("/admin/whatsapp/send", methods=["POST"])
@require_auth
def admin_whatsapp_send():
    """Handle Admin WhatsApp send form and trigger the automation script."""

    # --- Live guard: block automation on Render ---
    if IS_PROD:
        # Live site: do NOT try to automate WhatsApp.
        return jsonify({
            "ok": False,
            "error": (
                "WhatsApp auto-send is only available on your local "
                "SoulStart console (desktop). On the live site, please "
                "copy–paste the message into WhatsApp."
            ),
        }), 400

    # ----- 1. Read form inputs (local desktop only) -----
    date_str = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")
    mode = request.form.get("mode") or "both"
    chat = request.form.get("chat") or "Silent SoulConnect"
    paste_delay_str = request.form.get("paste_delay") or "8"

    try:
        paste_delay = int(paste_delay_str)
    except ValueError:
        paste_delay = 8

    send_flag = "send" in request.form
    open_only = "open_only" in request.form
    dry_run = "dry_run" in request.form

    # ----- 2. Build payload & log it -----
    payload = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "date": date_str,
        "mode": mode,
        "chat": chat,
        "paste_delay": paste_delay,
        "send": send_flag,
        "open_only": open_only,
        "dry_run": dry_run,
    }

    LOG_DIR = Path("logs")
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / "admin_whatsapp_log.jsonl"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")

    # ----- 3. Decide which modes to run -----
    if mode == "both":
        modes_to_run = ["morning", "night"]
    elif mode in ("morning", "night", "verses"):
        modes_to_run = [mode]
    else:
        # Fallback – treat unknown as morning
        modes_to_run = ["morning"]

    script_path = Path(__file__).parent / "scripts" / "whatsapp_auto.py"

    # Base command (shared flags)
    base_cmd = [
        sys.executable,
        str(script_path),
        "--date", date_str,
        "--paste-delay", str(paste_delay),
    ]
    if open_only:
        base_cmd.append("--open-only")
    if dry_run:
        base_cmd.append("--dry-run")
    if send_flag:
        base_cmd.append("--send")

    results = []

    # ----- 4. Run once per mode (morning, night, verses) -----
    for m in modes_to_run:
        cmd = base_cmd + ["--mode", m]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
            ok = proc.returncode == 0
            stderr_tail = (proc.stderr or "")[-400:] if proc.stderr else ""
            results.append({
                "mode": m,
                "ok": ok,
                "returncode": proc.returncode,
                "stderr": stderr_tail,
            })
        except Exception as exc:
            results.append({
                "mode": m,
                "ok": False,
                "returncode": -1,
                "stderr": f"Exception: {exc}",
            })

    overall_ok = all(r["ok"] for r in results)

    resp = {
        "ok": overall_ok,
        "results": results,
        "meta": payload,
    }
    return jsonify(resp)


# =============================================================================
# Run (HTTP dev) + auto-open browser
# =============================================================================
def _open_browser():
    try:
        webbrowser.open(f"http://{HOST}:{PORT}/")
    except Exception:
        pass

if __name__ == "__main__":
    print("💜 SoulStart Devotion — Flask heartbeat ready (HTTP dev)…", APP_VERSION)
    if AUTO_OPEN:
        Timer(1.0, _open_browser).start()
    app.run(host=HOST, port=PORT, debug=True)

