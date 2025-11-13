# app.py — SoulStart Devotion (HTTP dev, upgraded study routes) — v13 Full
# -------------------------------------------------------------------------
# - HTTP dev (no forced HTTPS)
# - Auto-open browser on start
# - CSP relaxed in dev; strict in prod with per-request nonces
# - CSRF, rate limits, rotating logs
# - WhatsApp subprocess uses current interpreter
# - FIX: removed placeholder render_template lines in home()
# - FIX: clean /study routes (index + detail) + alias endpoint for templates
# - NEW: template auto-reload + no-cache headers in dev

import os
import sys
import json
import secrets
import logging
import subprocess
import webbrowser
from threading import Timer
from datetime import datetime, date, time
from pathlib import Path

from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]
from flask import (  # pyright: ignore[reportMissingImports]
    Flask, request, session, render_template, redirect,
    url_for, jsonify, send_from_directory, g,
)
from flask_wtf import CSRFProtect  # pyright: ignore[reportMissingImports]
from flask_limiter import Limiter  # pyright: ignore[reportMissingImports]
from flask_limiter.util import get_remote_address  # pyright: ignore[reportMissingImports]
from flask_talisman import Talisman  # pyright: ignore[reportMissingImports]
from logging.handlers import RotatingFileHandler

APP_VERSION = "v13"

# =============================================================================
# Env & paths
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "soulstart" / "static"
DEVOTIONS_ROOT = Path(os.environ.get("DEVOTIONS_ROOT", str(BASE_DIR / "devotions")))

load_dotenv(BASE_DIR / ".env")

ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
IS_PROD = ENV == "production"
IS_HTTPS = os.environ.get("FORCE_HTTPS", "0") in ("1", "true", "True")

JOIN_URL = os.environ.get("JOIN_URL", "https://chat.whatsapp.com/CdkN2V0h8vCDg2AP4saYfG")
SITE_THEME = os.environ.get("SITE_THEME", "Faith to Rise, Grace to Rest")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "set-a-strong-password")
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:5000")
PORT = int(os.environ.get("PORT", "5000"))
AUTO_OPEN = os.environ.get("AUTO_OPEN", "1") in ("1", "true", "True")
HOST = os.environ.get("HOST", "127.0.0.1")

# =============================================================================
# App init
# =============================================================================
app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(TEMPLATES_DIR))
app.secret_key = os.environ.get("SECRET_KEY", "dev-insecure")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config.update(
    SESSION_COOKIE_SECURE=IS_PROD or IS_HTTPS,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# CSRF + Rate limits
csrf = CSRFProtect(app)
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["200/day", "50/hour"])

# Logging
logs_dir = BASE_DIR / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
handler = RotatingFileHandler(logs_dir / "app.log", maxBytes=1_000_000, backupCount=5)
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s [%(pathname)s:%(lineno)d]"))
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
        "style-src": ["'self'"],
        "script-src": ["'self'"],
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

# =============================================================================
# Routes
# =============================================================================

@app.route("/")
def home():
    today = datetime.now().date()
    iso = today.strftime("%Y-%m-%d")
    m = normalize_entry(
        find_entry_for_date(load_json(month_folder_for(today) / filename_for(today, "morning")), iso) or {},
        "morning",
    )

    hero_bg = None
    hero_class = "hero-ambient-day"
    requested = m.get("bg_image") or "img/hero_day.jpg"
    if static_exists(requested):
        hero_bg = requested
        hero_class = ""

    return render_template(
        "home.html",
        title="SoulStart Devotion",
        today=today,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        hero_bg=hero_bg,
        hero_class=hero_class,
        hero_title=m.get("title"),
        page_bg_class="bg-image",
        page_bg_url=url_for("static", filename="img/hero_day.jpg"),
        active="home",
    )

@app.route("/today", endpoint="today")
def today_view():
    d = datetime.now().date()
    iso = d.strftime("%Y-%m-%d")
    m = normalize_entry(
        find_entry_for_date(load_json(month_folder_for(d) / filename_for(d, "morning")), iso) or {}, "morning"
    )
    n = normalize_entry(
        find_entry_for_date(load_json(month_folder_for(d) / filename_for(d, "night")), iso) or {}, "night"
    )
    hero_bg = None
    hero_class = "hero-ambient-day"
    requested = m.get("bg_image") or "img/hero_day.jpg"
    if static_exists(requested):
        hero_bg = requested
        hero_class = ""
    return render_template(
        "today.html",
        today=d,
        morning=m if (m.get("title") or m.get("verse_ref")) else None,
        night=n if (n.get("title") or n.get("verse_ref")) else None,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        hero_bg=hero_bg,
        hero_class=hero_class,
        page_bg_class="",
        active="today",
    )

# ---------------- Study (v13) ----------------
# Provide BOTH endpoint names so existing templates using either work.
# ---------------- Study (v13 with XML detection — matches static/study/series/*.xml) ----------------
# -------- Study (super simple: open series#.html) --------
# -------- Study (super simple) --------
@app.route("/study", endpoint="study")
@app.route("/studies", endpoint="study_index")  # <-- add this line
def study_index():
    templates_root = Path(app.template_folder or "templates")
    study_dir = templates_root / "study"
    items = []
    for p in sorted(study_dir.glob("series*.html")):
        key = p.stem
        title = key.replace("series", "Series ")
        items.append({"key": key, "title": title})
    return render_template("study/index.html",
                           title="Study Series",
                           series=items,
                           theme=SITE_THEME,
                           active="study")


@app.route("/study/<series_name>", endpoint="study_detail")
def study_detail(series_name: str):
    # only allow series1..seriesN
    if not series_name.startswith("series"):
        return ("Study not found", 404)
    template_rel = Path("study") / f"{series_name}.html"
    template_abs = Path(app.template_folder or "templates") / template_rel
    if not template_abs.exists():
        return ("Study not found", 404)
    # render that exact file
    return render_template(str(template_rel).replace("\\", "/"),
                        title=series_name.replace("series", "Series "),
                        theme=SITE_THEME,
                        active="study")


# ---------------- Verses ----------------
@app.route("/verses")
def verses():
    today = datetime.now().date()
    data = load_json(DEVOTIONS_ROOT / "verses.json") or {}
    raw_cards = data.get("cards") or []
    cards = []
    for c in raw_cards:
        fname = (c.get("file") or "").strip()
        src = _find_verse_image_url(fname)
        if not src:
            continue
        cards.append({
            "src": src,
            "ref": c.get("ref") or "",
            "caption": c.get("caption") or "",
            "alt": c.get("ref") or "Scripture card",
        })
    return render_template(
        "verses.html",
        today=today,
        theme=SITE_THEME,
        join_url=JOIN_URL,
        theme_title=data.get("theme") or SITE_THEME,
        cards=cards,
        page_bg_class="bg-video",
        page_bg_video=url_for("static", filename="img/videos/seaside 1.mp4"),
        page_bg_poster=url_for("static", filename="img/hero_day.jpg"),
        active="verses",
    )

def _hero_for_now():
    # Optional helper if you later want time-based hero swap
    day = time(6, 0)
    night = time(16, 30)
    now_t = datetime.now().time()
    use_night = (now_t >= night) or (now_t < day)
    return ("img/hero_night.jpg", "hero-ambient-night") if use_night else ("img/hero_day.jpg", "hero-ambient-day")

# ---- Prayer (rate-limited)
@app.route("/prayer", methods=["GET", "POST"])
@limiter.limit("5/minute; 20/hour")
def prayer():
    today = datetime.now().date()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        text = (request.form.get("request") or "").strip()
        if text:
            req_file = DEVOTIONS_ROOT / "prayer_requests.json"
            try:
                existing = load_json(req_file) or []
                if not isinstance(existing, list):
                    existing = []
                existing.append({
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "name": name,
                    "contact": contact,
                    "request": text,
                })
                req_file.parent.mkdir(parents=True, exist_ok=True)
                with open(req_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
                return render_template("prayer.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, ok=True, active="prayer")
            except Exception:
                return render_template("prayer.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, ok=False, active="prayer")
    return render_template("prayer.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, active="prayer")

# ---- Feedback
FEEDBACK_FILE = DEVOTIONS_ROOT / "feedback.json"

@app.route("/feedback", methods=["GET", "POST"])
@limiter.limit("5/minute; 50/day")
def feedback_view():
    today = datetime.now().date()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        message = (request.form.get("message") or "").strip()
        if message:
            try:
                existing = load_json(FEEDBACK_FILE) or []
                if not isinstance(existing, list):
                    existing = []
                existing.append({
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "name": name,
                    "contact": contact,
                    "message": message,
                })
                FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
                FEEDBACK_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
                return render_template("feedback.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, ok=True, active="feedback")
            except Exception:
                return render_template("feedback.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, ok=False, active="feedback")
    return render_template("feedback.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, active="feedback")

@app.route("/admin/feedback")
def admin_feedback():
    if not is_authed():
        return redirect(url_for("login"))
    items = load_json(FEEDBACK_FILE) or []
    if not isinstance(items, list):
        items = []
    items = sorted(items, key=lambda r: r.get("ts", ""), reverse=True)
    return render_template("admin_feedback.html", items=items, theme=SITE_THEME)

# ---- Volunteer
@app.route("/volunteer", methods=["GET", "POST"])
@limiter.limit("5/minute; 50/day")
def volunteer():
    today = datetime.now().date()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        skills = (request.form.get("skills") or "").strip()
        availability = (request.form.get("availability") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        if name and (contact or skills):
            vf = DEVOTIONS_ROOT / "volunteers.json"
            try:
                current = load_json(vf) or []
                if not isinstance(current, list):
                    current = []
                current.append(
                    {
                        "ts": datetime.now().isoformat(timespec="seconds"),
                        "name": name,
                        "contact": contact,
                        "skills": skills,
                        "availability": availability,
                        "notes": notes,
                    }
                )
                vf.parent.mkdir(parents=True, exist_ok=True)
                vf.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
                return render_template("volunteer.html", ok=True, today=today, theme=SITE_THEME, join_url=JOIN_URL)
            except Exception:
                return render_template("volunteer.html", ok=False, today=today, theme=SITE_THEME, join_url=JOIN_URL)
        return render_template(
            "volunteer.html",
            ok=None,
            err="Please include your name and at least contact or skills.",
            today=today,
            theme=SITE_THEME,
            join_url=JOIN_URL,
        )
    return render_template("volunteer.html", today=today, theme=SITE_THEME, join_url=JOIN_URL)

@app.route("/admin/volunteers")
def admin_volunteers():
    if not is_authed():
        return redirect(url_for("login"))
    vf = DEVOTIONS_ROOT / "volunteers.json"
    rows = load_json(vf) or []
    if not isinstance(rows, list):
        rows = []
    try:
        rows.sort(key=lambda r: r.get("ts", ""), reverse=True)
    except Exception:
        pass
    return render_template("admin_volunteers.html", rows=rows, today=datetime.now().time(), theme=SITE_THEME, join_url=JOIN_URL)

# ---- Auth + Admin
@app.route("/login", methods=["GET", "POST"])
def login():
    today = datetime.now().date()
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASS:
            session["authed"] = True
            return redirect(url_for("admin"))
        error = "Incorrect password."
    return render_template("login.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, error=error, active="admin")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin")
def admin():
    if not is_authed():
        return redirect(url_for("login"))
    today = datetime.now().date()
    return render_template(
        "admin.html",
        today=today,
        today_str=today.strftime("%Y-%m-%d"),
        theme=SITE_THEME,
        join_url=JOIN_URL,
        active="admin",
    )

# ---- Admin: WhatsApp auto-sender
@app.post("/admin/whatsapp/send")
def admin_whatsapp_send():
    if not is_authed():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    mode = (request.form.get("mode") or "both").strip()  # both|morning|night|verses
    date_str = (request.form.get("date") or "").strip()

    candidate_paths = [
        BASE_DIR / "scripts" / "whatsapp_auto.py",
        BASE_DIR / "whatsapp_auto.py",
    ]
    script_path = next((p for p in candidate_paths if p.exists()), None)
    if not script_path:
        return (
            jsonify({
                "ok": False,
                "error": "whatsapp_auto.py not found",
                "looked_in": [str(p) for p in candidate_paths],
            }),
            500,
        )

    targets = {
        "both": ["morning", "night"],
        "morning": ["morning"],
        "night": ["night"],
        "verses": ["verses"],
    }.get(mode, ["morning", "night"])

    results, all_ok = [], True
    for m in targets:
        args = [sys.executable, str(script_path), "--mode", m]
        if date_str:
            args += ["--date", date_str]
        try:
            out = subprocess.run(args, cwd=str(BASE_DIR), capture_output=True, text=True, shell=False)
            ok = out.returncode == 0
            all_ok = all_ok and ok
            results.append(
                {
                    "mode": m,
                    "ok": ok,
                    "args": args,
                    "stdout": (out.stdout or "")[-4000:],
                    "stderr": (out.stderr or "")[-4000:],
                    "returncode": out.returncode,
                }
            )
        except Exception as e:
            all_ok = False
            results.append({"mode": m, "ok": False, "error": str(e)})

    return jsonify({"ok": all_ok, "results": results})

# ---- Donation / Thanks
@app.route("/donation")
def donation():
    paypal = os.environ.get("PAYPAL_LINK", "")
    ok = request.args.get("ok") == "1"
    return render_template("donation.html", theme=SITE_THEME, today=datetime.now().time(), paypal_link=paypal, ok=ok)

@app.route("/donation/thanks")
def donation_thanks():
    back_url = url_for("donation", ok=1)
    nxt = request.args.get("next")
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        back_url = nxt
    return render_template("donation_thanks.html", theme=SITE_THEME, today=datetime.now().time(), back_url=back_url)

# ---- About / Join
@app.route("/about")
def about():
    return render_template("about.html", today=datetime.now().date(), theme=SITE_THEME, join_url=JOIN_URL, active="about")

@app.route("/join")
def join():
    return redirect(JOIN_URL, code=302)

# ---- Favicon
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )

# ---- Errors
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html", theme=SITE_THEME), 404

@app.errorhandler(500)
def server_error(e):
    app.logger.exception("Unhandled error: %s", e)
    return render_template("500.html", theme=SITE_THEME), 500

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
