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
    os.environ.get("DEVOTIONS_ROOT", str(BASE_DIR / "devotions_legacy"))
)

HERO_DAY_BG = "img/hero_day.jpg"
HERO_NIGHT_BG = "img/hero_night.jpg"  # change to your real night image name if different
HERO_NIGHT_BG = HERO_DAY_BG

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

from datetime import datetime, date
# … your other imports …

def normalize_date_str(s: str) -> str | None:
    """Try to parse many date formats and return ISO YYYY-MM-DD, or None."""
    s = (s or "").strip()
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y",
        "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y",
        "%b %d, %Y", "%B %d, %Y",
        "%d %b %Y", "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None

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
# =============================================================================
# Devotions + WhatsApp helpers (unified, hardened)
# Normalized OUTPUT schema for a single devotion:
#
# {
#   "date": "YYYY-MM-DD",
#   "mode": "morning" | "night",
#   "theme": "Daily theme",
#   "verse_ref": "Book 1:1",
#   "verse_text": "Scripture text",
#   "verse_meaning": "Silent soul meaning / 'This reminds me...'",
#   "body": "Main content (I DECLARE / I REFUSE / I WILL or reflection)",
#   "prayer": "Closing prayer",
#   "tags": [ ... ]
# }
# =============================================================================

# One fallback definition only
FALLBACK_DEVOTION = {
    "theme": "Silent Strength — God is Near",
    "verse_ref": "Psalm 46:1",
    "verse_text": "God is our refuge and strength, a very present help in trouble.",
    "verse_meaning": "When life feels uncertain, He steadies the soul.",
    "body": "Even without today’s devotion, His Word is enough. Stand firm.",
    "prayer": "Lord, anchor my heart today.",
}

# Core fields that must never be empty in the final entry
REQUIRED_FIELDS = ["theme", "verse_ref", "verse_text", "verse_meaning", "body", "prayer"]


def placeholder_devotion(date_str: str, mode: str = "morning") -> dict:
    """Safe devotion used when data is missing or broken."""
    return {
        "date": date_str,
        "mode": mode,
        "theme": FALLBACK_DEVOTION["theme"],
        "verse_ref": FALLBACK_DEVOTION["verse_ref"],
        "verse_text": FALLBACK_DEVOTION["verse_text"],
        "verse_meaning": FALLBACK_DEVOTION["verse_meaning"],
        "body": FALLBACK_DEVOTION["body"],
        "prayer": FALLBACK_DEVOTION["prayer"],
        "tags": ["placeholder"],
    }


def _devotions_file_for_year(year: int) -> Path:
    """Return path like data/devotions/devotions_2026.json."""
    return DEVOTIONS_DIR / f"devotions_{year}.json"


def load_devotions_for_year(year: int) -> dict[str, dict]:
    """
    Load all devotions for a given year and normalize to:
        { "YYYY-MM-DD": day_block }

    Supports:
    - 2025 migrated dict format  (already keyed by date)
    - 2026+ list-of-entries-with-date format
    """
    path = _devotions_file_for_year(year)
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # Corrupted JSON → treat as empty, caller will use placeholder
        return {}

    # Case 1: already dict keyed by date
    if isinstance(data, dict):
        return data

    # Case 2: list of entries, each with a "date"
    if isinstance(data, list):
        out: dict[str, dict] = {}
        for entry in data:
            if not isinstance(entry, dict):
                continue
            raw_date = entry.get("date") or entry.get("DATE")
            if not raw_date:
                continue
            norm = normalize_date_str(str(raw_date)) or str(raw_date)
            out[norm] = entry
        return out

    return {}


def load_devotion_for(target_date: date, slot: str = "morning") -> dict:
    """
    Return a single devotion for the given date/slot in the unified schema.

    Handles:
    - 2025-style blocks (one devotion per date with points/closing)
    - 2026+ day blocks with { theme, morning{...}, night{...} }

    This function **never** returns None – always a safe devotion dict.
    """
    slot = (slot or "morning").lower()
    if slot not in ("morning", "night"):
        slot = "morning"

    day_key = target_date.isoformat()
    all_for_year = load_devotions_for_year(target_date.year)

    # Year file missing or unreadable → placeholder
    if not all_for_year:
        return placeholder_devotion(day_key, slot)

    day_block = all_for_year.get(day_key)

    # Date missing or malformed → placeholder
    if not isinstance(day_block, dict):
        return placeholder_devotion(day_key, slot)

    # Does this day have separate morning/night dicts? (2026+)
    has_slots = isinstance(day_block.get("morning"), dict) or isinstance(day_block.get("night"), dict)
    if has_slots:
        theme = day_block.get("theme") or ""
        slot_block = day_block.get(slot) or {}
    else:
        # 2025 style – whole block is the devotion
        theme = (
            day_block.get("theme")
            or day_block.get("Theme")
            or day_block.get("title")
            or ""
        )
        slot_block = day_block

    # Mode block missing or not a dict → placeholder
    if not isinstance(slot_block, dict):
        return placeholder_devotion(day_key, slot)

    # ---- verse_ref / verse_text / verse_meaning ----
    verse_ref = (
        slot_block.get("verse_ref")
        or day_block.get("verse_ref")
        or slot_block.get("scripture")
        or day_block.get("scripture")
        or ""
    )

    verse_text = (
        slot_block.get("verse_text")
        or day_block.get("verse_text")
        or ""
    )

    verse_meaning = (
        slot_block.get("verse_meaning")
        or slot_block.get("silent_soul_meaning")
        or slot_block.get("heart_picture")
        or slot_block.get("encouragement_intro")
        or day_block.get("verse_meaning")
        or day_block.get("silent_soul_meaning")
        or day_block.get("heart_picture")
        or day_block.get("encouragement_intro")
        or ""
    )

    # ---- body (points + closing OR body text) ----
    body_lines: list[str] = []

    raw_body = slot_block.get("body") or day_block.get("body")
    if raw_body:
        body_lines.append(str(raw_body))

    for key in ("point1", "point2", "point3"):
        val = slot_block.get(key) or day_block.get(key)
        if val:
            body_lines.append(str(val))

    closing = slot_block.get("closing") or day_block.get("closing")
    if closing:
        body_lines.append(str(closing))

    body_text = ("\n".join([l for l in body_lines if l]).strip()) or verse_text or ""

    # ---- prayer ----
    prayer = (
        slot_block.get("prayer")
        or slot_block.get("morning_prayer")
        or slot_block.get("night_prayer")
        or day_block.get("prayer")
        or ""
    )

    tags = slot_block.get("tags") or day_block.get("tags") or []

    entry = {
        "date": day_key,
        "mode": slot,
        "theme": theme,
        "verse_ref": verse_ref,
        "verse_text": verse_text,
        "verse_meaning": verse_meaning,
        "body": body_text,
        "prayer": prayer,
        "tags": tags,
    }

    # Ensure required fields are never empty strings
    for field in REQUIRED_FIELDS:
        if not entry.get(field):
            entry[field] = FALLBACK_DEVOTION.get(field, "")

    return entry


def build_whatsapp_text(entry: dict | None, mode: str, today: date) -> str:
    """
    Build WhatsApp share text for a devotion entry.
    Safe even if some fields are missing (thanks to load_devotion_for).
    """
    if not entry:
        return ""

    mode = (mode or "morning").lower()
    date_str = today.strftime("%A, %B %d, %Y")

    heading = (
        f"🌅 SoulStart Sunrise – {date_str}"
        if mode == "morning"
        else f"🌙 SoulStart Sunset – {date_str}"
    )

    lines: list[str] = [heading, ""]

    theme = (entry.get("theme") or "").strip()
    verse_ref = (entry.get("verse_ref") or "").strip()
    verse_text = (entry.get("verse_text") or "").strip()

    if theme:
        lines.append(f"Theme: {theme}")
    if verse_ref:
        line = f"📖 Scripture: {verse_ref}"
        if verse_text:
            line += f' — "{verse_text}"'
        lines.append(line)

    verse_meaning = (entry.get("verse_meaning") or "").strip()
    if verse_meaning:
        lines.extend(["", verse_meaning])

    body = (entry.get("body") or "").strip()
    if body:
        lines.extend(["", body])

    prayer = (entry.get("prayer") or "").strip()
    if prayer:
        lines.extend(["", f"🙏 Prayer: {prayer}"])

    lines.extend(["", f"🔗 Share Us: {WHATSAPP_GROUP_LINK}"])

    return "\n".join([l for l in lines if l])

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


# ---------- Today ----------
@app.route("/today", endpoint="today")
def today_view():
    """Show today's morning or night devotion using the unified loader."""
    mode = (request.args.get("mode") or "morning").lower()
    if mode not in ("morning", "night"):
        mode = "morning"

    today = date.today()
    entry = load_devotion_for(today, mode)

    if not entry:
        entry = {}
        flash("Devotion is not available for this date yet.", "warn")

    whatsapp_share_text = build_whatsapp_text(entry, mode, today)

    hero_class = "hero-night" if mode == "night" else "hero-day"
    hero_bg = "img/hero_night.jpg" if mode == "night" else "img/hero_day.jpg"

    return render_template(
        "devotion.html",
        entry=entry,
        mode=mode,
        today=today,
        hero_class=hero_class,
        hero_bg=hero_bg,
        whatsapp_share_text=whatsapp_share_text,
        whatsapp_group_link=WHATSAPP_GROUP_LINK,
        theme=SITE_THEME,
        join_url=JOIN_URL,
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
            "note": "God is calling you to rise and shine, even when life feels dark.",
        },
        {
            "image": "Stillness.jpg",
            "ref": "Psalm 46:10 (NLV)",
            "title": "Stillness",
            "note": "A reminder to pause, breathe, and know that God is in control.",
        },
        {
            "image": "Restoration.jpg",
            "ref": "Joel 2:25 (NLV)",
            "title": "Restoration",
            "note": "God can restore the years and moments that feel wasted or broken.",
        },
        {
            "image": "Delight.jpg",
            "ref": "Isaiah 58:13–14",
            "title": "Delight",
            "note": "There is joy and freedom when we delight ourselves in the Lord.",
        },
        {
            "image": "Presence.jpg",
            "ref": "Exodus 33:14",
            "title": "Presence",
            "note": "His presence brings rest to a tired mind and a heavy heart.",
        },
        {
            "image": "Refuge.jpg",
            "ref": "Psalm 62:8",
            "title": "Refuge",
            "note": "You can pour out your heart; God is a safe place, not a harsh judge.",
        },
        {
            "image": "Overflow.jpg",
            "ref": "Psalm 23:5",
            "title": "Overflow",
            "note": "Even in hard seasons, God can cause your cup to overflow with grace.",
        },
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

        cards.append(
            {
                "id": idx,
                "src": src,
                "ref": v.get("ref", "Untitled"),
                "caption": v.get("title", ""),
                "note": v.get("note", ""),
                "alt": f"Theme verse — {v.get('ref', '')}",
            }
        )

    return render_template(
        "verses.html",
        today=today,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        cards=cards,
        page_bg_class="",
        active="verses",
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
        "alt": f"Theme verse — {v.get('ref', '')}",
    }

    return render_template(
        "verse_detail.html",
        card=card,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        active="verses",
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


# ---------- Donations (admin + public) ----------
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

    items = load_json_list(DONATIONS_FILE)

    try:
        items.sort(
            key=lambda r: (r.get("date") or "", r.get("created_at") or ""),
            reverse=True,
        )
    except Exception:
        pass

    total_amount = sum(
        (r.get("amount") or 0)
        for r in items
        if isinstance(r.get("amount"), (int, float))
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
    """Public donation page used by the floating 💚 button."""
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
