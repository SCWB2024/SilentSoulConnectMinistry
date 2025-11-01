# app.py — SoulStart Devotion (clean HTTP dev build)
# -------------------------------------------------
# - Runs on plain HTTP for local dev (no forced HTTPS)
# - Auto-opens default browser on startup
# - CSP with per-request nonce (strict in prod, relaxed in dev)
# - CSRF, rate limits, rotating logs
# - Consolidated routes for home/today/study/verses/prayer/admin/etc.

import os
import sys
import json
import secrets
import logging
import subprocess
import webbrowser
from threading import Timer
from datetime import datetime, date
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask, request, session, render_template, redirect,
    url_for, jsonify, send_from_directory, g
)
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from logging.handlers import RotatingFileHandler

# =============================================================================
# Env & paths
# =============================================================================
BASE_DIR       = Path(__file__).resolve().parent
TEMPLATES_DIR  = BASE_DIR / "templates"
STATIC_DIR     = BASE_DIR / "static"
DEVOTIONS_ROOT = Path(os.environ.get("DEVOTIONS_ROOT", str(BASE_DIR / "devotions")))

load_dotenv(BASE_DIR / ".env")

APP_ENV  = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
IS_PROD  = APP_ENV == "production"
IS_HTTPS = os.environ.get("FORCE_HTTPS", "0") in ("1", "true", "True")

JOIN_URL     = os.environ.get("JOIN_URL", "https://chat.whatsapp.com/CdkN2V0h8vCDg2AP4saYfG")
SITE_THEME   = os.environ.get("SITE_THEME", "Faith to Rise, Grace to Rest")
ADMIN_PASS   = os.environ.get("ADMIN_PASSWORD", "set-a-strong-password")
SITE_URL     = os.environ.get("SITE_URL", "http://127.0.0.1:5000")
PORT         = int(os.environ.get("PORT", "5000"))
AUTO_OPEN    = os.environ.get("AUTO_OPEN", "1") in ("1", "true", "True")
HOST         = os.environ.get("HOST", "127.0.0.1")  # keep localhost for http dev

# =============================================================================
# App init (single instance)
# =============================================================================
app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(TEMPLATES_DIR))
app.secret_key = os.environ.get("SECRET_KEY", "dev-insecure")

# Cookies
app.config.update(
    SESSION_COOKIE_SECURE = IS_PROD or IS_HTTPS,
    SESSION_COOKIE_HTTPONLY = True,
    SESSION_COOKIE_SAMESITE = "Lax",
)

# CSRF
csrf = CSRFProtect(app)

# Rate limiting
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["200/day", "50/hour"])

# Logging
logs_dir = BASE_DIR / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
handler = RotatingFileHandler(logs_dir / "app.log", maxBytes=1_000_000, backupCount=5)
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s [%(pathname)s:%(lineno)d]"))
app.logger.addHandler(handler)
app.logger.info("App startup")

# =============================================================================
# CSP (nonce) + HTTPS policy
# =============================================================================
def _gen_nonce(length: int = 16) -> str:
    return secrets.token_urlsafe(length)

@app.before_request
def _set_nonce():
    g.csp_nonce = _gen_nonce() if IS_PROD else ""  # strict only in prod

@app.context_processor
def _inject_nonce():
    # In templates: <script nonce="{{ csp_nonce() }}"> ... </script>
    return {"csp_nonce": lambda: g.get("csp_nonce", "")}

if IS_PROD:
    # Strict CSP (nonced)
    csp = {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "https:"],
        "style-src": ["'self'"],     # nonce added per response
        "script-src": ["'self'"],    # nonce added per response
        "media-src": ["'self'", "data:", "blob:"],
        "font-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'self'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    }
    talisman = Talisman(app,
        content_security_policy=csp,
        force_https=True if (IS_PROD or IS_HTTPS) else False,
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        frame_options="SAMEORIGIN",
        referrer_policy="strict-origin-when-cross-origin",
    )

    @app.after_request
    def _apply_nonce(resp):
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
    # Dev: relaxed CSP, no HTTPS enforcement (prevents local SSL redirect)
    csp = {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "blob:", "https:"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "script-src": ["'self'", "'unsafe-inline'"],
        "media-src": ["'self'", "data:", "blob:"],
        "font-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'self'"],
    }
    talisman = Talisman(
        app,
        content_security_policy=csp,
        force_https=False,  # <— key for HTTP local dev
        strict_transport_security=False,
        frame_options="SAMEORIGIN",
        referrer_policy="no-referrer-when-downgrade",
    )

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
        "%Y-%m-%d","%d-%m-%Y","%m-%d-%Y","%Y/%m/%d","%m/%d/%Y","%d/%m/%Y",
        "%b %d, %Y","%B %d, %Y","%d %b %Y","%d %B %Y"
    ]
    for fmt in fmts:
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception: pass
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
            if not isinstance(item, dict): continue
            if "date" in item and normalize_date_str(str(item.get("date", ""))) == iso:
                return item
            for key in ("day", "Day", "DATE", "Date"):
                if key in item and normalize_date_str(str(item.get(key, ""))) == iso:
                    return item
    return None

def normalize_entry(entry: dict, default_mode: str) -> dict:
    if not entry: return {}
    out: dict = {}
    out["title"]     = entry.get("title") or entry.get("Theme") or entry.get("theme")
    out["verse_ref"] = entry.get("verse_ref") or entry.get("verseRef") or entry.get("VerseRef")
    out["verse_text"]= entry.get("verse_text") or entry.get("verseText") or entry.get("VerseText")
    out["points"]    = [p for p in [entry.get("point1"), entry.get("point2"), entry.get("point3")] if p]
    out["closing"]   = entry.get("closing")
    out["prayer"]    = entry.get("prayer")
    out["bg_image"]  = entry.get("bg_image")
    scripture        = entry.get("scripture") or entry.get("Scripture") or entry.get("verse")
    reflection       = entry.get("reflection") or entry.get("note") or entry.get("thought")

    if not out["title"] and entry.get("theme"):       out["title"]   = entry.get("theme")
    if not out["verse_ref"] and scripture:            out["verse_ref"] = scripture
    if not out["closing"] and reflection:             out["closing"] = reflection
    if not out["prayer"]:
        out["prayer"] = (
            entry.get("morning_prayer") or entry.get("morningPrayer")
            or entry.get("night_prayer") or entry.get("nightPrayer")
        )
    out["join_text"] = entry.get("join_text")
    out["join_url"]  = entry.get("join_url")
    t = (entry.get("type") or "").lower()
    out["type"] = "morning" if t in ("sunrise", "morning") else ("night" if t in ("sunset", "night") else default_mode)
    return out

def _find_verse_image_url(fname: str) -> str | None:
    if not fname: return None
    bases = [STATIC_DIR / "img" / "verses", STATIC_DIR / "images", STATIC_DIR / "img"]
    for base in bases:
        if not base.exists(): continue
        p = base / fname
        if p.exists():
            rel = p.relative_to(STATIC_DIR)
            return url_for("static", filename=str(rel).replace("\\", "/"))
        for entry in base.iterdir():
            if entry.is_file() and entry.name.lower() == fname.lower():
                rel = entry.relative_to(STATIC_DIR)
                return url_for("static", filename=str(rel).replace("\\", "/"))
    return None

def is_authed() -> bool:
    return session.get("authed") is True

@app.context_processor
def _globals():
    return {"is_authed": is_authed()}

# =============================================================================
# Routes
# =============================================================================

@app.route("/")
def home():
    today = datetime.now().date()
    iso   = today.strftime("%Y-%m-%d")
    m     = normalize_entry(
                find_entry_for_date(load_json(month_folder_for(today) / filename_for(today, "morning")), iso) or {},
                "morning"
            )
    hero_bg = None
    hero_class = "hero-ambient-day"
    requested = m.get("bg_image") or "img/hero_day.jpg"
    if static_exists(requested):
        hero_bg = requested
        hero_class = ""
    return render_template(
        "home.html",
        today=today, theme=SITE_THEME, join_url=JOIN_URL,
        hero_bg=hero_bg, hero_class=hero_class, hero_title=m.get("title"),
        page_bg_class="bg-image", page_bg_url=url_for("static", filename="img/hero_day.jpg"),
        active="home",
    )

@app.route("/today", endpoint="today")
def today_view():
    d   = datetime.now().date()
    iso = d.strftime("%Y-%m-%d")
    m   = normalize_entry(find_entry_for_date(load_json(month_folder_for(d) / filename_for(d, "morning")), iso) or {}, "morning")
    n   = normalize_entry(find_entry_for_date(load_json(month_folder_for(d) / filename_for(d, "night")), iso) or {}, "night")
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
        theme=SITE_THEME, join_url=JOIN_URL,
        hero_bg=hero_bg, hero_class=hero_class,
        page_bg_class="", active="today",
    )

# legacy alias (if any older template calls it)
app.add_url_rule("/today", endpoint="today", view_func=today_view)

@app.route("/study")
def study():
    today = datetime.now().date()
    studies_path = DEVOTIONS_ROOT / "studies.json"
    studies = load_json(studies_path) or []
    if not isinstance(studies, list): studies = []
    try:
        studies.sort(key=lambda s: s.get("date") or "", reverse=True)
    except Exception:
        pass
    week1_cards = load_json(DEVOTIONS_ROOT / "week1_cards.json") or []
    if not isinstance(week1_cards, list): week1_cards = []

    return render_template(
        "study.html",
        today=today, theme=SITE_THEME, join_url=JOIN_URL,
        studies=studies, week1_cards=week1_cards, active="study",
    )

# optional static study detail pages in templates/studies/<slug>.html
@app.route("/study/<slug>")
def study_detail(slug):
    filename = f"studies/{slug}.html"
    file_path = TEMPLATES_DIR / filename
    if not file_path.exists():
        return "Study not found", 404
    return render_template(filename)

@app.route("/verses")
def verses():
    today = datetime.now().date()
    data = load_json(DEVOTIONS_ROOT / "verses.json") or {}
    raw_cards = data.get("cards") or []
    cards = []
    for c in raw_cards:
        fname = (c.get("file") or "").strip()
        src = _find_verse_image_url(fname)
        if not src: continue
        cards.append({
            "src": src, "ref": c.get("ref") or "",
            "caption": c.get("caption") or "",
            "alt": c.get("ref") or "Scripture card",
        })
    return render_template(
        "verses.html",
        today=today, theme=SITE_THEME, join_url=JOIN_URL,
        theme_title=data.get("theme") or SITE_THEME,
        cards=cards,
        page_bg_class="bg-video",
        page_bg_video=url_for("static", filename="img/videos/seaside 1.mp4"),
        page_bg_poster=url_for("static", filename="img/hero_day.jpg"),
        active="verses",
    )

# ---- Prayer (rate-limited)
@app.route("/prayer", methods=["GET", "POST"])
@limiter.limit("5/minute; 20/hour")
def prayer():
    today = datetime.now().date()
    if request.method == "POST":
        name    = (request.form.get("name") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        text    = (request.form.get("request") or "").strip()
        if text:
            req_file = DEVOTIONS_ROOT / "prayer_requests.json"
            try:
                existing = load_json(req_file) or []
                if not isinstance(existing, list): existing = []
                existing.append({
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "name": name, "contact": contact, "request": text,
                })
                req_file.parent.mkdir(parents=True, exist_ok=True)
                with open(req_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
                return render_template("prayer.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, ok=True, active="prayer")
            except Exception:
                return render_template("prayer.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, ok=False, active="prayer")
    return render_template("prayer.html", today=today, theme=SITE_THEME, join_url=JOIN_URL, active="prayer")

@app.route("/about")
def about():
    return render_template("about.html", today=datetime.now().date(), theme=SITE_THEME, join_url=JOIN_URL, active="about")

@app.route("/join")
def join():
    return redirect(JOIN_URL, code=302)

# ---------- Feedback ----------
FEEDBACK_FILE = DEVOTIONS_ROOT / "feedback.json"

@app.route("/feedback", methods=["GET", "POST"])
@limiter.limit("5/minute; 50/day")
def feedback_view():
    today = datetime.now().date()
    if request.method == "POST":
        name    = (request.form.get("name") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        message = (request.form.get("message") or "").strip()
        if message:
            try:
                existing = load_json(FEEDBACK_FILE) or []
                if not isinstance(existing, list): existing = []
                existing.append({
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "name": name, "contact": contact, "message": message,
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
    if not isinstance(items, list): items = []
    items = sorted(items, key=lambda r: r.get("ts", ""), reverse=True)
    return render_template("admin_feedback.html", items=items, theme=SITE_THEME)

# ---------- Auth + Admin ----------
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
    return render_template("admin.html", today=today, today_str=today.strftime("%Y-%m-%d"),
                           theme=SITE_THEME, join_url=JOIN_URL, active="admin")

@app.route("/admin/requests")
def admin_requests():
    if not is_authed():
        return redirect(url_for("login"))
    req_file = DEVOTIONS_ROOT / "prayer_requests.json"
    items = load_json(req_file) or []
    if not isinstance(items, list): items = []
    items.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return render_template("admin_requests.html", items=items, theme=SITE_THEME, today=datetime.now().date())

@app.post("/admin/whatsapp/send")
def admin_whatsapp_send():
    if not is_authed():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    mode     = (request.form.get("mode") or "both").strip()  # both|morning|night|verses
    date_str = (request.form.get("date") or "").strip()

    candidate_paths = [
        BASE_DIR / "scripts" / "whatsapp_auto.py",
        BASE_DIR / "whatsapp_auto.py",
    ]
    script_path = next((p for p in candidate_paths if p.exists()), None)
    if not script_path:
        return jsonify({"ok": False, "error": "whatsapp_auto.py not found",
                        "looked_in": [str(p) for p in candidate_paths]}), 500

    targets = {
        "both": ["morning", "night"],
        "morning": ["morning"],
        "night": ["night"],
        "verses": ["verses"],
    }.get(mode, ["morning", "night"])

    results, all_ok = [], True
    for m in targets:
        args = [sys.executable, str(script_path), "--mode", m]
        if date_str: args += ["--date", date_str]
        try:
            out = subprocess.run(args, cwd=str(BASE_DIR), capture_output=True, text=True, shell=False)
            ok = out.returncode == 0
            all_ok = all_ok and ok
            results.append({
                "mode": m, "ok": ok, "args": args,
                "stdout": (out.stdout or "")[-4000:], "stderr": (out.stderr or "")[-4000:],
                "returncode": out.returncode,
            })
        except Exception as e:
            all_ok = False
            results.append({"mode": m, "ok": False, "error": str(e)})

    return jsonify({"ok": all_ok, "results": results})

# ---------- Donation / Volunteer ----------
@app.route("/donation")
def donation():
    paypal = os.environ.get("PAYPAL_LINK", "")
    ok = (request.args.get("ok") == "1")
    return render_template("donation.html", theme=SITE_THEME,
                           today=datetime.now().date(), paypal_link=paypal, ok=ok)

@app.route("/donation/thanks")
def donation_thanks():
    back_url = url_for("donation", ok=1)
    nxt = request.args.get("next")
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        back_url = nxt
    return render_template("donation_thanks.html", theme=SITE_THEME,
                           today=datetime.now().date(), back_url=back_url)

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
                if not isinstance(current, list): current = []
                current.append({
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "name": name, "contact": contact, "skills": skills,
                    "availability": availability, "notes": notes
                })
                vf.parent.mkdir(parents=True, exist_ok=True)
                vf.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
                return render_template("volunteer.html", ok=True, today=today, theme=SITE_THEME, join_url=JOIN_URL)
            except Exception:
                return render_template("volunteer.html", ok=False, today=today, theme=SITE_THEME, join_url=JOIN_URL)
        return render_template("volunteer.html", ok=None, err="Please include your name and at least contact or skills.",
                               today=today, theme=SITE_THEME, join_url=JOIN_URL)
    return render_template("volunteer.html", today=today, theme=SITE_THEME, join_url=JOIN_URL)

@app.route("/admin/volunteers")
def admin_volunteers():
    if not is_authed():
        return redirect(url_for("login"))
    vf = DEVOTIONS_ROOT / "volunteers.json"
    rows = load_json(vf) or []
    if not isinstance(rows, list): rows = []
    try:
        rows.sort(key=lambda r: r.get("ts", ""), reverse=True)
    except Exception:
        pass
    return render_template("admin_volunteers.html", rows=rows, today=datetime.now().date(),
                           theme=SITE_THEME, join_url=JOIN_URL)

# ---------- Favicon ----------
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon"
    )

# ---------- Errors ----------
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
    print("💜 SoulStart Devotion — Flask heartbeat ready (HTTP dev)…")
    if AUTO_OPEN:
        Timer(1.0, _open_browser).start()
    # debug True for fast iteration in dev; set APP_ENV=production for prod
    app.run(host=HOST, port=PORT, debug=not IS_PROD)
