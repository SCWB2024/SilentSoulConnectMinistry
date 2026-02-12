# app.py — SoulStart Devotion — v13 (Clean Single-App Core)
from __future__ import annotations

from email.mime import message
import os
import json
import secrets
import logging
import re
from datetime import datetime, date, timedelta
from calendar import month_name
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
    Flask,
    request,
    session,
    render_template,
    redirect,
    current_app,
    url_for,
    jsonify,
    send_from_directory,
    g,
    flash,
    abort,
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

PRAYER_REQUESTS_FILE = DATA_DIR / "prayer_requests.json"

def load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

VOLUNTEERS_FILE = DATA_DIR / "volunteers.json"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
PRAYER_REQUESTS_FILE = DATA_DIR / "prayer_requests.json"
BLOG_POSTS = DATA_DIR / "blog_posts.json"
DEVOTIONS_DIR = DATA_DIR / "devotions"
DEVOTIONS_DIR.mkdir(exist_ok=True)

# Path to your blog data
BLOG_DATA_PATH = 'data/blog_posts.json'

print("SAVING TO:", (DATA_DIR / "prayer_requests.json").resolve())

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

def read_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def append_json_list(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = read_json_list(path)
    data.append(item)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

STUDY_SERIES: list[dict] = []
VERSE_CARDS: list[dict] = []

import random

def load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def pick_random_request(topic: str | None = None) -> dict | None:
    file = DATA_DIR / "prayer_requests.json"
    items = load_json_list(file)
    if not items:
        return None

    topic = (topic or "").strip()
    if topic:
        filtered = [r for r in items if (r.get("topic") or "").strip() == topic]
        if filtered:
            return random.choice(filtered)

    # fallback: any topic
    return random.choice(items)

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
    """Injects variables into every single template automatically."""
    from datetime import datetime
    return {
        "SOCIAL_LINKS": SOCIAL_LINKS,
        "SITE_JOIN_URL": SITE_JOIN_URL,
        "SITE_THEME": SITE_THEME,
        "APP_VERSION": APP_VERSION,
        "PAYPAL_LINK": PAYPAL_LINK, # Ensure this matches the button logic
        "FACEBOOK_URL": FACEBOOK_URL,
        "LINKEDIN_URL": LINKEDIN_URL,
        "JOIN_URL": JOIN_URL,
        "SITE_URL": request.url_root.rstrip("/"),
        "now": datetime.now(),  # <--- THIS FIXES THE 'now' ERROR
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

def append_json_list(path, item):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "[]")
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
    data.append(item)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
AMEN_LINE = "In Jesus’ name, Amen."

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

# ---------------------------------------------------------------------------
# BLOG CONFIG (templates/blog/*.html are the posts)
# ---------------------------------------------------------------------------
BLOG_DIR = Path(app.template_folder or "templates") / "blog"

_slug_re = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")  # gods-love-beyond-sound

# Your static blog images folder (recommended)
BLOG_IMG_DIR = Path(app.static_folder) / "img" / "soulspeaks"

# Optional: month themes banner
MONTH_THEMES = {
    (2026, 2): {"title": "God’s Love in Silence", "subtitle": "God’s Love Beyond Sound • Silence Is Not Absence"},
    (2026, 3): {"title": "Seeing Beyond Noise", "subtitle": "Focus vs distraction • Faith without noise"},
    (2026, 4): {"title": "Healing Without Spectacle", "subtitle": "God’s quiet restoration"},
}

# Map blog slug -> image filename (keep it simple + explicit)
BLOG_IMAGES = {
    "gods-love-beyond-sound": "Feb Blog1.png",
    "silence-is-not-absence": "Feb Blog2.png",
    "peter-walks-on-water-faith-without-noise": "mar blog1.png",
    "when-the-wind-is-loud-but-god-is-near": "mar blog2.png",
    "healing-is-not-always-loud": "april blog1.png",
    "when-jesus-touches-before-he-speaks": "april blog2.png",
}

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

def _find_blog_image(slug: str) -> str | None:
    """
    Return a static-relative path like:
      img/soulspeaks/Feb Blog1.png
    """
    filename = BLOG_IMAGES.get(slug)
    if not filename:
        return None
    # file exists check (optional but helpful)
    if (BLOG_IMG_DIR / filename).exists():
        return f"img/soulspeaks/{filename}"
    return f"img/soulspeaks/{filename}"  # still return even if missing (won’t crash)

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
        return text[:220]  # keep short
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
    posts.sort(key=lambda x: (x.get("year", 0), x.get("month", 0), x.get("slug", "")), reverse=True)
    return posts

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

PRAYER_TOPICS = [
  {"value":"peace", "label":"🕊️ Peace / Anxiety"},
  {"value":"relationships", "label":"💞 Relationships / Family"},
  {"value":"grief", "label":"💔 Grief / Loss"},
  {"value":"healing", "label":"🩺 Sickness / Healing"},
  {"value":"work", "label":"💼 Work / Finances"},
  {"value":"direction", "label":"🧭 Direction / Decisions"},
  {"value":"faith", "label":"🙏 Faith / Spiritual Strength"},
  {"value":"community", "label":"🧑‍🤝‍🧑 Community / Others"},
  {"value":"other", "label":"✍️ Other"},
]

@app.route("/prayer", methods=["GET", "POST"], endpoint="prayer")
def prayer():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        topic = (request.form.get("topic") or "").strip() or "other"
        req_text = (request.form.get("request") or "").strip()

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

        file = DATA_DIR / "prayer_requests.json"
        append_json_list(file, record)

        flash("🙏 Your prayer request was received.", "success")
        return redirect(url_for("prayer", ok=1))

    ctx = common_page_ctx(active="prayer")
    ctx["prayer_topics"] = PRAYER_TOPICS
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

# Single source of truth: slug -> template + title + group + order
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

    # Master Plan
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

def build_study_ctx(page_title: str):
    ctx = common_page_ctx(active="study")
    ctx["title"] = page_title
    ctx["hero_class"] = "hero"
    ctx["hero_bg"] = HERO_DAY_BG
    return ctx

@app.route("/study")
def study_redirect():
    # legacy: /study -> /studies
    return redirect(url_for("study_index"))

@app.route("/studies", endpoint="study_index")
def study_index():
    pages = []
    for slug, meta in STUDY_PAGES.items():
        pages.append({
            "slug": slug,
            "title": meta["title"],
            "group": meta.get("group", "Study"),
            "order": meta.get("order", 999),
        })

    # Intro first, then Master Plan; within group use order then title
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

    ctx = build_study_ctx(meta["title"])
    return render_template(meta["template"], **ctx)

# ---- Optional legacy redirects (keep for old links) ----
@app.route("/studies/coin/1")
def legacy_coin_1():
    return redirect(url_for("study_detail", slug="coin-1"))

@app.route("/studies/coin/2")
def legacy_coin_2():
    return redirect(url_for("study_detail", slug="coin-2"))

@app.route("/studies/coin/3")
def legacy_coin_3():
    return redirect(url_for("study_detail", slug="coin-3"))

@app.route("/studies/master/secret-inside-glove")
def legacy_secret_glove():
    return redirect(url_for("study_detail", slug="secret-inside-glove"))

@app.route("/studies/master/three-room-house")
def legacy_three_room_house():
    return redirect(url_for("study_detail", slug="three-room-house"))

@app.route("/studies/master/broken-tv")
def legacy_broken_tv():
    return redirect(url_for("study_detail", slug="broken-tv"))

@app.route("/studies/master/war-two-natures")
def legacy_war_two_natures():
    return redirect(url_for("study_detail", slug="war-two-natures"))

# ---------- Donation (PUBLIC) ----------
@app.route("/donation", endpoint="donation")
def donation():
    ctx = common_page_ctx(active="donation")
    ctx["paypal_link"] = None  # Coming soon for now
    return render_template("donation.html", **ctx)

# ---------- Volunteer (PUBLIC) ----------
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
def admin_requests():
    items = load_json_list(PRAYER_REQUESTS_FILE)
    items.reverse()  # newest first

    print("READING FROM:", PRAYER_REQUESTS_FILE.resolve())
    print("ITEM COUNT:", len(items))

    ctx = common_page_ctx(active="admin")
    return render_template("admin/admin_requests.html", items=items, **ctx)


@app.route("/admin/requests/delete/<int:index>", methods=["POST"], endpoint="admin_request_delete")
@require_auth
def admin_request_delete(index: int):
    """Archives a prayer request by removing it from the JSON list."""
    items = load_json_list(PRAYER_REQUESTS_FILE)
    
    # Since the view is reversed, the index from the loop needs to be 
    # handled carefully or we just pop from the list and re-save.
    # The simplest way is to reverse the list back, pop, and save.
    items.reverse() 
    
    if 0 <= index < len(items):
        removed = items.pop(index)
        # Save back to file
        with open(PRAYER_REQUESTS_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
        flash(f"Prayer from {removed.get('name', 'Anonymous')} archived.", "success")
    else:
        flash("Request not found.", "error")
        
    return redirect(url_for("admin_requests"))

def load_posts():
    if not os.path.exists(BLOG_DATA_PATH):
        return []
    with open(BLOG_DATA_PATH, 'r') as f:
        return json.load(f)

def save_posts(posts):
    with open(BLOG_DATA_PATH, 'w') as f:
        json.dump(posts, f, indent=4)

@app.route('/admin/blog', methods=['GET', 'POST'])
def admin_blog():
    if request.method == 'POST':
        # Capture form data
        new_post = {
            "title": request.form.get('title'),
            "slug": request.form.get('title').lower().replace(" ", "-"),
            "date_display": request.form.get('date'),
            "month_label": request.form.get('month_label'),
            "excerpt": request.form.get('excerpt'),
            "section1_title": request.form.get('s1_title'),
            "section1_text": request.form.get('s1_text'),
            "scripture_ref": request.form.get('scripture_ref'),
            "scripture_quote": request.form.get('scripture_quote'),
            "image": request.form.get('image') or "default.jpg"
        }
        
        posts = load_posts()
        posts.insert(0, new_post) # Add to top
        save_posts(posts)
        flash("Post Published to Soul Speaks!")
        return redirect(url_for('blog_index'))
        
    return render_template('admin/blog_form.html')


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


@app.route("/admin/whatsapp", methods=["GET", "POST"], endpoint="admin_whatsapp")
def admin_whatsapp():
    ctx = common_page_ctx(active="admin")
    ctx["prayer_topics"] = PRAYER_TOPICS

    result = {}
    selected_topic = ""

    if request.method == "POST":
        date_str = request.form.get("date") or date.today().isoformat()
        mode = request.form.get("mode") or "morning"
        selected_topic = request.form.get("topic") or ""

        # your existing devotion builder...
        devotion_payload = build_share_payload(date_str=date_str, mode=mode)  # example

        picked = pick_random_request(selected_topic)

        add_on = ""
        if picked:
            who = picked.get("name") or "Someone"
            topic = picked.get("topic") or "Prayer"
            req = (picked.get("request") or "").strip()
            if len(req) > 240:
                req = req[:240].rstrip() + "…"

            add_on = (
                "\n\n🙏 **Prayer Focus (from community)**\n"
                f"👤 {who}\n"
                f"🏷️ {topic}\n"
                f"📝 {req}\n"
                "\nIn Jesus’ name, Amen."
            )
        else:
            add_on = "\n\nIn Jesus’ name, Amen."

        # attach to each message variant
        if devotion_payload.get("text"):
            devotion_payload["text"] += add_on
        if devotion_payload.get("text_morning"):
            devotion_payload["text_morning"] += add_on
        if devotion_payload.get("text_night"):
            devotion_payload["text_night"] += add_on

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

# If your list_blog_posts() already exists, keep yours.
# Expected output for each post:
# {
#   "slug": "gods-love-beyond-sound",
#   "title": "God’s Love Beyond Sound",
#   "date": "2026-02-01"  (ISO string preferred),
#   "month": 2,
#   "year": 2026,
#   "excerpt": "...",
#   "image": "img/blog/soulspeaks/gods-love-beyond-sound.jpg" (static-relative)
# }

def _filter_posts(posts: list[dict], year: int | None, month: int | None) -> list[dict]:
    out = []
    for p in posts:
        y = p.get("year")
        m = p.get("month")
        if year and y != year:
            continue
        if month and m != month:
            continue
        out.append(p)
    return out

def _decorate_posts(posts: list[dict]) -> list[dict]:
    """Add labels for template."""
    for p in posts:
        y = p.get("year")
        m = p.get("month")
        d = p.get("date")
        p["month_label"] = _month_label(m) if isinstance(m, int) else ""
        # nice date display
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
    if not year or not month:
        return None
    return MONTH_THEMES.get((year, month))


# ----------------------------
# Blog routes (clean)
# ----------------------------
@app.route("/blog", endpoint="blog_index")
def blog_index():
    # read filters
    year = _coerce_int(request.args.get("year"), None)
    month = _coerce_int(request.args.get("month"), None)

    posts_all = list_blog_posts()  # use yours
    # ensure predictable sort (newest first)
    posts_all = sorted(
        posts_all,
        key=lambda p: (p.get("year") or 0, p.get("month") or 0, p.get("date") or ""),
        reverse=True
    )

    # years + months for dropdown
    years = sorted({p.get("year") for p in posts_all if isinstance(p.get("year"), int)}, reverse=True)
    if not years:
        years = [date.today().year]

    months = [{"value": i, "label": _month_label(i)} for i in range(1, 13)]

    # defaults (if no query params)
    selected_year = year if year else years[0]
    selected_month = month if month in range(1, 13) else ""

    posts = _filter_posts(posts_all, selected_year, month if month in range(1, 13) else None)
    posts = list_blog_posts()

    ctx = common_page_ctx(active="blog")
    ctx["posts"] = list_blog_posts()
    ctx.update({
        "posts": posts,
        "years": years,
        "months": months,
        "selected_year": selected_year,
        "selected_month": selected_month,
        "month_theme": _get_month_theme(selected_year, month if month in range(1, 13) else None),
        "SITE_URL": SITE_URL,  # used in template for Copy Link
    })
    return render_template("blog/index.html", **ctx)


@app.route("/blog/<slug>", endpoint="blog_post")
def blog_post(slug: str):
    slug = (slug or "").strip().lower()
    if not _slug_re.match(slug):
        abort(404)

    # template file must be templates/blog/<slug>.html
    rel_tpl = f"blog/{slug}.html"   # ✅ define it here (always)
    abs_path = BLOG_DIR / f"{slug}.html"
    if not abs_path.exists():
        abort(404)

    # Find metadata from registry, else fallback
    posts = list_blog_posts()
    posts = [p for p in posts if p["slug"] != "silence-is-not-absence"]
    meta = next((p for p in posts if (p.get("slug") == slug)), None)

    title = (meta.get("title") if meta else None) or _pretty_title_from_slug(slug)
    image = (meta.get("image") if meta else None) or _find_blog_image(slug)

    ctx = common_page_ctx(active="blog")
    ctx["post"] = {
        "slug": slug,
        "title": _pretty_title_from_slug(slug),
        "image": _find_blog_image(slug),
    }

    return render_template(rel_tpl, **ctx)

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
