# app.py — SoulStart Devotion — v13 (Clean Single-App Core)
from __future__ import annotations

import os
import json
import secrets
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from functools import wraps
from urllib.parse import quote
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]

# =========================
# 0) ENV LOAD (safe)
# =========================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")   # local dev
load_dotenv()                    # fallback

ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
IS_PROD = ENV == "production"
IS_HTTPS = os.getenv("FORCE_HTTPS", "0").lower() in ("1", "true", "yes")

# =========================
# 1) LOGGING (safe, no duplicates)
# =========================
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("soulstart")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fh = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

logger.info("SoulStart starting…")

# =========================
# 2) FLASK IMPORTS
# =========================
from flask import (  # pyright: ignore[reportMissingImports]
    Flask, request, session, render_template, redirect,
    url_for, jsonify, send_from_directory, g, flash, abort,
)

from flask_login import (  # pyright: ignore[reportMissingImports]
    LoginManager, UserMixin, login_required, login_user,
    logout_user, current_user,
)

from flask_wtf import CSRFProtect  # pyright: ignore[reportMissingImports]
from flask_limiter import Limiter  # pyright: ignore[reportMissingImports]
from flask_limiter.util import get_remote_address  # pyright: ignore[reportMissingImports]

try:
    from flask_talisman import Talisman  # pyright: ignore[reportMissingImports]
except Exception:
    Talisman = None  # type: ignore

# =========================
# 3) CORE SETTINGS
# =========================
APP_VERSION = "v13"

SITE_THEME = os.getenv("SITE_THEME", "Faith to Rise, Grace to Rest")

JOIN_URL = os.getenv("JOIN_URL", "https://chat.whatsapp.com/CdkN2V0h8vCDg2AP4saYfG")
WHATSAPP_GROUP_LINK = os.getenv("WHATSAPP_GROUP_LINK", JOIN_URL)
SITE_JOIN_URL = WHATSAPP_GROUP_LINK

PAYPAL_LINK = os.getenv(
    "PAYPAL_LINK",
    "https://www.paypal.com/donate/?hosted_button_id=21H73722ER303860GND5CN2Y",
)

SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:5000")
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "127.0.0.1")
AUTO_OPEN = os.getenv("AUTO_OPEN", "0").lower() in ("1", "true", "yes")

# =========================
# 4) PATHS / STORAGE
# =========================
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "soulstart" / "static"

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DEVOTIONS_ROOT = Path(os.getenv("DEVOTIONS_ROOT", str(BASE_DIR / "devotions_legacy")))

HERO_DAY_BG = "img/hero_day.jpg"
HERO_NIGHT_BG = "img/hero_night.jpg"

VERSES_FILE = DATA_DIR / "verses.json"
DONATIONS_FILE = DATA_DIR / "donations.json"
REQUESTS_FILE = DATA_DIR / "requests.json"
VOLUNTEERS_FILE = DATA_DIR / "volunteers.json"
FEEDBACK_FILE = DATA_DIR / "feedback.json"

DEVOTIONS_DIR = DATA_DIR / "devotions"
DEVOTIONS_DIR.mkdir(exist_ok=True)

# =========================
# 5) FLASK APP (ONE TIME ONLY)
# =========================
app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
    template_folder=str(TEMPLATES_DIR),
)

app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config.update(
    SESSION_COOKIE_SECURE=IS_PROD or IS_HTTPS,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# =========================
# 6) EXTENSIONS (ONE TIME ONLY)
# =========================
csrf = CSRFProtect(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class AdminUser(UserMixin):
    def __init__(self, user_id: str = "admin"):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id: str):
    return AdminUser() if user_id == "admin" else None

# =========================
# 7) CSP / TALISMAN (ONE STRATEGY)
# =========================
if Talisman is not None:
    csp = {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "https:"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "script-src": ["'self'", "'unsafe-inline'"],
        "connect-src": ["'self'"],
        "font-src": ["'self'", "data:"],
        "media-src": ["'self'", "data:", "blob:"],
        "frame-ancestors": ["'self'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    }
    Talisman(
        app,
        content_security_policy=csp,
        force_https=IS_PROD or IS_HTTPS,
        frame_options="SAMEORIGIN",
        referrer_policy="strict-origin-when-cross-origin",
    )

@app.after_request
def add_no_cache(resp):
    if not IS_PROD:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
    return resp

@app.get("/health")
def health():
    return "ok", 200

# =========================
# 8) ADMIN CREDENTIALS
# =========================
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL", "sscministry@outlook.com") or "").strip().lower()
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD", "") or "").strip()
ADMIN_PASS = ADMIN_PASSWORD  # backwards compat

def verify_admin_credentials(email: str, password: str) -> bool:
    if not ADMIN_PASSWORD:
        return False
    return email.strip().lower() == ADMIN_EMAIL and password.strip() == ADMIN_PASSWORD

# =========================
# 9) HELPERS
# =========================
def is_authed() -> bool:
    return bool(session.get("authed"))

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_authed():
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def common_page_ctx(active: str):
    return dict(
        today=date.today(),
        theme=SITE_THEME,
        join_url=SITE_JOIN_URL,
        active=active,
        page_bg_class="bg-image",
        page_bg_url=url_for("static", filename=HERO_DAY_BG),
    )

STUDY_SERIES: list[dict] = []
VERSE_CARDS: list[dict] = []

# =========================
# 10) SOCIAL LINKS (Phase 3)
# =========================
FACEBOOK_URL = os.getenv("FACEBOOK_URL", "https://www.facebook.com/profile.php?id=61585837505269")
LINKEDIN_URL = os.getenv("LINKEDIN_URL", "https://www.linkedin.com/company/silentsoulconnect")

SOCIAL_LINKS = {
    "whatsapp": SITE_JOIN_URL,
    "facebook": FACEBOOK_URL,
    "linkedin": LINKEDIN_URL,
}

@app.context_processor
def inject_globals():
    return {
        "SOCIAL_LINKS": SOCIAL_LINKS,
        "SITE_JOIN_URL": SITE_JOIN_URL,
        "SITE_THEME": SITE_THEME,
        "APP_VERSION": APP_VERSION,
        "PAYPAL_LINK": PAYPAL_LINK,
    }

# =========================
# 11) DATE PARSE UTIL
# =========================
def normalize_date_str(s: str) -> str | None:
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

def load_json_list(path: Path) -> list:
    """Load a JSON list from file; return [] on missing/invalid."""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        # If someone accidentally stored a dict, wrap it
        return [data]
    except Exception as e:
        logger.warning("Failed to load JSON list %s (%s)", path, e)
        return []

def append_json_list(path: Path, record: dict) -> None:
    """Append a record to a JSON list file (never raises)."""
    items = load_json_list(path)
    items.append(record)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Failed to append JSON list %s (%s)", path, e)


# =============================================================================
# Devotions helpers (year-based JSON, unified schema)
# Normalized OUTPUT for a single devotion:
#
# {
#   "date": "YYYY-MM-DD",
#   "mode": "morning" | "night",
#   "theme": "Daily theme",
#   "verse_ref": "Book 1:1",
#   "verse_text": "Scripture text",
#   "verse_meaning": "This reminds me…",
#   "body": "Main content (I DECLARE / I REFUSE / I WILL or reflection)",
#   "prayer": "Closing prayer",
#   "tags": [ ... ]
# }
# =============================================================================

def _devotions_file_for_year(year: int) -> Path:
    """Return path like data/devotions/devotions_2026.json."""
    return DEVOTIONS_DIR / f"devotions_{year}.json"

def load_devotions_for_year(year: int) -> dict[str, dict]:
    """
    Load all devotions for a given year and normalize to:
      { "YYYY-MM-DD": day_block }

    Supports:
    - dict keyed by date: { "2026-01-01": {...} }
    - list entries with "date": [ {"date":"2026-01-01", ...}, ... ]
    """
    path = _devotions_file_for_year(year)
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.exception("[DEVOTIONS] Failed to read %s (%s)", path, e)
        return {}

    if isinstance(data, dict):
        return data

    if isinstance(data, list):
        out: dict[str, dict] = {}
        for entry in data:
            if not isinstance(entry, dict):
                continue
            raw_date = entry.get("date") or entry.get("DATE")
            if not raw_date:
                continue
            norm = normalize_date_str(str(raw_date)) or str(raw_date).strip()
            out[norm] = entry
        return out

    return {}

def placeholder_devotion(date_str: str = "", mode: str = "morning") -> dict:
    return {
        "date": date_str,
        "mode": mode,
        "theme": "Coming Soon",
        "verse_ref": "",
        "verse_text": "",
        "verse_meaning": "",
        "body": "Devotion is being prepared. Please check back soon.",
        "prayer": "",
        "tags": [],
    }

def load_devotion_for(target_date: date, slot: str = "morning") -> dict:
    """
    Return ONE devotion in unified schema.
    Always returns something (real devotion or placeholder).

    Handles:
    - 2026+ day blocks:
        {
          "theme":"...",
          "morning": {...},
          "night": {...}
        }
    - 2025 style (single block per day):
        { "theme": "...", "point1":..., "closing":... }
    """
    slot = (slot or "morning").lower()
    if slot not in ("morning", "night"):
        slot = "morning"

    day_key = target_date.isoformat()
    all_for_year = load_devotions_for_year(target_date.year)
    if not all_for_year:
        return placeholder_devotion(day_key, slot)

    day_block = all_for_year.get(day_key)
    if not isinstance(day_block, dict):
        return placeholder_devotion(day_key, slot)

    # 2026+ slot mode?
    has_slots = isinstance(day_block.get("morning"), dict) or isinstance(day_block.get("night"), dict)
    if has_slots:
        theme = str(day_block.get("theme") or "").strip()
        slot_block = day_block.get(slot) or {}
    else:
        theme = str(
            day_block.get("theme")
            or day_block.get("Theme")
            or day_block.get("title")
            or ""
        ).strip()
        slot_block = day_block

    if not isinstance(slot_block, dict) or not slot_block:
        return placeholder_devotion(day_key, slot)

    # ---- verse_ref / verse_text / verse_meaning ----
    verse_ref = str(
        slot_block.get("verse_ref")
        or day_block.get("verse_ref")
        or slot_block.get("scripture")
        or day_block.get("scripture")
        or ""
    ).strip()

    verse_text = str(
        slot_block.get("verse_text")
        or day_block.get("verse_text")
        or ""
    ).strip()

    verse_meaning = str(
        slot_block.get("verse_meaning")
        or slot_block.get("silent_soul_meaning")
        or slot_block.get("heart_picture")
        or slot_block.get("encouragement_intro")
        or day_block.get("verse_meaning")
        or day_block.get("silent_soul_meaning")
        or day_block.get("heart_picture")
        or day_block.get("encouragement_intro")
        or ""
    ).strip()

    # ---- body ----
    lines: list[str] = []

    raw_body = slot_block.get("body") or day_block.get("body")
    if raw_body:
        lines.append(str(raw_body).strip())

    for key in ("point1", "point2", "point3"):
        val = slot_block.get(key) or day_block.get(key)
        if val:
            lines.append(str(val).strip())

    closing = slot_block.get("closing") or day_block.get("closing")
    if closing:
        lines.append(str(closing).strip())

    body_text = "\n".join([l for l in lines if l]).strip()
    if not body_text:
        body_text = verse_text or ""

    # ---- prayer ----
    prayer = str(
        slot_block.get("prayer")
        or slot_block.get("morning_prayer")
        or slot_block.get("night_prayer")
        or day_block.get("prayer")
        or ""
    ).strip()

    tags = slot_block.get("tags") or day_block.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    return {
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

def build_whatsapp_text(entry: dict | None, mode: str, today: date) -> str:
    """WhatsApp share text for a devotion entry (or empty string)."""
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

    # Footer link (use your single source of truth)
    lines.extend(["", f"🔗 Join us: {SITE_JOIN_URL}"])

    return "\n".join([l for l in lines if l]).strip()

# =============================================================================
# Routes
# =============================================================================

# ---------- Utilities ----------
def _safe_static(filename: str) -> str | None:
    """Return static URL if file exists; else None."""
    path = Path(app.static_folder) / filename
    return url_for("static", filename=filename) if path.exists() else None


# ---------- Verses Data ----------
def load_verses() -> list[dict]:
    """
    Load verse cards from data/verses.json if present.
    Fallback to built-in defaults if missing or invalid.
    """
    fallback = [
        {"image": "Firelight.jpg", "ref": "Isaiah 60:1 (NLV)", "title": "Firelight",
         "note": "God is calling you to rise and shine, even when life feels dark."},
        {"image": "Stillness.jpg", "ref": "Psalm 46:10 (NLV)", "title": "Stillness",
         "note": "A reminder to pause, breathe, and know that God is in control."},
        {"image": "Restoration.jpg", "ref": "Joel 2:25 (NLV)", "title": "Restoration",
         "note": "God can restore the years and moments that feel wasted or broken."},
        {"image": "Delight.jpg", "ref": "Isaiah 58:13–14", "title": "Delight",
         "note": "There is joy and freedom when we delight ourselves in the Lord."},
        {"image": "Presence.jpg", "ref": "Exodus 33:14", "title": "Presence",
         "note": "His presence brings rest to a tired mind and a heavy heart."},
        {"image": "Refuge.jpg", "ref": "Psalm 62:8", "title": "Refuge",
         "note": "You can pour out your heart; God is a safe place, not a harsh judge."},
        {"image": "Overflow.jpg", "ref": "Psalm 23:5", "title": "Overflow",
         "note": "Even in hard seasons, God can cause your cup to overflow with grace."},
    ]

    if not VERSES_FILE.exists():
        return fallback

    try:
        with VERSES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else fallback
    except Exception as e:
        logger.warning("Failed to load verses (%s)", e)
        return fallback


# ---------- Home ----------
@app.route("/", endpoint="home")
def home():
    ctx = common_page_ctx(active="home")
    return render_template("home.html", **ctx)


# ---------- Devotion / Study Hub ----------
@app.route("/devotion-study", endpoint="devotion_study")
def devotion_study():
    ctx = common_page_ctx(active="devotion_study")
    return render_template("devotion_study.html", **ctx)


# ---------- Today ----------
DEFAULT_MODE = "morning"

@app.route("/today", endpoint="today")
@limiter.limit("20/minute")
def today_view():
    """Show devotion for today (or requested date) + WhatsApp share preview."""
    mode = (request.args.get("mode") or DEFAULT_MODE).lower().strip()
    if mode not in ("morning", "night"):
        mode = DEFAULT_MODE

    raw_date = (request.args.get("date") or "").strip()
    if raw_date:
        norm = normalize_date_str(raw_date)
        if norm:
            try:
                target_date = datetime.strptime(norm, "%Y-%m-%d").date()
            except Exception:
                target_date = date.today()
        else:
            target_date = date.today()
    else:
        target_date = date.today()

    entry = load_devotion_for(target_date, mode)
    preview_text = build_whatsapp_text(entry, mode, target_date)

    hero_bg = HERO_NIGHT_BG if mode == "night" else HERO_DAY_BG
    hero_class = "hero night-tone" if mode == "night" else "hero"

    ctx = common_page_ctx(active="today")
    ctx.update({
        "hero_bg": hero_bg,
        "hero_class": hero_class,
        "today": target_date,
        "entry": entry,
        "mode": mode,
        "whatsapp_preview": preview_text,
    })

    # Yesterday link
    yday_date = target_date - timedelta(days=1)
    ctx["yday_url"] = url_for("today", date=yday_date.isoformat(), mode=mode)
    ctx["yday_label"] = "← Yesterday’s devotion"

    return render_template("devotion.html", **ctx)


# ---------- Verses ----------
@app.route("/verses", endpoint="verses")
def verses():
    verses_data = load_verses()
    cards = []

    for idx, v in enumerate(verses_data):
        image = (v.get("image") or "").strip()
        src = _safe_static(f"img/verses/{image}") if image else None
        cards.append({
            "id": idx,
            "src": src,
            "ref": v.get("ref", "Untitled"),
            "title": v.get("title", ""),
            "note": v.get("note", ""),
            "alt": f"Theme verse — {v.get('ref', '')}",
        })

    ctx = common_page_ctx(active="verses")
    return render_template("verses.html", cards=cards, **ctx)


@app.route("/verses/<int:card_id>", endpoint="verse_detail")
def verse_detail(card_id: int):
    verses_data = load_verses()
    if card_id < 0 or card_id >= len(verses_data):
        abort(404)

    v = verses_data[card_id]
    image = (v.get("image") or "").strip()
    src = _safe_static(f"img/verses/{image}") if image else None

    card = {
        "id": card_id,
        "src": src,
        "ref": v.get("ref", "Untitled"),
        "title": v.get("title", ""),
        "note": v.get("note", ""),
        "alt": f"Theme verse — {v.get('ref', '')}",
    }

    ctx = common_page_ctx(active="verses")
    return render_template("verse_detail.html", card=card, **ctx)


# ---------- Prayer ----------
PRAYER_REQUESTS_FILE = DATA_DIR / "prayer_requests.json"

@app.route("/prayer", methods=["GET", "POST"], endpoint="prayer")
def prayer():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        request_text = (request.form.get("request") or "").strip()
        if request_text:
            record = {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "name": name,
                "request": request_text,
            }
            append_json_list(PRAYER_REQUESTS_FILE, record)

        flash("🙏 Your prayer request was received.", "success")
        return redirect(url_for("prayer"))

    ctx = common_page_ctx(active="prayer")
    return render_template("prayer.html", **ctx)


# ---------- About ----------
@app.route("/about", endpoint="about")
def about():
    ctx = common_page_ctx(active="about")
    return render_template("about.html", **ctx)


# ---------- Study ----------
STUDIES_META_FILE = DATA_DIR / "studies.json"

def load_study_meta() -> dict:
    if not STUDIES_META_FILE.exists():
        return {}
    try:
        with STUDIES_META_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

@app.route("/studies", endpoint="study_index")
def study_index():
    templates_root = Path(app.template_folder or "templates")
    study_dir = templates_root / "study"
    meta = load_study_meta()

    items: list[dict] = []
    if study_dir.exists():
        for p in sorted(study_dir.glob("series*.html")):
            key = p.stem
            default_title = key.replace("series", "Series ").title()
            m = meta.get(key, {})
            items.append({
                "key": key,
                "title": m.get("title", default_title),
                "tagline": m.get("tagline", ""),
            })

    ctx = common_page_ctx(active="study")
    ctx["hero_class"] = "hero"
    ctx["hero_bg"] = HERO_DAY_BG
    return render_template("study/index.html", series=items, **ctx)

@app.route("/studies/<series_name>", endpoint="study_detail")
def study_detail(series_name: str):
    if not series_name.startswith("series"):
        abort(404)

    rel = Path("study") / f"{series_name}.html"
    abs_path = Path(app.template_folder or "templates") / rel
    if not abs_path.exists():
        abort(404)

    meta = load_study_meta()
    default_title = series_name.replace("series", "Series ").title()
    page_title = meta.get(series_name, {}).get("title", default_title)

    ctx = common_page_ctx(active="study")
    return render_template(str(rel).replace("\\", "/"), title=page_title, **ctx)


# ---------- Donation ----------
@app.route("/donation", endpoint="donation")
def donation():
    ctx = common_page_ctx(active="donation")
    ctx["paypal_link"] = PAYPAL_LINK
    return render_template("donation.html", **ctx)


# ---------- Volunteer ----------
@app.route("/volunteer", methods=["GET", "POST"], endpoint="volunteer")
def volunteer():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        skills = (request.form.get("skills") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        if name or skills or contact:
            record = {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "name": name,
                "skills": skills,
                "contact": contact,
            }
            append_json_list(VOLUNTEERS_FILE, record)
        flash("💚 Thank you for offering your skills!", "success")
        return redirect(url_for("volunteer"))

    ctx = common_page_ctx(active="volunteer")
    return render_template("volunteer.html", **ctx)


# ---------- Feedback ----------
@app.route("/feedback", methods=["GET", "POST"], endpoint="feedback_view")
def feedback_view():
    if request.method == "POST":
        message = (request.form.get("message") or "").strip()
        if message:
            record = {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "message": message,
            }
            append_json_list(FEEDBACK_FILE, record)

        flash("📝 Feedback submitted. Thank you!", "success")
        return redirect(url_for("feedback_view"))

    ctx = common_page_ctx(active="feedback")
    return render_template("feedback.html", **ctx)


# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"], endpoint="login")
def login():
    if is_authed():
        return redirect(url_for("admin"))

    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        if not ADMIN_PASSWORD:
            error = "Admin login is not configured on the server."
        elif verify_admin_credentials(email, password):
            session["authed"] = True
            login_user(AdminUser("admin"))
            flash("Welcome back, Admin.", "success")
            return redirect(url_for("admin"))
        else:
            error = "Incorrect email or password."

    ctx = common_page_ctx(active="login")
    return render_template("login.html", error=error, **ctx)

@app.route("/logout", endpoint="logout")
def logout():
    session.clear()
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# =============================================================================
# Admin Routes
# =============================================================================

@app.route("/admin", endpoint="admin")
@require_auth
def admin_dashboard():
    ctx = common_page_ctx(active="admin")
    ctx["today_str"] = date.today().isoformat()
    return render_template("admin/admin.html", **ctx)


@app.route("/admin/verses", methods=["GET", "POST"], endpoint="admin_verses")
@require_auth
def admin_verses_view():
    error: str | None = None
    success: str | None = None

    verses_img_dir = Path(app.static_folder) / "img" / "verses"
    try:
        image_files = sorted([
            f.name for f in verses_img_dir.iterdir()
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")
        ])
    except Exception:
        image_files = []

    verses = load_verses()
    action = (request.form.get("action") or "").strip().lower() if request.method == "POST" else ""

    if request.method == "POST":
        if action == "delete":
            idx_str = (request.form.get("index") or "").strip()
            try:
                idx = int(idx_str)
                if 0 <= idx < len(verses):
                    removed = verses.pop(idx)
                    with VERSES_FILE.open("w", encoding="utf-8") as f:
                        json.dump(verses, f, ensure_ascii=False, indent=2)
                    success = f"Deleted verse #{idx} ({removed.get('ref','')})."
                else:
                    error = "Verse index out of range."
            except Exception as e:
                error = f"Could not delete verse: {e}"

        elif action == "update":
            idx_str = (request.form.get("index") or "").strip()
            try:
                idx = int(idx_str)
                if 0 <= idx < len(verses):
                    rec = verses[idx]
                    rec["image"] = (request.form.get("image") or rec.get("image", "")).strip()
                    rec["ref"]   = (request.form.get("ref")   or rec.get("ref", "")).strip()
                    rec["title"] = (request.form.get("title") or rec.get("title", "")).strip()
                    rec["note"]  = (request.form.get("note")  or rec.get("note", "")).strip()

                    with VERSES_FILE.open("w", encoding="utf-8") as f:
                        json.dump(verses, f, ensure_ascii=False, indent=2)
                    success = f"Updated verse #{idx}."
                else:
                    error = "Verse index out of range."
            except Exception as e:
                error = f"Could not update verse: {e}"

        else:  # add
            image = (request.form.get("image") or "").strip()
            ref   = (request.form.get("ref") or "").strip()
            title = (request.form.get("title") or "").strip() or ref
            note  = (request.form.get("note") or "").strip()

            if not image or not ref:
                error = "Image filename and Scripture reference are required."
            else:
                verses.append({"image": image, "ref": ref, "title": title, "note": note})
                try:
                    VERSES_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with VERSES_FILE.open("w", encoding="utf-8") as f:
                        json.dump(verses, f, ensure_ascii=False, indent=2)
                    success = "Verse added successfully."
                except Exception as e:
                    error = f"Could not save verses.json: {e}"

    cards = []
    for idx, v in enumerate(verses):
        image = (v.get("image") or "").strip()
        src = _safe_static(f"img/verses/{image}") if image else None
        cards.append({
            "index": idx,
            "src": src,
            "image": image,
            "ref": v.get("ref", ""),
            "title": v.get("title", ""),
            "note": v.get("note", ""),
        })

    ctx = common_page_ctx(active="admin")
    return render_template(
        "admin/admin_verses.html",
        cards=cards,
        error=error,
        success=success,
        image_files=image_files,
        **ctx,
    )


@app.route("/admin/requests", endpoint="admin_requests")
@require_auth
def admin_requests_view():
    items = load_json_list(PRAYER_REQUESTS_FILE)
    ctx = common_page_ctx(active="admin")
    return render_template("admin/admin_requests.html", items=items, **ctx)

@app.route("/admin/feedback", endpoint="admin_feedback")
@require_auth
def admin_feedback_view():
    items = load_json_list(FEEDBACK_FILE)
    ctx = common_page_ctx(active="admin")
    return render_template("admin/admin_feedback.html", items=items, **ctx)

@app.route("/admin/volunteers", endpoint="admin_volunteers")
@require_auth
def admin_volunteers_view():
    rows = load_json_list(VOLUNTEERS_FILE)
    ctx = common_page_ctx(active="admin")
    return render_template("admin/admin_volunteers.html", rows=rows, **ctx)


@app.route("/admin/donations", methods=["GET", "POST"], endpoint="admin_donations")
@require_auth
def admin_donations_view():
    error = None
    success = None

    if request.method == "POST":
        donor_name = (request.form.get("donor_name") or "").strip()
        amount_raw = (request.form.get("amount") or "").strip()
        currency = (request.form.get("currency") or "USD").strip().upper()
        note = (request.form.get("note") or "").strip()
        date_str = (request.form.get("date") or "").strip() or date.today().isoformat()

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
        items.sort(key=lambda r: (r.get("date") or "", r.get("created_at") or ""), reverse=True)
    except Exception:
        pass

    total_amount = sum(
        (r.get("amount") or 0)
        for r in items
        if isinstance(r.get("amount"), (int, float))
    )

    ctx = common_page_ctx(active="admin")
    return render_template(
        "admin/admin_donations.html",
        items=items,
        total_amount=total_amount,
        error=error,
        success=success,
        **ctx,
    )


@app.route("/admin/whatsapp", methods=["GET"], endpoint="admin_whatsapp")
@require_auth
def admin_whatsapp_page():
    ctx = common_page_ctx(active="admin")
    ctx.update({
        "today": date.today(),
        "selected_date": date.today().isoformat(),
        "selected_mode": "morning",
        "result": {},
    })
    return render_template("admin/admin_whatsapp.html", **ctx)


@app.route("/admin/whatsapp/send", methods=["POST"], endpoint="admin_whatsapp_send")
@require_auth
def admin_whatsapp_send():
    today_ = date.today()

    raw_mode = (request.form.get("mode") or "morning").lower().strip()
    if raw_mode in ("morning", "m", "am"):
        mode = "morning"
    elif raw_mode in ("night", "n", "pm"):
        mode = "night"
    else:
        mode = "both"

    raw_date = (request.form.get("date") or today_.isoformat()).strip()
    try:
        target_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        target_date = today_
        raw_date = today_.isoformat()

    def make_share_urls(message: str) -> dict:
        enc = quote(message)
        return {
            "share_web": f"https://web.whatsapp.com/send?text={enc}",
            "share_api": f"https://api.whatsapp.com/send?text={enc}",
            "share_wa":  f"https://wa.me/?text={enc}",
        }

    if mode in ("morning", "night"):
        entry = load_devotion_for(target_date, mode) or placeholder_devotion(raw_date, mode)
        text = build_whatsapp_text(entry, mode, target_date)
        urls = make_share_urls(text)
        return jsonify({
            "ok": True,
            "mode": mode,
            "date": raw_date,
            "text": text,
            "share_web": urls["share_web"],
            "share_api": urls["share_api"],
            "share_wa":  urls["share_wa"],
            "join_url": SITE_JOIN_URL,
        })

    entry_m = load_devotion_for(target_date, "morning") or placeholder_devotion(raw_date, "morning")
    entry_n = load_devotion_for(target_date, "night") or placeholder_devotion(raw_date, "night")

    text_m = build_whatsapp_text(entry_m, "morning", target_date)
    text_n = build_whatsapp_text(entry_n, "night", target_date)

    urls_m = make_share_urls(text_m)
    urls_n = make_share_urls(text_n)

    return jsonify({
        "ok": True,
        "mode": "both",
        "date": raw_date,
        "text_morning": text_m,
        "text_night": text_n,
        "share_web_morning": urls_m["share_web"],
        "share_api_morning": urls_m["share_api"],
        "share_wa_morning":  urls_m["share_wa"],
        "share_web_night": urls_n["share_web"],
        "share_api_night": urls_n["share_api"],
        "share_wa_night":  urls_n["share_wa"],
        "join_url": SITE_JOIN_URL,
    })


# =============================================================================
# Run (HTTP dev) + auto-open browser
# =============================================================================
def _open_browser():
    try:
        webbrowser.open(f"http://{HOST}:{PORT}/")
    except Exception:
        pass

if __name__ == "__main__":
    logger.info(f"💜 SoulStart Devotion — Flask heartbeat ready (HTTP dev)… {APP_VERSION}")
    if AUTO_OPEN:
        Timer(1.0, _open_browser).start()
    app.run(host=HOST, port=PORT, debug=True)
