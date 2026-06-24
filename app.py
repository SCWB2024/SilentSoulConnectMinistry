# app.py — SoulStart Devotion Gateway Core
# Cleaned for old SSCM site: gateway homepage + devotion engine + admin WhatsApp tools

from __future__ import annotations

import io
import json
import logging
import os
import random
import re
import secrets
import zipfile
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import quote

import smtplib
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, UserMixin, login_user, logout_user
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from flask_talisman import Talisman
except Exception:
    Talisman = None


# =========================
# 1) ENV / PATHS
# =========================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()

ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
IS_PROD = ENV == "production"
IS_HTTPS = os.getenv("FORCE_HTTPS", "0").lower() in ("1", "true", "yes")

APP_VERSION = "gateway-v1"
SITE_THEME = os.getenv("SITE_THEME", "Faith to Rise, Grace to Rest")

NEW_SSCM_URL = os.getenv("NEW_SSCM_URL", "https://new-sscm-2026.onrender.com/")
JOIN_URL = os.getenv("JOIN_URL", "https://chat.whatsapp.com/CdkN2V0h8vCDg2AP4saYfG")
WHATSAPP_GROUP_LINK = os.getenv("WHATSAPP_GROUP_LINK", JOIN_URL)
SITE_JOIN_URL = WHATSAPP_GROUP_LINK

SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:5000")
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "0.0.0.0" if IS_PROD else "127.0.0.1")
AUTO_OPEN = (not IS_PROD) and os.getenv("AUTO_OPEN", "0").lower() in ("1", "true", "yes")

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "soulstart" / "static"

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DEVOTIONS_DIR = DATA_DIR / "devotions"
DEVOTIONS_DIR.mkdir(exist_ok=True)

PRAYER_REQUESTS_FILE = DATA_DIR / "prayer_requests.json"

HERO_DAY_BG = "img/hero_day.jpg"
HERO_NIGHT_BG = "img/hero_night.jpg"


# =========================
# 2) LOGGING
# =========================
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("soulstart")
logger.setLevel(logging.INFO)

fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

if not logger.handlers:
    fh = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

if not IS_PROD:
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

logger.info("SoulStart Gateway starting...")


# =========================
# 3) FLASK APP
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

csrf = CSRFProtect(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["5000 per day", "500 per hour"],
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

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
# 4) ADMIN AUTH
# =========================
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL", "sscministry@outlook.com") or "").strip().lower()
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD", "") or "").strip()


class AdminUser(UserMixin):
    def __init__(self, user_id: str = "admin"):
        self.id = user_id


@login_manager.user_loader
def load_user(user_id: str):
    return AdminUser() if user_id == "admin" else None


def verify_admin_credentials(email: str, password: str) -> bool:
    if not ADMIN_PASSWORD:
        return False
    return (
        email.strip().lower() == ADMIN_EMAIL
        and secrets.compare_digest(password.strip(), ADMIN_PASSWORD)
    )


def is_authed() -> bool:
    return bool(session.get("authed"))


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_authed():
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


# =========================
# 5) SHARED HELPERS
# =========================
def common_page_ctx(active: str):
    return dict(
        today=date.today(),
        theme=SITE_THEME,
        join_url=SITE_JOIN_URL,
        active=active,
        page_bg_class="bg-image",
        page_bg_url=url_for("static", filename=HERO_DAY_BG),
        new_sscm_url=NEW_SSCM_URL,
    )


@app.context_processor
def inject_globals():
    return {
        "SITE_JOIN_URL": SITE_JOIN_URL,
        "SITE_THEME": SITE_THEME,
        "APP_VERSION": APP_VERSION,
        "JOIN_URL": JOIN_URL,
        "NEW_SSCM_URL": NEW_SSCM_URL,
        "SITE_URL": request.url_root.rstrip("/"),
        "now": datetime.now(),
    }


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


def read_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "[]")
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("Could not read %s: %s", path, e)
        return []


def save_json_list(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def append_json_list(path: Path, item: dict) -> None:
    data = read_json_list(path)
    data.append(item)
    save_json_list(path, data)


def _safe_static(filename: str) -> str | None:
    filename = (filename or "").lstrip("/\\")
    path = Path(app.static_folder) / filename
    return url_for("static", filename=filename) if path.exists() else None


def _safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = name.replace("\\", "/").split("/")[-1]
    return re.sub(r"[^A-Za-z0-9._-]+", "", name)


def _truncate(s: str, n: int) -> str:
    return (s or "").strip()[:n]


# =========================
# 6) DEVOTION ENGINE
# =========================
AMEN_LINE = os.getenv("PRAYER_CLOSING", "In Jesus’ name, Amen.")


def ensure_amen(text: str) -> str:
    t = (text or "").rstrip()
    if not t:
        return t
    low = t.lower()
    if "in jesus" in low and "amen" in low:
        return t
    return t + "\n\n" + AMEN_LINE


def _devotions_file_for_year(year: int) -> Path:
    return DEVOTIONS_DIR / f"devotions_{year}.json"


def load_devotions_for_year(year: int) -> dict[str, dict]:
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

    has_slots = isinstance(day_block.get("morning"), dict) or isinstance(day_block.get("night"), dict)
    if has_slots:
        theme = str(day_block.get("theme") or "").strip()
        slot_block = day_block.get(slot) or {}
    else:
        theme = str(day_block.get("theme") or day_block.get("Theme") or day_block.get("title") or "").strip()
        slot_block = day_block

    if not isinstance(slot_block, dict) or not slot_block:
        return placeholder_devotion(day_key, slot)

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

    body_text = "\n".join([l for l in lines if l]).strip() or verse_text

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


def build_whatsapp_text(entry: dict | None, mode: str, day: date) -> str:
    if not entry:
        return ""

    mode = (mode or "morning").lower().strip()
    date_str = day.strftime("%A, %B %d, %Y")
    icon = (entry.get("icon") or "").strip() or ("🌅" if mode == "morning" else "🌙")

    heading = f"{icon} SoulStart {'Sunrise' if mode == 'morning' else 'Sunset'} – {date_str}"
    lines: list[str] = [heading, ""]

    theme = (entry.get("theme") or "").strip()
    verse_ref = (entry.get("verse_ref") or "").strip()
    verse_text = (entry.get("verse_text") or "").strip()

    if theme:
        lines.append(f"Theme: {theme}")

    if verse_ref:
        lines.append(f"📖 Scripture: {verse_ref} — “{verse_text}”" if verse_text else f"📖 Scripture: {verse_ref}")

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
        lines.extend(["", f"🙏 Prayer: {ensure_amen(prayer)}"])
    else:
        lines.extend(["", AMEN_LINE])

    lines.extend(["", f"🔗 Join us: {SITE_JOIN_URL}"])

    return "\n".join([l for l in lines if l]).strip()


def build_share_payload(date_str: str, mode: str) -> dict:
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        target_date = date.today()

    mode = (mode or "morning").lower()
    if mode not in ("morning", "night", "both"):
        mode = "morning"

    if mode in ("morning", "night"):
        entry = load_devotion_for(target_date, mode)
        text = build_whatsapp_text(entry, mode, target_date)
        return {"text": text, f"text_{mode}": text}

    entry_m = load_devotion_for(target_date, "morning")
    entry_n = load_devotion_for(target_date, "night")
    text_m = build_whatsapp_text(entry_m, "morning", target_date)
    text_n = build_whatsapp_text(entry_n, "night", target_date)
    return {"text": text_m, "text_morning": text_m, "text_night": text_n}

# =========================
# 8) PRAYER REQUEST HELPER FOR ADMIN WHATSAPP
# =========================
PRAYER_TOPICS = [
    {"value": "peace", "label": "🕊️ Peace / Anxiety"},
    {"value": "relationships", "label": "💞 Relationships / Family"},
    {"value": "grief", "label": "💔 Grief / Loss"},
    {"value": "healing", "label": "🩺 Sickness / Healing"},
    {"value": "provision", "label": "💼 Provision / Finances"},
    {"value": "direction", "label": "🧭 Direction / Decisions"},
    {"value": "faith", "label": "🙏 Faith / Spiritual Strength"},
    {"value": "community", "label": "🧑‍🤝‍🧑 Community / Others"},
    {"value": "other", "label": "✍️ Other"},
]


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


def send_prayer_email(record: dict) -> bool:
    to_addr = (os.getenv("ALERT_EMAIL_TO") or "").strip()
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int(os.getenv("SMTP_PORT", "587") or "587")
    user = (os.getenv("SMTP_USER") or "").strip()
    pwd = (os.getenv("SMTP_PASS") or "").strip()

    if not all([to_addr, host, user, pwd]):
        return False

    msg = EmailMessage()
    msg["Subject"] = f"New Prayer Request ({record.get('topic', 'General')})"
    msg["From"] = (os.getenv("ALERT_EMAIL_FROM") or user).strip()
    msg["To"] = to_addr
    msg.set_content(
        f"Time: {record.get('ts')}\n"
        f"Name: {record.get('name') or 'Anonymous'}\n"
        f"Contact: {record.get('contact') or '-'}\n"
        f"Topic(s): {record.get('topic') or 'General'}\n\n"
        f"Request:\n{record.get('request') or '[No written request]'}\n"
    )

    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(user, pwd)
        smtp.send_message(msg)

    return True


# =========================
# 9) PUBLIC ROUTES
# =========================
@app.route("/", endpoint="home")
def home():
    ctx = common_page_ctx(active="home")
    return render_template("index.html", **ctx)


@app.route("/today", endpoint="today")
@limiter.limit("60 per minute")
def today_view():
    mode = (request.args.get("mode") or "morning").strip().lower()
    mode = mode if mode in ("morning", "night") else "morning"

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
        "yday_url": url_for("today", date=(target_date - timedelta(days=1)).isoformat(), mode=mode),
        "yday_label": "← Yesterday’s devotion",
    })

    return render_template("devotion.html", **ctx)

@app.route("/prayer", endpoint="prayer")
def prayer_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/devotion-study", endpoint="devotion_study")
def devotion_study_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/path", endpoint="path")
def path_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/anchor", endpoint="anchor")
def anchor_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/declarations", endpoint="declarations")
def declarations_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/about", endpoint="about")
def about_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/study", endpoint="study_redirect")
def study_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/studies", endpoint="study_index")
def studies_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/donation", endpoint="donation")
def donation_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/volunteer", endpoint="volunteer")
def volunteer_redirect():
    return redirect(NEW_SSCM_URL, code=302)


@app.route("/blog", endpoint="blog_index")
def blog_redirect():
    return redirect(NEW_SSCM_URL, code=302)

# =========================
# 10) AUTH ROUTES
# =========================
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


# =========================
# 11) ADMIN ROUTES
# =========================
@app.route("/admin", endpoint="admin")
@require_auth
def admin_dashboard():
    ctx = common_page_ctx(active="admin")
    ctx["today_str"] = date.today().isoformat()
    return render_template("admin/admin.html", **ctx)

@app.route("/admin/requests", endpoint="admin_requests")
@require_auth
def admin_requests():
    items = list(reversed(read_json_list(PRAYER_REQUESTS_FILE)))
    ctx = common_page_ctx(active="admin")
    return render_template("admin/admin_requests.html", items=items, **ctx)


@app.route("/admin/requests/delete/<int:index>", methods=["POST"], endpoint="admin_request_delete")
@require_auth
def admin_request_delete(index: int):
    items = read_json_list(PRAYER_REQUESTS_FILE)
    real_index = len(items) - 1 - index

    if 0 <= real_index < len(items):
        removed = items.pop(real_index)
        save_json_list(PRAYER_REQUESTS_FILE, items)
        flash(f"Prayer from {removed.get('name', 'Anonymous')} archived.", "success")
    else:
        flash("Request not found.", "error")

    return redirect(url_for("admin_requests"))


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
        if mode not in ("morning", "night", "both"):
            mode = "morning"

        selected_topic = (request.form.get("topic") or "").strip()
        devotion_payload = build_share_payload(date_str=date_str, mode=mode)

        picked = pick_random_request(selected_topic) if selected_topic else None
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

        for k in ("text", "text_morning", "text_night"):
            if devotion_payload.get(k):
                devotion_payload[k] += add_on

        result = devotion_payload

    ctx.update({"result": result, "selected_topic": selected_topic})
    return render_template("admin/admin_whatsapp.html", **ctx)


@app.route("/admin/whatsapp/send", methods=["POST"], endpoint="admin_whatsapp_send")
@require_auth
def admin_whatsapp_send():
    today_ = date.today()
    raw_mode = (request.form.get("mode") or "").strip().lower()

    mode_map = {
        "morning": "morning", "m": "morning", "am": "morning",
        "night": "night", "n": "night", "pm": "night",
        "both": "both", "b": "both",
        "morning & night": "both", "morning-night": "both", "morning and night": "both",
    }
    mode = mode_map.get(raw_mode, "morning")

    raw_date = (request.form.get("date") or today_.isoformat()).strip()
    try:
        target_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except Exception:
        target_date = today_
        raw_date = today_.isoformat()

    def make_share_urls(message: str) -> dict[str, str]:
        enc = quote(message)
        return {
            "share_web": f"https://web.whatsapp.com/send?text={enc}",
            "share_api": f"https://api.whatsapp.com/send?text={enc}",
            "share_wa": f"https://wa.me/?text={enc}",
        }

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


# =========================
# 12) RUN
# =========================
def _open_browser():
    try:
        import webbrowser
        webbrowser.open(f"http://{HOST}:{PORT}/")
    except Exception:
        pass


if __name__ == "__main__":
    from threading import Timer

    logger.info("SoulStart Gateway ready... %s", APP_VERSION)
    if AUTO_OPEN:
        Timer(1.0, _open_browser).start()

    app.run(host=HOST, port=PORT, debug=not IS_PROD)
