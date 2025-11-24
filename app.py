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

DEVOTIONS_ROOT = Path(
    os.environ.get("DEVOTIONS_ROOT", str(BASE_DIR / "devotions"))
)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

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
ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD", "") or "").strip()
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

def is_authed() -> bool:
    return session.get("authed") is True

@app.context_processor
def _globals():
    return {"is_authed": is_authed}

def authed() -> bool:
    return bool(session.get("is_authed", False))

@app.context_processor
def inject_globals():
    """Values available in all templates."""
    return {
        "theme": SITE_THEME,
        "join_url": JOIN_URL,
        "today": date.today(),
        "is_authed": authed(),
    }

def nav_args(active: str, **extra):
    """Common args passed into render_template for active tab highlighting."""
    base = dict(active=active)
    base.update(extra)
    return base

@app.context_processor
def inject_auth_flag():
    return {"is_authed": is_authed()}


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
@app.route("/today", endpoint="today")
def today_view():
    today = date.today()
    today_iso = today.isoformat()        # "2025-11-20"
    month_full = today.strftime("%B")    # "November"
    month_abbr = today.strftime("%b")    # "Nov"

    # 🔹 SAFE FALLBACKS (never show an empty card)
    morning = {
        "title": "Morning Mercies",
        "verse_ref": "Lamentations 3:22–23",
        "verse_text": "His mercies are new every morning; great is Your faithfulness.",
        "encouragement_intro": "",
        "point1": "",
        "point2": "",
        "point3": "",
        "closing": "",
        "prayer": "",
        "body": "His mercies are new every morning; great is Your faithfulness.",
    }

    night = {
        "title": "Quiet Rest",
        "verse_ref": "Psalm 4:8",
        "verse_text": "In peace I will both lie down and sleep, for You alone make me dwell in safety.",
        "encouragement_intro": "",
        "point1": "",
        "point2": "",
        "point3": "",
        "closing": "",
        "prayer": "",
        "body": "In peace I will both lie down and sleep, for You alone make me dwell in safety.",
    }

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


# ---------- Verses ----------
def _safe_static(filename: str) -> str | None:
    p = (Path(app.static_folder) / filename)
    return url_for("static", filename=filename) if p.exists() else None

@app.route("/verses")
def verses():
    today = datetime.now().date()
    raw = [
        ("Firelight.jpg","Isaiah 60:1 (NLV)","Firelight"),
        ("Stillness.jpg","Psalm 46:10 (NLV)","Stillness"),
        ("Restoration.jpg","Joel 2:25 (NLV)","Restoration"),
        ("Delight.jpg","Isaiah 58:13–14","Delight"),
        ("Presence.jpg","Exodus 33:14","Presence"),
        ("Refuge.jpg","Psalm 62:8","Refuge"),
        ("Overflow.jpg","Psalm 23:5","Overflow"),
    ]
    cards = []
    for fname, ref, title in raw:
        src = _safe_static(f"img/verses/{fname}")
        cards.append({"src": src, "ref": ref, "caption": title, "alt": ref})
    return render_template("verses.html",
        today=today, theme=SITE_THEME, join_url=JOIN_URL,
        cards=cards, page_bg_class="", active="verses")


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
PAYPAL_LINK = os.environ.get("PAYPAL_LINK", "")

@app.route("/donation")
def donation():
    return render_template(
        "donation.html",
        theme=SITE_THEME,
        join_url=JOIN_URL,
        paypal_link=PAYPAL_LINK,
        active="donation",
    )

# ---------- Feedback ----------
@app.route("/feedback", methods=["GET", "POST"])
def feedback_view():
    if request.method == "POST":
        flash("📝 Feedback submitted. Thank you!", "success")
        return redirect(url_for("feedback_view"))
    return render_template("feedback.html", theme=SITE_THEME, join_url=JOIN_URL, active="feedback")

# ---------- Study (Hub + 4 series) ----------
# Expose BOTH endpoints so old links won’t break
@app.route("/study", endpoint="study")
@app.route("/studies", endpoint="study_index")
def study_index():
    templates_root = Path(app.template_folder or "templates")
    study_dir = templates_root / "study"
    items = []
    for p in sorted(study_dir.glob("series*.html")):
        key = p.stem                 # e.g., series1
        title = key.replace("series", "Series ")
        items.append({"key": key, "title": title})
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
    if not series_name.startswith("series"):
        abort(404)
    rel = Path("study") / f"{series_name}.html"
    abs_path = Path(app.template_folder or "templates") / rel
    if not abs_path.exists():
        abort(404)
    return render_template(
        str(rel).replace("\\", "/"),
        title=series_name.replace("series", "Series "),
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
        print("=== ADMIN LOGIN DEBUG ===")
        print("Has ADMIN_EMAIL:", bool(ADMIN_EMAIL))
        print("Has ADMIN_PASSWORD:", bool(ADMIN_PASSWORD))
        print("Submitted email:", repr(email))
        print("Env email:", repr(ADMIN_EMAIL))

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
def admin_whatsapp_send():
    """Handle Admin WhatsApp send form and trigger the automation script."""
    # ----- 1. Read form inputs -----
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

