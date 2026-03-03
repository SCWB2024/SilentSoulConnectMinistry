# app.py — SoulStart Devotion — v13 (Clean Single-App Core)
# =========================
# FLASK IMPORTS
# =========================
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import smtplib
import random
from calendar import month_name
from datetime import date, datetime, timedelta
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import quote
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

from werkzeug.middleware.proxy_fix import ProxyFix

from flask import (
    Flask,
    abort,
    ctx,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_user,
    logout_user,
)

from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

try:
    from flask_talisman import Talisman
except Exception:
    Talisman = None

# =========================
# 1) ENV LOAD (safe)
# =========================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")   # local dev
load_dotenv()                    # fallback

ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
IS_PROD = ENV == "production"
IS_HTTPS = os.getenv("FORCE_HTTPS", "0").lower() in ("1", "true", "yes")

# =========================
# 2) LOGGING (safe, no duplicates)
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

if not IS_PROD:
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

# =========================
# 3) CORE SETTINGS
# =========================
APP_VERSION = "v13"

SITE_THEME = os.getenv("SITE_THEME", "Faith to Rise, Grace to Rest")

JOIN_URL = os.getenv("JOIN_URL", "https://chat.whatsapp.com/CdkN2V0h8vCDg2AP4saYfG")
WHATSAPP_GROUP_LINK = os.getenv("WHATSAPP_GROUP_LINK", JOIN_URL)
SITE_JOIN_URL = WHATSAPP_GROUP_LINK

PAYPAL_LINK = os.getenv("PAYPAL_LINK", "")

SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:5000")
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "0.0.0.0" if IS_PROD else "127.0.0.1")
AUTO_OPEN = (not IS_PROD) and os.getenv("AUTO_OPEN", "0").lower() in ("1","true","yes")

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
PRAYER_REQUESTS_FILE = DATA_DIR / "prayer_requests.json"
VOLUNTEERS_FILE = DATA_DIR / "volunteers.json"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
DEVOTIONS_DIR = DATA_DIR / "devotions"
DEVOTIONS_DIR.mkdir(exist_ok=True)
BLOG_DATA_PATH = DATA_DIR / "blog_posts.json"

logger.info("Prayer requests file: %s", PRAYER_REQUESTS_FILE.resolve())

if not IS_PROD:
    if not TEMPLATES_DIR.exists():
        logger.warning("Templates folder not found: %s", TEMPLATES_DIR)
    if not STATIC_DIR.exists():
        logger.warning("Static folder not found: %s", STATIC_DIR)

# =========================
# 5) FLASK APP (ONE TIME ONLY)
# =========================
app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
    template_folder=str(TEMPLATES_DIR),
)

app.secret_key = os.getenv("SECRET_KEY") or "dev-only-change-me"
if IS_PROD and app.secret_key == "dev-only-change-me":
    raise RuntimeError("SECRET_KEY must be set in production.")

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config.update(
    SESSION_COOKIE_SECURE=IS_PROD or IS_HTTPS,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# =========================
# 6) EXTENSIONS (ONE TIME ONLY)
# =========================
csrf = CSRFProtect(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["5000 per day", "500 per hour"],
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
        force_https=IS_PROD,
        frame_options="SAMEORIGIN",
        referrer_policy="strict-origin-when-cross-origin",
    )

# =========================
# 8) ADMIN CREDENTIALS
# =========================
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL", "sscministry@outlook.com") or "").strip().lower()
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD", "") or "").strip()
ADMIN_PASS = ADMIN_PASSWORD  # backwards compat

def verify_admin_credentials(email: str, password: str) -> bool:
    if not ADMIN_PASSWORD:
        return False
    return (
        email.strip().lower() == ADMIN_EMAIL
        and secrets.compare_digest(password.strip(), ADMIN_PASSWORD)
    )

# =========================
# 9) HELPERS
# =========================
def is_authed() -> bool:
    return bool(session.get("authed"))

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_authed():
            return redirect(url_for("login", next=request.path))
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

def read_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("Could not read %s: %s", path, e)
        return []
    

def append_json_list(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = read_json_list(path)
    data.append(item)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def pick_random_request(topic: str | None = None) -> dict | None:
    items = read_json_list(PRAYER_REQUESTS_FILE)
    if not items:
        return None

    topic = (topic or "").strip()
    if topic:
        filtered = [r for r in items if (r.get("topic") or "").strip() == topic]
        if filtered:
            return random.choice(filtered)

    return random.choice(items)


# =========================
# 10) SOCIAL LINKS
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
        "FACEBOOK_URL": FACEBOOK_URL,
        "LINKEDIN_URL": LINKEDIN_URL,
        "JOIN_URL": JOIN_URL,
        "SITE_URL": request.url_root.rstrip("/"),
        "now": datetime.now(),
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
# 12) Donation log helpers
# ---------------------------------------------------------------------------
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
#   "prayer": "Closing prayer", "In Jesus’ name, Amen."
#   "tags": [ ... ]
# }
# =============================================================================
AMEN_LINE = os.getenv("PRAYER_CLOSING", "In Jesus’ name, Amen.")

def ensure_amen(text: str) -> str:
    t = (text or "").rstrip()
    if not t:
        return t
    # avoid double-adding if already present
    low = t.lower()
    if "in jesus" in low and "amen" in low:
        return t
    return t + "\n\n" + AMEN_LINE

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
        "icon": "🌅" if mode == "morning" else "🌙",
        "verse_ref": "",
        "verse_text": "",
        "verse_meaning": "💡",
        "body": "Devotion is being prepared. Please check back soon.",
        "prayer": "🙏 In Jesus’ name, Amen.",
        "tags": ["placeholder"],
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
    prayer = ensure_amen(str(
        slot_block.get("prayer")
        or slot_block.get("morning_prayer")
        or slot_block.get("night_prayer")
        or day_block.get("prayer")
        or ""
    ).strip())
    

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

    prayer_raw = str(entry.get("prayer") or ""  ).strip()
    prayer = ensure_amen(prayer_raw or "Lord, cover us today with Your peace.")

def build_whatsapp_text(entry: dict | None, mode: str, day: date) -> str:
    """WhatsApp share text for a devotion entry (or empty string)."""
    if not entry:
        return ""

    mode = (mode or "morning").lower().strip()
    date_str = day.strftime("%A, %B %d, %Y")

    # Icon: from entry.icon OR by mode
    icon = (entry.get("icon") or "").strip()
    if not icon:
        icon = "🌅" if mode == "morning" else "🌙"

    heading = f"{icon} SoulStart {'Sunrise' if mode=='morning' else 'Sunset'} – {date_str}"

    lines: list[str] = [heading, ""]

    theme = (entry.get("theme") or "").strip()
    verse_ref = (entry.get("verse_ref") or "").strip()
    verse_text = (entry.get("verse_text") or "").strip()

    if theme:
        lines.append(f"Theme: {theme}")

    if verse_ref:
        if verse_text:
            lines.append(f"📖 Scripture: {verse_ref} — “{verse_text}”")
        else:
            lines.append(f"📖 Scripture: {verse_ref}")

    # Meaning: try multiple keys (since your JSON varies by year/version)
    meaning = (
        (entry.get("verse_meaning") or "").strip()
        or (entry.get("silent_soul_meaning") or "").strip()
        or (entry.get("heart_picture") or "").strip()
        or (entry.get("encouragement_intro") or "").strip()
    )

    if meaning:
        lines.extend(["", f"💡 Meaning: {meaning}"])

    body = (entry.get("body") or "").strip()
    if body:
        lines.extend(["", body])

    prayer = (entry.get("prayer") or "").strip()
    if prayer:
        prayer = ensure_amen(prayer)
        lines.extend(["", f"🙏 Prayer: {prayer}"])
    else:
        # still ensure we end cleanly
        lines.extend(["", AMEN_LINE])

    # Footer link
    lines.extend(["", f"🔗 Join us: {SITE_JOIN_URL}"])

    return "\n".join([l for l in lines if l]).strip()

# =========================
# JSON STORAGE HELPERS (single source of truth)
# =========================
def read_json_list(path: Path) -> list[dict]:
    """Read a JSON list from disk safely."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []

def append_json_list(path: Path, item: dict) -> None:
    """Append dict to a JSON list file safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = read_json_list(path)
    data.append(item)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------------------
# BLOG CONFIG
# ---------------------------------------------------------------------------
BLOG_DIR = Path(app.template_folder or "templates") / "blog"
_slug_re = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# ✅ Correct static image folder
BLOG_IMG_DIR = Path(app.static_folder) / "img" / "blog" / "soulspeaks"

def _find_blog_image(slug: str) -> str | None:
    """
    Auto-match image to slug.
    Example:
    slug = 'gods-love-beyond-sound'
    image file = 'gods-love-beyond-sound.jpg'
    """

    filename = f"{slug}.jpg"
    img_path = BLOG_IMG_DIR / filename

    if img_path.exists():
        return f"img/blog/soulspeaks/{filename}"

    # fallback
    default_path = BLOG_IMG_DIR / "default.jpg"
    if default_path.exists():
        return "img/blog/soulspeaks/default.jpg"

    return None

STUDY_PAGES = {
    # Introduction / Coin series
    "coin-1": {
        "order": 1,
        "title": "Coin Study — Part 1",
        "template": "study/introduction/study_coin_1.html",
        "group": "Introduction",
    },
    "coin-2": {
        "order": 2,
        "title": "Coin Study — Part 2",
        "template": "study/introduction/study_coin_2.html",
        "group": "Introduction",
    },
    "coin-3": {
        "order": 3,
        "title": "Coin Study — Part 3",
        "template": "study/introduction/study_coin_3.html",
        "group": "Introduction",
    },

    # Master Plan (your confirmed order)
    "secret-inside-glove": {
        "order": 1,
        "title": "Lesson 01: The Secret Inside the Glove",
        "template": "study/master_plan/lesson_01_secret_inside_glove.html",
        "group": "Master Plan",
    },
    "three-room-house": {
        "order": 2,
        "title": "Lesson 02: The Three-Room House",
        "template": "study/master_plan/lesson_02_three_room_house.html",
        "group": "Master Plan",
    },
    "broken-tv": {
        "order": 3,
        "title": "Lesson 03: The Broken TV Screen",
        "template": "study/master_plan/lesson_03_broken_tv.html",
        "group": "Master Plan",
    },
    "war-two-natures": {
        "order": 4,
        "title": "Lesson 04: The War of Two Natures",
        "template": "study/master_plan/lesson_04_war_two_natures.html",
        "group": "Master Plan",
    },
}

def _month_label(m: int) -> str:
    try:
        return month_name[m]
    except Exception:
        return str(m)

def _pretty_title_from_slug(slug: str) -> str:
    """Fallback title if the post doesn’t define one."""
    return slug.replace("-", " ").title()

def _first_paragraph_from_template(slug: str) -> str:
    """
    Tiny excerpt helper (no heavy parsing):
    Reads the blog html file and grabs first <p>...</p> content.
    If not found, returns empty string.
    """
    path = BLOG_DIR / f"{slug}.html"
    if not path.exists():
        return ""
    try:
        html = path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"<p[^>]*>(.*?)</p>", html, flags=re.I | re.S)
        if not m:
            return ""
        # strip tags inside that <p>
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        return text[:220] + ("..." if len(text) > 220 else "")
    except Exception:
        return ""

def _infer_year_month(slug: str) -> tuple[int, int]:
    """
    Simple rule: infer from your known slugs (Feb/Mar/Apr 2026).
    You can expand later.
    """
    feb = {"gods-love-beyond-sound", "silence-is-not-absence"}
    mar = {"peter-walks-on-water-faith-without-noise", "when-the-wind-is-loud-but-god-is-near"}
    apr = {"healing-is-not-always-loud", "when-jesus-touches-before-he-speaks"}

    if slug in feb: return (2026, 2)
    if slug in mar: return (2026, 3)
    if slug in apr: return (2026, 4)
    return (date.today().year, date.today().month)

def list_blog_posts() -> list[dict]:
    """
    Build posts list from templates/blog/*.html (excluding index.html).
    """
    posts: list[dict] = []
    if not BLOG_DIR.exists():
        return posts

    for p in sorted(BLOG_DIR.glob("*.html")):
        if p.name.lower() == "index.html":
            continue
        slug = p.stem.strip().lower()
        if not _slug_re.match(slug):
            continue

        y, m = _infer_year_month(slug)
        image = _find_blog_image(slug)
        excerpt = _first_paragraph_from_template(slug)

        posts.append({
            "slug": slug,
            "title": _pretty_title_from_slug(slug),
            "year": y,
            "month": m,
            "date": f"{y}-{m:02d}-01",
            "image": image,      # static-relative
            "excerpt": excerpt,  # short
        })

    # newest first
    posts.sort(key=lambda x: x.get("date", ""), reverse=True)
    return posts

# =============================================================================
# 14) Routes (clean block)
# =============================================================================

# ---------- Utilities ----------
def _safe_static(filename: str) -> str | None:
    """Return static URL if file exists; else None."""
    filename = (filename or "").lstrip("/\\")
    path = Path(app.static_folder) / filename
    return url_for("static", filename=filename) if path.exists() else None


# ---------- Verses Data ----------
def load_verses() -> list[dict]:
    """
    Load verse cards from data/verses.json if present.
    Fallback to built-in defaults if missing/invalid.
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
        if isinstance(data, list):
            return data
        logger.warning("verses.json is not a list (got %s). Using fallback.", type(data).__name__)
        return fallback
    except Exception as e:
        logger.warning("Failed to load verses.json (%s). Using fallback.", e)
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
@limiter.limit("60 per minute")
def today_view():
    """Show devotion for today (or requested date) + WhatsApp share preview."""
    mode = (request.args.get("mode") or DEFAULT_MODE).strip().lower()
    mode = mode if mode in ("morning", "night") else DEFAULT_MODE

    raw_date = (request.args.get("date") or "").strip()
    norm = normalize_date_str(raw_date) if raw_date else None
    try:
        target_date = datetime.strptime(norm, "%Y-%m-%d").date() if norm else date.today()
    except Exception:
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

    yday_date = target_date - timedelta(days=1)
    ctx["yday_url"] = url_for("today", date=yday_date.isoformat(), mode=mode)
    ctx["yday_label"] = "← Yesterday’s devotion"

    return render_template("devotion.html", **ctx)


@app.route("/anchor", endpoint="anchor")
def anchor():
    ctx = common_page_ctx(active="anchor")
    return render_template("anchor/index.html", **ctx)


# ---------- Verses ----------
@app.route("/verses", endpoint="verses")
def verses():
    verses_data = load_verses()
    cards: list[dict] = []

    for idx, v in enumerate(verses_data):
        image = (v.get("image") or "").strip()
        src = _safe_static(f"img/verses/{image}") if image else None
        if not src:
            src = _safe_static("img/verses/placeholder.jpg")

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
    if not src:
        src = _safe_static("img/verses/placeholder.jpg")

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


# ---------- Declarations ----------
DECLARATION_IMAGES = [f"{chr(c)}.jpg" for c in range(ord("A"), ord("Z") + 1)]

@app.route("/declarations", methods=["GET"], endpoint="declarations")
def declarations():
    ctx = common_page_ctx(active="declarations")

    items: list[dict] = []
    for i, fname in enumerate(DECLARATION_IMAGES):
        slug = fname.rsplit(".", 1)[0]
        img_url = _safe_static(f"img/declarations/{fname}")
        if not img_url:
            img_url = _safe_static("img/declarations/placeholder.jpg")

        items.append({
            "i": i,
            "slug": slug,
            "img": img_url,
            "title": slug.replace("_", " ").title(),
        })

    open_slug = (request.args.get("open") or "").strip()
    valid_slugs = {x["slug"] for x in items}
    ctx["declarations"] = items
    ctx["open_slug"] = open_slug if open_slug in valid_slugs else ""

    return render_template("declarations/index.html", **ctx)


# ---------- Prayer ----------
PRAYER_TOPICS = [
    {"value": "peace",         "label": "🕊️ Peace / Anxiety"},
    {"value": "relationships", "label": "💞 Relationships / Family"},
    {"value": "grief",         "label": "💔 Grief / Loss"},
    {"value": "healing",       "label": "🩺 Sickness / Healing"},
    {"value": "work",          "label": "💼 Work / Finances"},
    {"value": "direction",     "label": "🧭 Direction / Decisions"},
    {"value": "faith",         "label": "🙏 Faith / Spiritual Strength"},
    {"value": "community",     "label": "🧑‍🤝‍🧑 Community / Others"},
    {"value": "other",         "label": "✍️ Other"},
]
PRAYER_TOPIC_VALUES = {t["value"] for t in PRAYER_TOPICS}

@app.route("/prayer", methods=["GET", "POST"], endpoint="prayer")
@limiter.limit("5 per minute", methods=["POST"])
@limiter.limit("30 per day", methods=["POST"])
def prayer():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:80]
        contact = (request.form.get("contact") or "").strip()[:120]
        topic = (request.form.get("topic") or "").strip() or "other"
        if topic not in PRAYER_TOPIC_VALUES:
            topic = "other"

        req_text = (request.form.get("request") or "").strip()
        req_text = req_text[:2000]

        if not req_text:
            flash("❌ Please write your prayer request.", "error")
            return redirect(url_for("prayer"))

        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "name": name,
            "contact": contact,
            "topic": topic,
            "request": req_text,
        }

        append_json_list(PRAYER_REQUESTS_FILE, record)

        try:
            send_prayer_email(record)
        except Exception:
            # Don’t break the site if email is not configured
            logger.info("Prayer email skipped (not configured or failed).")

        flash("🙏 Your prayer request was received.", "success")
        return redirect(url_for("prayer", ok=1))

    ctx = common_page_ctx(active="prayer")
    ctx["prayer_topics"] = PRAYER_TOPICS
    return render_template("prayer.html", **ctx)


def send_prayer_email(record: dict) -> bool:
    to_addr = (os.getenv("ALERT_EMAIL_TO") or "").strip()
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int(os.getenv("SMTP_PORT", "587") or "587")
    user = (os.getenv("SMTP_USER") or "").strip()
    pwd = (os.getenv("SMTP_PASS") or "").strip()

    if not all([to_addr, host, user, pwd]):
        return False

    msg = EmailMessage()
    msg["Subject"] = f"New Prayer Request ({record.get('topic', 'other')})"
    msg["From"] = (os.getenv("ALERT_EMAIL_FROM") or user).strip()
    msg["To"] = to_addr
    msg.set_content(
        f"Time: {record.get('ts')}\n"
        f"Name: {record.get('name')}\n"
        f"Contact: {record.get('contact')}\n"
        f"Topic: {record.get('topic')}\n\n"
        f"Request:\n{record.get('request')}\n"
    )

    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(user, pwd)
        smtp.send_message(msg)

    return True


# ---------- About ----------
@app.route("/about", endpoint="about")
def about():
    ctx = common_page_ctx(active="about")
    return render_template("about.html", **ctx)

# =============================================================================
# Study + Donation + Volunteer + Auth (clean block)
# =============================================================================
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

SLUG_RE = re.compile(r"^[a-z0-9_-]+$")

def build_study_ctx(page_title: str):
    ctx = common_page_ctx(active="study")
    ctx["title"] = page_title
    ctx["hero_class"] = "hero"
    ctx["hero_bg"] = HERO_DAY_BG
    return ctx

# Single source of truth: slug -> template + title + group + order
STUDY_PAGES: dict[str, dict] = {
    # Introduction / Coin series
    "coin-1": {
        "order": 1,
        "title": "Coin Study — Part 1",
        "template": "study/introduction/study_coin_1.html",
        "group": "Introduction",
    },
    "coin-2": {
        "order": 2,
        "title": "Coin Study — Part 2",
        "template": "study/introduction/study_coin_2.html",
        "group": "Introduction",
    },
    "coin-3": {
        "order": 3,
        "title": "Coin Study — Part 3",
        "template": "study/introduction/study_coin_3.html",
        "group": "Introduction",
    },

    # Master Plan (confirmed order)
    "secret-inside-glove": {
        "order": 1,
        "title": "Lesson 01: The Secret Inside the Glove",
        "template": "study/master_plan/lesson_01_secret_inside_glove.html",
        "group": "Master Plan",
    },
    "three-room-house": {
        "order": 2,
        "title": "Lesson 02: The Three-Room House",
        "template": "study/master_plan/lesson_02_three_room_house.html",
        "group": "Master Plan",
    },
    "broken-tv": {
        "order": 3,
        "title": "Lesson 03: The Broken TV Screen",
        "template": "study/master_plan/lesson_03_broken_tv.html",
        "group": "Master Plan",
    },
    "war-two-natures": {
        "order": 4,
        "title": "Lesson 04: The War of Two Natures",
        "template": "study/master_plan/lesson_04_war_two_natures.html",
        "group": "Master Plan",
    },
}

SLUG_RE = re.compile(r"^[a-z0-9_-]+$")


def build_study_ctx(page_title: str) -> dict:
    ctx = common_page_ctx(active="study")
    ctx.update({
        "title": page_title,
        "hero_class": "hero",
        "hero_bg": HERO_DAY_BG,
    })
    return ctx


# ---------- Study ----------
@app.route("/study")
def study_redirect():
    # legacy: /study -> /studies
    return redirect(url_for("study_index"))


@app.route("/studies", endpoint="study_index")
def study_index():
    pages: list[dict] = []
    for slug, meta in STUDY_PAGES.items():
        pages.append({
            "slug": slug,
            "title": meta.get("title", slug),
            "group": meta.get("group", "Study"),
            "order": meta.get("order", 999),
        })

    group_order = {"Introduction": 1, "Master Plan": 2}
    pages.sort(key=lambda p: (group_order.get(p["group"], 99), p["order"], p["title"]))

    ctx = build_study_ctx("Study Hub")
    return render_template("study/index.html", pages=pages, **ctx)


@app.route("/studies/<slug>", endpoint="study_detail")
def study_detail(slug: str):
    if not SLUG_RE.fullmatch(slug):
        abort(404)

    meta = STUDY_PAGES.get(slug)
    if not meta:
        abort(404)

    template = meta.get("template")
    if not template:
        abort(404)

    ctx = build_study_ctx(meta.get("title", slug))
    return render_template(template, **ctx)


# ---- Optional legacy redirects (keep for old links) ----
@app.route("/studies/coin/1")
def legacy_coin_1():
    return redirect(url_for("study_detail", slug="coin-1"), code=301)


@app.route("/studies/coin/2")
def legacy_coin_2():
    return redirect(url_for("study_detail", slug="coin-2"), code=301)


@app.route("/studies/coin/3")
def legacy_coin_3():
    return redirect(url_for("study_detail", slug="coin-3"), code=301)


@app.route("/studies/master/secret-inside-glove")
def legacy_secret_glove():
    return redirect(url_for("study_detail", slug="secret-inside-glove"), code=301)


@app.route("/studies/master/three-room-house")
def legacy_three_room_house():
    return redirect(url_for("study_detail", slug="three-room-house"), code=301)


@app.route("/studies/master/broken-tv")
def legacy_broken_tv():
    return redirect(url_for("study_detail", slug="broken-tv"), code=301)


@app.route("/studies/master/war-two-natures")
def legacy_war_two_natures():
    return redirect(url_for("study_detail", slug="war-two-natures"), code=301)


# ---------- Donation (PUBLIC) ----------
@app.route("/donation", endpoint="donation")
def donation():
    ctx = common_page_ctx(active="donation")
    ctx["paypal_link"] = PAYPAL_LINK or None
    return render_template("donation.html", **ctx)


# ---------- Volunteer (PUBLIC) ----------
@app.route("/volunteer", methods=["GET", "POST"], endpoint="volunteer")
def volunteer():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:80]
        skills = (request.form.get("skills") or "").strip()[:200]
        contact = (request.form.get("contact") or "").strip()[:120]

        if name or skills or contact:
            record = {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "name": name,
                "skills": skills,
                "contact": contact,
            }
            append_json_list(VOLUNTEERS_FILE, record)

        flash("💚 Thank you for offering your skills!", "success")
        return redirect(url_for("volunteer", ok=1))

    ctx = common_page_ctx(active="volunteer")
    return render_template("volunteer.html", **ctx)


# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"], endpoint="login")
def login():
    if is_authed():
        return redirect(url_for("admin"))

    error: str | None = None

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
# Admin Routes (clean + consistent + safer)
# =============================================================================

# --- small helpers (admin) ---
def _safe_filename(name: str) -> str:
    """Allow only simple filenames like 'abc.jpg' (prevents path tricks)."""
    name = (name or "").strip()
    name = name.replace("\\", "/").split("/")[-1]  # basename only
    return re.sub(r"[^A-Za-z0-9._-]+", "", name)

def _slugify(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "post"

def _truncate(s: str, n: int) -> str:
    s = (s or "").strip()
    return s[:n]

def load_posts() -> list[dict]:
    """Blog posts stored as JSON list (data/blog_posts.json)."""
    path = Path(BLOG_DATA_PATH)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_posts(posts: list[dict]) -> None:
    path = Path(BLOG_DATA_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


# =============================================================================
# Admin Dashboard
# =============================================================================
@app.route("/admin", endpoint="admin")
@require_auth
def admin_dashboard():
    ctx = common_page_ctx(active="admin")
    ctx["today_str"] = date.today().isoformat()
    return render_template("admin/admin.html", **ctx)


# =============================================================================
# Admin — Verses
# =============================================================================
@app.route("/admin/verses", methods=["GET", "POST"], endpoint="admin_verses")
@require_auth
def admin_verses_view():
    error: str | None = None
    success: str | None = None

    verses_img_dir = Path(app.static_folder) / "img" / "verses"
    try:
        image_files = sorted(
            f.name for f in verses_img_dir.iterdir()
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")
        )
    except Exception:
        image_files = []

    verses = load_verses()
    action = (request.form.get("action") or "").strip().lower() if request.method == "POST" else ""

    def _save_verses() -> None:
        VERSES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with VERSES_FILE.open("w", encoding="utf-8") as f:
            json.dump(verses, f, ensure_ascii=False, indent=2)

    if request.method == "POST":
        try:
            if action == "delete":
                idx = int((request.form.get("index") or "").strip())
                if 0 <= idx < len(verses):
                    removed = verses.pop(idx)
                    _save_verses()
                    success = f"Deleted verse #{idx} ({removed.get('ref','')})."
                else:
                    error = "Verse index out of range."

            elif action == "update":
                idx = int((request.form.get("index") or "").strip())
                if 0 <= idx < len(verses):
                    rec = verses[idx]
                    rec["image"] = _safe_filename(request.form.get("image") or rec.get("image", ""))
                    rec["ref"]   = _truncate(request.form.get("ref") or rec.get("ref", ""), 120)
                    rec["title"] = _truncate(request.form.get("title") or rec.get("title", ""), 140)
                    rec["note"]  = _truncate(request.form.get("note") or rec.get("note", ""), 600)
                    _save_verses()
                    success = f"Updated verse #{idx}."
                else:
                    error = "Verse index out of range."

            else:  # add
                image = _safe_filename(request.form.get("image") or "")
                ref   = _truncate(request.form.get("ref") or "", 120)
                title = _truncate((request.form.get("title") or "").strip() or ref, 140)
                note  = _truncate(request.form.get("note") or "", 600)

                if not image or not ref:
                    error = "Image filename and Scripture reference are required."
                else:
                    verses.append({"image": image, "ref": ref, "title": title, "note": note})
                    _save_verses()
                    success = "Verse added successfully."

        except Exception as e:
            error = f"Action failed: {e}"

    cards: list[dict] = []
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


# =============================================================================
# Admin — Prayer Requests
# =============================================================================
@app.route("/admin/requests", endpoint="admin_requests")
@require_auth
def admin_requests():
    items = read_json_list(PRAYER_REQUESTS_FILE)
    items = list(reversed(items))  # newest first
    ctx = common_page_ctx(active="admin")
    return render_template("admin/admin_requests.html", items=items, **ctx)


@app.route("/admin/requests/delete/<int:index>", methods=["POST"], endpoint="admin_request_delete")
@require_auth
def admin_request_delete(index: int):
    items = load_json_list(PRAYER_REQUESTS_FILE) or []

    # Convert display index to real index
    real_index = len(items) - 1 - index

    if 0 <= real_index < len(items):
        removed = items.pop(real_index)
        PRAYER_REQUESTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PRAYER_REQUESTS_FILE.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        flash(f"Prayer from {removed.get('name', 'Anonymous')} archived.", "success")
    else:
        flash("Request not found.", "error")

    return redirect(url_for("admin_requests"))

# =============================================================================
# Admin — Blog (JSON-backed)
# =============================================================================
# ✅ Admin — Blog (JSON-backed)
@app.route("/admin/blog", methods=["GET", "POST"], endpoint="admin_blog")
@require_auth
def admin_blog():
    if request.method == "POST":
        title_raw = request.form.get("title") or ""
        title = _truncate(title_raw, 140)
        slug = _slugify(request.form.get("slug") or title)

        new_post = {
            "title": title,
            "slug": slug,
            "date_display": _truncate(request.form.get("date") or "", 40),
            "month_label": _truncate(request.form.get("month_label") or "", 40),
            "excerpt": _truncate(request.form.get("excerpt") or "", 260),
            "section1_title": _truncate(request.form.get("s1_title") or "", 120),
            "section1_text": _truncate(request.form.get("s1_text") or "", 5000),
            "scripture_ref": _truncate(request.form.get("scripture_ref") or "", 120),
            "scripture_quote": _truncate(request.form.get("scripture_quote") or "", 600),
            "image": _safe_filename(request.form.get("image") or "default.jpg"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        posts = load_posts()
        posts.insert(0, new_post)
        save_posts(posts)

        flash("Post published to Soul Speaks!", "success")
        return redirect(url_for("admin_blog"))

    ctx = common_page_ctx(active="admin")
    ctx["posts_count"] = len(load_posts())

    # ✅ FIXED TEMPLATE PATH
    return render_template("admin/admin_blog_form.html", **ctx)

# =============================================================================
# Admin — Feedback / Volunteers / Donations
# =============================================================================
@app.route("/admin/feedback", endpoint="admin_feedback")
@require_auth
def admin_feedback():
    items = read_json_list(FEEDBACK_FILE)
    items = list(reversed(items))
    ctx = common_page_ctx(active="admin")
    return render_template("admin/admin_feedback.html", items=items, **ctx)


@app.route("/admin/volunteers", endpoint="admin_volunteers")
@require_auth
def admin_volunteers():
    rows = read_json_list(VOLUNTEERS_FILE)
    rows = list(reversed(rows))
    ctx = common_page_ctx(active="admin")
    return render_template("admin/admin_volunteers.html", rows=rows, **ctx)


# =============================================================================
# Admin — Donations
# =============================================================================
@app.route("/admin/donations", methods=["GET", "POST"], endpoint="admin_donations")
@require_auth
def admin_donations_view():
    error: str | None = None
    success: str | None = None

    if request.method == "POST":
        donor_name = (request.form.get("donor_name") or "").strip()
        amount_raw = (request.form.get("amount") or "").strip()
        currency = (request.form.get("currency") or "USD").strip().upper()
        note = (request.form.get("note") or "").strip()
        date_str = (request.form.get("date") or "").strip() or date.today().isoformat()

        try:
            amount = float(amount_raw)
        except Exception:
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

    items = read_json_list(DONATIONS_FILE)

    # newest first (safe sort)
    try:
        items.sort(key=lambda r: (r.get("date") or "", r.get("created_at") or ""), reverse=True)
    except Exception:
        pass

    total_amount = 0.0
    for r in items:
        amt = r.get("amount")
        if isinstance(amt, (int, float)):
            total_amount += float(amt)

    ctx = common_page_ctx(active="admin")
    return render_template(
        "admin/admin_donations.html",
        items=items,
        total_amount=total_amount,
        error=error,
        success=success,
        **ctx,
    )

    return render_template("admin/admin_donations.html",
                       items=items,
                       total_amount=total_amount,
                       error=error,
                       success=success,
                       **ctx)

# =============================================================================
# Admin — WhatsApp Builder
# NOTE: build_share_payload() must exist in your app (same signature).
# =============================================================================
@app.route("/admin/whatsapp", methods=["GET", "POST"], endpoint="admin_whatsapp")
@require_auth
def admin_whatsapp():
    ctx = common_page_ctx(active="admin")
    ctx["prayer_topics"] = PRAYER_TOPICS

    result: dict = {}
    selected_topic = ""

    if request.method == "POST":
        date_str = (request.form.get("date") or date.today().isoformat()).strip()
        mode = (request.form.get("mode") or "morning").strip().lower()
        if mode not in ("morning", "night"):
            mode = "morning"

        selected_topic = (request.form.get("topic") or "").strip()

        # Must exist elsewhere in your file
        devotion_payload = build_share_payload(date_str=date_str, mode=mode)

        picked = None
        if selected_topic:
            picked = pick_random_request(selected_topic)

        add_on = ""
        if picked:
            who = (picked.get("name") or "Someone").strip()[:80]
            topic = (picked.get("topic") or "Prayer").strip()[:40]
            req = (picked.get("request") or "").strip().replace("\n", " ")
            if len(req) > 240:
                req = req[:240].rstrip() + "…"

            add_on = (
                "\n\n🙏 Prayer Focus (from community)\n"
                f"👤 {who}\n"
                f"🏷️ {topic}\n"
                f"📝 {req}\n"
                "\nIn Jesus’ name, Amen."
            )
        else:
            add_on = "\n\nIn Jesus’ name, Amen."

        # Attach to each message variant (if present)
        for k in ("text", "text_morning", "text_night"):
            if devotion_payload.get(k):
                devotion_payload[k] += add_on

        result = devotion_payload

    ctx.update({
        "result": result,
        "selected_topic": selected_topic,
    })
    return render_template("admin/admin_whatsapp.html", **ctx)


@app.route("/admin/whatsapp/send", methods=["POST"], endpoint="admin_whatsapp_send")
@require_auth
def admin_whatsapp_send():
    today_ = date.today()

    # ----------------------------
    # 1) MODE (clean + robust)
    # ----------------------------
    raw_mode = (request.form.get("mode") or "").strip().lower()

    MODE_MAP = {
        "morning": "morning",
        "m": "morning",
        "am": "morning",

        "night": "night",
        "n": "night",
        "pm": "night",

        "both": "both",
        "b": "both",
        "morning & night": "both",
        "morning-night": "both",
        "morning and night": "both",
    }
    mode = MODE_MAP.get(raw_mode, "morning")  # default safe

    # ----------------------------
    # 2) DATE (safe)
    # ----------------------------
    raw_date = (request.form.get("date") or today_.isoformat()).strip()
    try:
        target_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except Exception:
        target_date = today_
        raw_date = today_.isoformat()

    # ----------------------------
    # 3) SHARE URL BUILDER (single source)
    # ----------------------------
    def make_share_urls(message: str) -> dict[str, str]:
        enc = quote(message)
        return {
            "share_web": f"https://web.whatsapp.com/send?text={enc}",
            "share_api": f"https://api.whatsapp.com/send?text={enc}",
            "share_wa":  f"https://wa.me/?text={enc}",
        }

    # ----------------------------
    # 4) SINGLE MODE RESPONSE
    # ----------------------------
    if mode in ("morning", "night"):
        entry = load_devotion_for(target_date, mode) or placeholder_devotion(raw_date, mode)
        text = build_whatsapp_text(entry, mode, target_date)
        urls = make_share_urls(text)
        return jsonify(
            ok=True,
            mode=mode,
            date=raw_date,
            text=text,
            share_web=urls["share_web"],
            share_api=urls["share_api"],
            share_wa=urls["share_wa"],
            join_url=SITE_JOIN_URL,
        )

    # ----------------------------
    # 5) BOTH MODES RESPONSE
    # ----------------------------
    entry_m = load_devotion_for(target_date, "morning") or placeholder_devotion(raw_date, "morning")
    entry_n = load_devotion_for(target_date, "night") or placeholder_devotion(raw_date, "night")

    text_m = build_whatsapp_text(entry_m, "morning", target_date)
    text_n = build_whatsapp_text(entry_n, "night", target_date)

    urls_m = make_share_urls(text_m)
    urls_n = make_share_urls(text_n)

    return jsonify(
        ok=True,
        mode="both",
        date=raw_date,
        text_morning=text_m,
        text_night=text_n,
        share_web_morning=urls_m["share_web"],
        share_api_morning=urls_m["share_api"],
        share_wa_morning=urls_m["share_wa"],
        share_web_night=urls_n["share_web"],
        share_api_night=urls_n["share_api"],
        share_wa_night=urls_n["share_wa"],
        join_url=SITE_JOIN_URL,
    )

# =============================================================================
# BLOG: helpers + routes (clean, no duplicates, filters work)
# =============================================================================

# ----------------------------
# Blog helpers (small + safe)
# ----------------------------
def _month_label(m: int) -> str:
    try:
        return month_name[m]
    except Exception:
        return str(m)

def _coerce_int(v, default=None):
    try:
        return int(v)
    except Exception:
        return default

def _filter_posts(posts: list[dict], year: int | None, month: int | None) -> list[dict]:
    out: list[dict] = []
    for p in posts:
        y = p.get("year")
        m = p.get("month")
        if year is not None and y != year:
            continue
        if month is not None and m != month:
            continue
        out.append(p)
    return out

def _decorate_posts(posts: list[dict]) -> list[dict]:
    """Add labels for templates (month_label, date_display)."""
    for p in posts:
        m = p.get("month")
        d = p.get("date")
        p["month_label"] = _month_label(m) if isinstance(m, int) else ""
        try:
            if isinstance(d, str) and d:
                dt = datetime.strptime(d, "%Y-%m-%d").date()
                p["date_display"] = dt.strftime("%b %d, %Y")
            else:
                p["date_display"] = ""
        except Exception:
            p["date_display"] = d or ""
    return posts

# Optional: month theme banner (simple)
MONTH_THEMES = {
    (2026, 2): {"title": "God’s Love in Silence", "subtitle": "God’s Love Beyond Sound • Silence Is Not Absence"},
    (2026, 3): {"title": "Seeing Beyond Noise", "subtitle": "Focus vs distraction • Faith without noise"},
    (2026, 4): {"title": "Healing Without Spectacle", "subtitle": "God’s quiet restoration"},
}

def _get_month_theme(year: int | None, month: int | None):
    if year is None or month is None:
        return None
    return MONTH_THEMES.get((year, month))

def _sort_posts_newest_first(posts: list[dict]) -> list[dict]:
    return sorted(
        posts,
        key=lambda p: (
            p.get("year") or 0,
            p.get("month") or 0,
            p.get("date") or "",
            p.get("slug") or "",
        ),
        reverse=True,
    )

def _get_available_years(posts: list[dict]) -> list[int]:
    years = sorted({p.get("year") for p in posts if isinstance(p.get("year"), int)}, reverse=True)
    return years or [date.today().year]

def _valid_month(m: int | None) -> int | None:
    return m if isinstance(m, int) and 1 <= m <= 12 else None


# ----------------------------
# Blog routes (PUBLIC)
# ----------------------------
@app.route("/blog", endpoint="blog_index")
def blog_index():
    """
    Public blog index page.
    Supports filters: ?year=2026&month=2
    """
    # Read filters
    year_q = _coerce_int(request.args.get("year"), None)
    month_q = _coerce_int(request.args.get("month"), None)
    month_q = _valid_month(month_q)  # returns 1..12 or None

    # Build posts list from templates/blog/*.html
    posts_all = list_blog_posts()
    posts_all = _sort_posts_newest_first(posts_all)
    posts_all = _decorate_posts(posts_all)

    # Dropdown options
    years = _get_available_years(posts_all)
    months = [{"value": i, "label": _month_label(i)} for i in range(1, 13)]

    # Defaults
    selected_year = year_q if (year_q in years) else (years[0] if years else date.today().year)
    selected_month = month_q  # None = all months

    # Filter final list
    posts = _filter_posts(posts_all, selected_year, selected_month)

    ctx = common_page_ctx(active="blog")
    ctx.update({
        "posts": posts,
        "years": years if years else [date.today().year],
        "months": months,
        "selected_year": selected_year,
        "selected_month": selected_month or "",
        "month_theme": _get_month_theme(selected_year, selected_month),
        "SITE_URL": request.url_root.rstrip("/"),
    })

    # ✅ THIS is the PUBLIC blog index template
    return render_template("blog/index.html", **ctx)


@app.route("/blog/<slug>", endpoint="blog_post")
def blog_post(slug: str):
    """
    Public blog post page. Template must exist:
    templates/blog/<slug>.html
    """
    slug = (slug or "").strip().lower()
    if not _slug_re.match(slug):
        abort(404)

    abs_path = BLOG_DIR / f"{slug}.html"
    if not abs_path.exists():
        abort(404)

    # Metadata from registry (safe fallback)
    posts_all = list_blog_posts()
    meta = next((p for p in posts_all if p.get("slug") == slug), None)

    title = (meta.get("title") if meta else None) or _pretty_title_from_slug(slug)
    image = (meta.get("image") if meta else None) or _find_blog_image(slug)
    excerpt = (meta.get("excerpt") if meta else "") if meta else ""

    ctx = common_page_ctx(active="blog")
    ctx.update({
        "post": {
            "slug": slug,
            "title": title,
            "image": image,
            "excerpt": excerpt,
        },
        "SITE_URL": request.url_root.rstrip("/"),
    })

    rel_tpl = f"blog/{slug}.html"
    return render_template(rel_tpl, **ctx)

# =============================================================================
# Run (HTTP dev) + auto-open browser
# =============================================================================
def _open_browser():
    try:
        import webbrowser
        webbrowser.open(f"http://{HOST}:{PORT}/")
    except Exception:
        pass

if __name__ == "__main__":
    from threading import Timer
    logger.info("💜 SoulStart Devotion — Flask heartbeat ready (HTTP dev)… %s", APP_VERSION)
    if AUTO_OPEN:
        Timer(1.0, _open_browser).start()
    app.run(host=HOST, port=PORT, debug=not IS_PROD)