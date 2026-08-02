# -*- coding: utf-8 -*-

from flask import Flask, render_template, redirect, request, url_for, jsonify, abort
from flask_wtf import CSRFProtect
from werkzeug.utils import secure_filename
import json
import random
import os
from urllib.parse import quote
from old_backup.build_whatsapp_message import build_whatsapp_message
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key"
csrf = CSRFProtect(app)

BASE_DIR = Path(__file__).resolve().parent

PRAYER_FILE = BASE_DIR / "data" / "prayer_requests.json"

DEVOTION_FILE = (
    BASE_DIR
    / "data"
    / "devotions"
    / "devotions_2026.json"
)

STUDY_DIR = BASE_DIR / "data" / "study"

BLOG_DATA_PATH = (
    BASE_DIR
    / "data"
    / "blog"
    / "blog_backup.json"
)

BLOG_POSTS_JSON = (
    BASE_DIR
    / "data"
    / "blog"
    / "soul_speaks_2026.json"
)

FAITH_FOUNDATIONS_FILE = (
    BASE_DIR
    / "data"
    / "faith_foundations"
    / "faith_foundations_2026.json"
)

UPLOAD_FOLDER = (
    BASE_DIR
    / "static"
    / "uploads"
    / "blog_images"
)

DEFAULT_MODE = "morning"
MINISTRY_TZ = timezone(timedelta(hours=-4))
HERO_DAY_BG = "img/home/hero-day.jpg"
HERO_NIGHT_BG = "img/home/hero-night.jpg"

CATEGORY_MAP = {
    "Soul Speaks": "soul_speaks",
    "Faith Foundations": "faith_foundations",
    "Practical Growth": "practical_growth",
    "Community & Advocacy": "community_advocacy",
}

CATEGORY_PREFIX = {
    "Soul Speaks": "SS",
    "Faith Foundations": "FF",
    "Practical Growth": "PG",
    "Community & Advocacy": "CA",
}

OLD_BLOGS = [
    {
        "title": "God’s Love Beyond Sound",
        "slug": "gods-love-beyond-sound",
        "publish_date": "2026-02-02",
        "month_label": "February",
        "category": "reflection",
        "category_label": "Soul Speaks",
        "blog_number": "SS001",
        "tags": ["Love", "Deaf Identity", "Presence", "Faith", "Silence"],
        "image": "gods-love-beyond-sound.jpg",
        "excerpt": "God’s love is not limited by sound. Every heart is fully known.",
    },
    {
        "title": "Silence Is Not Absence",
        "slug": "silence-is-not-absence",
        "publish_date": "2026-02-16",
        "month_label": "February",
        "category": "reflection",
        "category_label": "Soul Speaks",
        "blog_number": "SS002",
        "tags": ["Silence", "Presence", "Deaf Culture", "Reflection"],
        "image": "silence-is-not-absence.jpg",
        "excerpt": "Silence is not absence. It is presence without pressure.",
    },
{
    "title": "Faith Without Noise",
    "slug": "faith-without-noise",
    "publish_date": "2026-03-09",
    "month_label": "March",
    "category": "reflection",
    "category_label": "Soul Speaks",
    "blog_number": "SS003",
    "tags": ["Faith", "Focus", "Grace", "Courage"],
    "image": "img/blog/uploads/soulspeaks/faith-without-noise.jpg",
    "excerpt": "Faith does not need noise. It needs focus.",
},
{
    "title": "When the Wind Is Loud but God Is Near",
    "slug": "when-the-wind-is-loud",
    "publish_date": "2026-03-23",
    "month_label": "March",
    "category": "reflection",
    "category_label": "Soul Speaks",
    "blog_number": "SS004",
    "tags": ["Storms", "Presence", "Faith"],
    "image": "img/blog/uploads/soulspeaks/when-the-wind-is-loud.jpg",
    "excerpt": "God’s presence is near, even when life feels loud.",
},
{
    "title": "Healing Is Not Always Loud",
    "slug": "healing-is-not-always-loud",
    "publish_date": "2026-04-26",
    "month_label": "April",
    "category": "reflection",
    "category_label": "Soul Speaks",
    "blog_number": "SS005",
    "tags": ["Healing", "Restoration", "Grace"],
    "image": "img/blog/uploads/soulspeaks/healing-is-not-always-loud.jpg",
    "excerpt": "Healing is not less powerful because it is quiet.",
},
{
    "title": "When Jesus Touches Before He Speaks",
    "slug": "jesus-touches-before-he-speaks",
    "publish_date": "2026-04-20",
    "month_label": "April",
    "category": "reflection",
    "category_label": "Soul Speaks",
    "blog_number": "SS006",
    "tags": ["Healing", "Presence", "Compassion"],
    "image": "img/blog/uploads/soulspeaks/jesus-touches-before-he-speaks.jpg",
    "excerpt": "God’s love reaches us before words ever do.",
}
]

SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:5001")

SITE_THEME = os.getenv("SITE_THEME", "Faith to Rise, Grace to Rest")

JOIN_URL = os.getenv("JOIN_URL", "https://chat.whatsapp.com/CdkN2V0h8vCDg2AP4saYfG")
WHATSAPP_GROUP_LINK = os.getenv("WHATSAPP_GROUP_LINK", JOIN_URL)
SITE_JOIN_URL = WHATSAPP_GROUP_LINK

ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL", "sscministry@outlook.com") or "").strip().lower()
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD", "") or "").strip()
ADMIN_PASS = ADMIN_PASSWORD  # backwards compat

FACEBOOK_URL = os.getenv("FACEBOOK_URL", "https://www.facebook.com/profile.php?id=61585837505269")
LINKEDIN_URL = os.getenv("LINKEDIN_URL", "https://www.linkedin.com/company/silentsoulconnect")

SOCIAL_LINKS = {
    "facebook": FACEBOOK_URL,
    "linkedin": LINKEDIN_URL,
    "whatsapp": WHATSAPP_GROUP_LINK,
    "email": f"mailto:{ADMIN_EMAIL}",
}

SUPPORT_LINES = [
    "You do not have to walk alone.",
    "A simple gift can bring quiet strength to a searching heart.",
    "Together, we can make faith more accessible.",
    "Your support helps another heart find hope.",
    "Your generosity helps the message continue.",
]

def normalize_date_str(value: str) -> str:
    return value.strip()


def load_all_devotions():
    """Load the devotion JSON file safely."""
    if not DEVOTION_FILE.exists():
        app.logger.warning("Devotion file not found: %s", DEVOTION_FILE)
        return []

    try:
        with DEVOTION_FILE.open("r", encoding="utf-8") as f:
            records = json.load(f)

        return records if isinstance(records, list) else []

    except json.JSONDecodeError as error:
        app.logger.error("Devotion JSON error: %s", error)
        return []

    except OSError as error:
        app.logger.error("Could not open devotion file: %s", error)
        return []


def load_devotion_for(target_date, mode):
    date_str = target_date.strftime("%Y-%m-%d")
    records = load_all_devotions()

    for item in records:
        if item.get("date") == date_str:
            section = item.get(mode, {}) or {}

            return {
                "date": item.get("date", ""),
                "theme": item.get("theme", ""),

                # Image can be stored in the morning/night section
                # or at the main devotion level.
                "image": (
                    section.get("image")
                    or section.get("background")
                    or item.get("image")
                    or item.get("background")
                    or ""
                ),

                "verse_ref": section.get("verse_ref", ""),
                "verse_text": section.get("verse_text", ""),
                "verse_meaning": section.get("verse_meaning", ""),
                "body": section.get("body", ""),
                "prayer": section.get("prayer", ""),
            }

    return {}

def ensure_devotion_image(target_date):
        """
        Return one generated hero image for the devotion date.

        Morning and night use the same image.
        The night appearance is created with CSS.
        """

        date_str = target_date.strftime("%Y-%m-%d")
        year = target_date.strftime("%Y")

        image_rel = (
                Path("img")
                / "devotion"
                / "hero"
                / year
                / f"{date_str}.jpg"
        )

        image_full = Path(app.static_folder) / image_rel

        if image_full.exists():
            return image_rel.as_posix()

        try:
            from services.generate_devotion_image import generate_devotion_image

            generated_path = generate_devotion_image(date_str)

            if generated_path and Path(generated_path).exists():
                return image_rel.as_posix()

        except Exception as error:
            app.logger.exception(
                "Could not generate devotion hero for %s: %s",
                date_str,
                error,
            )

        fallback = Path(app.static_folder) / HERO_DAY_BG

        if fallback.exists():
            return HERO_DAY_BG

        return None

def base_ctx(**extra):
    """Shared context for public templates."""
    ctx = {
        "active": "",
        "join_url": SITE_JOIN_URL,
        "today": date.today(),
        "page_bg_class": "",
        "page_bg_url": "",
    }
    ctx.update(extra)
    return ctx


def common_page_ctx(active=""):
    """Backward-compatible page context helper."""
    return base_ctx(active=active)

## def get_next_ss_number():
    old_posts = load_blog_posts()
    new_posts = load_soul_speaks()

    all_posts = old_posts + new_posts

    numbers = []

    for post in all_posts:
        number = post.get("blog_number", "")

        if number.startswith("SS"):
            try:
                numbers.append(int(number.replace("SS", "")))
            except ValueError:
                pass

    if not numbers:
        return "SS007"

    next_number = max(numbers) + 1
    return f"SS{next_number:03d}"


def load_blog_posts():
    if not BLOG_DATA_PATH.exists():
        return []

    with BLOG_DATA_PATH.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def get_blog_post_by_slug(slug):
    posts = load_blog_posts()
    for post in posts:
        if post.get("slug") == slug:
            return post
    return None


def update_blog_post_by_slug(slug, updated_post):
    posts = load_blog_posts()

    for i, post in enumerate(posts):
        if post.get("slug") == slug:
            posts[i] = updated_post
            save_blog_posts(posts)
            return True

    return False

def save_blog_posts(posts):
    BLOG_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BLOG_DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4, ensure_ascii=False)


def make_slug(title: str) -> str:
    slug = title.strip().lower()
    for ch in ["?", "!", ".", ",", ":", ";", "'", '"', "(", ")", "&"]:
        slug = slug.replace(ch, "")
    slug = slug.replace("/", "-").replace("\\", "-")
    slug = "-".join(slug.split())
    return slug

def load_json_blog_posts():
    print("BLOG_POSTS_JSON:", BLOG_POSTS_JSON)
    print("EXISTS:", BLOG_POSTS_JSON.exists())

    if not BLOG_POSTS_JSON.exists():
        return []

    with BLOG_POSTS_JSON.open("r", encoding="utf-8") as f:
        try:
            posts = json.load(f)

            if isinstance(posts, dict):
                posts = [posts]

            print("JSON POSTS LOADED:", len(posts))
            print("FIRST POST:", posts[0].get("slug") if posts else "none")

            return posts if isinstance(posts, list) else []

        except json.JSONDecodeError as e:
            print("JSON ERROR:", e)
            return []

def format_content_to_html(text: str) -> str:
    """
    Convert plain text into simple HTML paragraphs.
    Separate paragraphs with a blank line in the form.
    """
    text = (text or "").strip()
    if not text:
        return ""

    paragraphs = text.split("\n\n")
    clean_paragraphs = []

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        p = p.replace("\n", "<br>")
        clean_paragraphs.append(f"<p>{p}</p>")

    return "\n".join(clean_paragraphs)


@app.context_processor
def inject_global_vars():
    return {
        "SITE_THEME": SITE_THEME,
        "SITE_URL": SITE_URL,
        "JOIN_URL": JOIN_URL,
        "WHATSAPP_GROUP_LINK": WHATSAPP_GROUP_LINK,
        "SITE_JOIN_URL": SITE_JOIN_URL,
        "ADMIN_EMAIL": ADMIN_EMAIL,
        "FACEBOOK_URL": FACEBOOK_URL,
        "LINKEDIN_URL": LINKEDIN_URL,
        "SOCIAL_LINKS": SOCIAL_LINKS,
        "current_year": date.today().year,
    }

# =========================
# BASIC PAGE ROUTES
# =========================

@app.route("/")
def home():
    return render_template("pages/home.html", active="home")


@app.route("/about")
def about():
    return render_template("pages/about.html", active="about")

@app.route("/anchor")
def anchor():
    return render_template("pages/anchor.html", active="anchor")


@app.route("/foundation")
def foundation():
    return render_template("pages/foundation.html", active="foundation")


@app.route("/path")
def path():
    return render_template("path/path.html", active="path")

# =========================
# DEVOTION ROUTES
# =========================

@app.route("/today", endpoint="today")
def today_view():
    """Display today's devotion or the single permitted previous day."""
    mode_arg = (request.args.get("mode") or "").strip().lower()
    mode = mode_arg if mode_arg in {"morning", "night"} else DEFAULT_MODE

    actual_today = datetime.now(MINISTRY_TZ).date()

    allowed_dates = {
        actual_today,
        actual_today - timedelta(days=1),
    }

    raw_date = (request.args.get("date") or "").strip()
    target_date = actual_today

    if raw_date:
        try:
            requested_date = datetime.strptime(
                normalize_date_str(raw_date),
                "%Y-%m-%d",
            ).date()

            if requested_date in allowed_dates:
                target_date = requested_date

        except ValueError:
            target_date = actual_today

    entry = load_devotion_for(target_date, mode)
    preview_text = build_whatsapp_message(target_date.isoformat(), mode)

    hero_bg = HERO_NIGHT_BG if mode == "night" else HERO_DAY_BG
    hero_class = "hero night-tone" if mode == "night" else "hero"

    devotion_image = ensure_devotion_image(target_date)

    ctx = base_ctx(
        active="today",
        entry=entry,
        mode=mode,
        target_date=target_date,
        today=target_date,
        devotion_image=devotion_image,
        hero_bg=hero_bg,
        hero_class=hero_class,
        preview_text=preview_text,
        whatsapp_preview=preview_text,
        is_today=(target_date == actual_today),
    )

    if target_date == actual_today:
        yesterday = actual_today - timedelta(days=1)
        ctx["yday_url"] = url_for(
            "today",
            date=yesterday.isoformat(),
            mode=mode,
        )
        ctx["yday_label"] = "← Yesterday’s devotion"
    else:
        ctx["yday_url"] = None
        ctx["yday_label"] = ""
        ctx["today_url"] = url_for("today", mode=mode)

    return render_template("devotion/devotion.html", **ctx)


@app.route("/devotion", endpoint="devotion")
def devotion_welcome():
    ctx = common_page_ctx(active="devotion")
    ctx.update({
        "begin_url": url_for("today")
    })
    return render_template("devotion/q3_welcome.html", **ctx)


@app.route("/devotion/q3-welcome", endpoint="q3_welcome")
def q3_welcome():
    ctx = common_page_ctx(active="devotion")
    ctx.update({
        "begin_url": url_for("today")
    })
    return render_template("devotion/q3_welcome.html", **ctx)

# =========================
# STUDY JSON LOADER
# =========================

def load_study_series(series_slug):
    study_file = (STUDY_DIR / f"{series_slug}.json").resolve()

    print("=" * 60)
    print("Slug      :", repr(series_slug))
    print("File      :", repr(study_file))
    print("Exists    :", study_file.exists())

    if not study_file.exists():
        print("Study JSON not found:", study_file)
        return None

    try:
        with study_file.open("r", encoding="utf-8") as f:
            study = json.load(f)

        print("Study loaded:", study_file.name)
        return study

    except json.JSONDecodeError as e:
        print(f"JSON error in {study_file.name}: {e}")
        return None

    except OSError as e:
        print(f"File error opening {study_file}: {e}")
        return None

# =========================
# STUDY ROUTES
# old Introduction series stays HTML
# =========================

@app.route("/study")
def study_index():
    return render_template(
        "study/study_index.html",
            active="study"
        )

@app.route("/study/introduction")
def intro_series():
    return render_template("study/intro_series.html")


@app.route("/study/introduction/lesson-1")
def study_lesson_1():
    return render_template("study/lesson1.html")


@app.route("/study/introduction/lesson-2")
def study_lesson_2():
    return render_template("study/lesson2.html")


@app.route("/study/introduction/lesson-3")
def study_lesson_3():
    return render_template("study/lesson3.html")


# =========================
# NEW JSON STUDY ROUTES
# =========================

@app.route("/study/<series_slug>")
def study_series(series_slug):
    study = load_study_series(series_slug)

    if not study:
        abort(404)

    return render_template(
        "study/study_series.html",
        study=study
    )


@app.route("/study/<series_slug>/<lesson_slug>")
def study_lesson_json(series_slug, lesson_slug):
    study = load_study_series(series_slug)

    if not study:
        abort(404)

    if lesson_slug == "introduction":
        lesson = study.get("introduction")
    else:
        lesson = next(
            (
                item
                for item in study.get("lessons", [])
                if item.get("id") == lesson_slug
            ),
            None
        )

    if not lesson:
        abort(404)

    return render_template(
        "study/study_lesson.html",
        study=study,
        lesson=lesson
    )

# =========================
# BLOG LOADERS
# =========================

def load_soul_speaks():
    if not BLOG_POSTS_JSON.exists():
        print("Soul Speaks file not found:", BLOG_POSTS_JSON)
        return []

    try:
        with BLOG_POSTS_JSON.open("r", encoding="utf-8") as f:
            posts = json.load(f)

        return posts if isinstance(posts, list) else []

    except json.JSONDecodeError as e:
        print("Soul Speaks JSON error:", e)
        return []

    except OSError as e:
        print("Soul Speaks file error:", e)
        return []


def load_faith_foundations():
    if not FAITH_FOUNDATIONS_FILE.exists():
        print(
            "Faith Foundations file not found:",
            FAITH_FOUNDATIONS_FILE
        )
        return []

    try:
        with FAITH_FOUNDATIONS_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:
            posts = json.load(f)

        return posts if isinstance(posts, list) else []

    except json.JSONDecodeError as e:
        print("Faith Foundations JSON error:", e)
        return []

    except OSError as e:
        print("Faith Foundations file error:", e)
        return []

# =========================
# BLOG ROUTES
# =========================
@app.route("/blog")
def blog_index():
    selected_category = request.args.get("category", "").strip()
    selected_tag = request.args.get("tag", "").strip()

    old_posts = OLD_BLOGS
    backup_posts = load_blog_posts()
    soul_posts = load_soul_speaks()
    faith_posts = load_faith_foundations()

    posts = old_posts + soul_posts + faith_posts + backup_posts

    posts = [
        p for p in posts
        if p.get("status", "published") == "published"
        or not p.get("status")
    ]

    today = date.today().isoformat()

    posts = [
        p for p in posts
        if (p.get("publish_date") or p.get("date", "1900-01-01")) <= today
    ]

    if selected_category:
        posts = [
            p for p in posts
            if p.get("category") == selected_category
            or p.get("category_label") == selected_category
            or p.get("pillar") == selected_category
        ]

    if selected_tag:
        posts = [
            p for p in posts
            if selected_tag in p.get("tags", [])
        ]

    posts = sorted(
        posts,
        key=lambda p: p.get("publish_date") or p.get("date", ""),
        reverse=True
    )

    return render_template(
        "blog/index.html",
        posts=posts,
        selected_category=selected_category,
        selected_tag=selected_tag
    )

@app.route("/blog/<slug>")
def blog_post(slug):
    posts = load_soul_speaks()

    post = next(
        (p for p in posts if p.get("slug") == slug),
        None
    )

    if not post:
        abort(404)

    return render_template(
        "blog/post.html",
        post=post,
        support_line=random.choice(SUPPORT_LINES)
        if "SUPPORT_LINES" in globals()
        else ""
    )

@app.route("/blog/faith-foundation/<slug>")
def faith_foundation_post(slug):
    posts = load_faith_foundations()

    post = next((p for p in posts if p.get("slug") == slug), None)

    if not post:
        abort(404)

    return render_template(
        "blog/faith-foundation/faith_foundation.html",
        post=post
    )

# =========================
# PRAYER ROUTE
# =========================

@app.route("/prayer", methods=["GET", "POST"])
def prayer():
    prayer_topics = [
        {"value": "simple_self", "label": "Simple prayer for myself"},
        {"value": "anonymous", "label": "Anonymous prayer"},
        {"value": "surrender", "label": "Surrendering prayer"},
        {"value": "help_unbelief", "label": "Lord, help my unbelief"},
        {"value": "healing", "label": "Healing"},
        {"value": "family", "label": "Family"},
        {"value": "peace", "label": "Peace"},
        {"value": "guidance", "label": "Guidance"},
        {"value": "grief", "label": "Grief / Loss"},
        {"value": "thanksgiving", "label": "Thanksgiving"},
        {"value": "other", "label": "Other"},
    ]

    if request.method == "POST":
        PRAYER_FILE.parent.mkdir(parents=True, exist_ok=True)

        new_request = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "name": request.form.get("name", "").strip() or "Anonymous",
            "contact": request.form.get("contact", "").strip(),
            "pref_method": request.form.get("pref_method", "").strip(),
            "topic": request.form.get("topic", "").strip(),
            "topic_other": request.form.get("topic_other", "").strip(),
            "request": request.form.get("request", "").strip(),
        }

        if PRAYER_FILE.exists():
            with open(PRAYER_FILE, "r", encoding="utf-8") as f:
                prayers = json.load(f)
        else:
            prayers = []

        prayers.append(new_request)

        with open(PRAYER_FILE, "w", encoding="utf-8") as f:
            json.dump(prayers, f, indent=2, ensure_ascii=False)

        return redirect(url_for("prayer", ok=1))

    return render_template(
        "prayer/prayer.html",
        active="prayer",
        prayer_topics=prayer_topics
    )


# =========================
# DONATION ROUTE
# =========================

@app.route("/donate", methods=["GET", "POST"])
def donate():
    return render_template("pages/donation.html")

#: ADMIN#
@app.route("/admin")
def admin_dashboard():
    return render_template("admin/admin_dashboard.html")

@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        name = request.form.get("name")
        contact = request.form.get("contact")
        skills = request.form.get("skills")
        availability = request.form.get("availability")
        notes = request.form.get("notes")

        # checkboxes
        prefs = []
        if request.form.get("asl"):
            prefs.append("Sign Language")
        if request.form.get("text"):
            prefs.append("Text/WhatsApp")
        if request.form.get("plain"):
            prefs.append("Plain English")

        # 👉 for now just print (safe testing)
        print("NEW JOIN REQUEST")
        print(name, contact, skills, availability, notes, prefs)

        # redirect after submit (prevents resubmission)
        return redirect(url_for("join", ok=1))

    return render_template("pages/join.html")

@app.route("/admin/blogs")
def admin_blog_list():
    posts = load_blog_posts()
    posts = sorted(posts, key=lambda p: p.get("publish_date", ""), reverse=True)

    return render_template("admin/admin_blog_list.html", posts=posts)

@app.route("/admin/blog/next-number")
def admin_blog_next_number():
    category = request.args.get("category", "").strip()
    prefix = CATEGORY_PREFIX.get(category)

    if not prefix:
        return jsonify({"blog_number": ""})

    posts = load_blog_posts()
    count = sum(1 for post in posts if post.get("category") == category)
    next_number = f"{prefix}{count + 1:03d}"

    return jsonify({"blog_number": next_number})


@app.route("/admin/blog/new", methods=["GET", "POST"])
def admin_blog():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        publish_date = (request.form.get("publish_date") or "").strip()
        category = (request.form.get("category") or "").strip()
        blog_number = (request.form.get("blog_number") or "").strip()
        topic_1 = (request.form.get("topic_1") or "").strip()
        topic_2 = (request.form.get("topic_2") or "").strip()
        topic_3 = (request.form.get("topic_3") or "").strip()
        content = (request.form.get("content") or "").strip()

        if not title or not publish_date or not category or not blog_number or not content:
            return "Missing required fields.", 400

        slug = make_slug(title)
        tags = [t.strip() for t in [topic_1, topic_2, topic_3] if t and t.strip()]

        image_file = request.files.get("image")
        image_path = "img/default-blog.jpg"

        if image_file and image_file.filename:
            category_folder = CATEGORY_MAP.get(category, "misc")
            upload_path = UPLOAD_FOLDER / category_folder
            upload_path.mkdir(parents=True, exist_ok=True)

            filename = secure_filename(f"{blog_number}-{image_file.filename}")
            image_file.save(upload_path / filename)

            image_path = f"uploads/blog_images/{category_folder}/{filename}"

        new_post = {
            "title": title,
            "publish_date": publish_date,
            "category": category,
            "blog_number": blog_number,
            "tags": tags,
            "image": image_path,
            "content": format_content_to_html(content),
            "slug": slug,
        }

        posts = load_blog_posts()
        posts.append(new_post)
        save_blog_posts(posts)

        return redirect(url_for("blog_index"))

    return render_template("admin/admin_blog_form.html")

@app.route("/admin/blog/edit/<slug>", methods=["GET", "POST"])
def edit_blog(slug):
    post = get_blog_post_by_slug(slug)

    if not post:
        abort(404)

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        publish_date = (request.form.get("publish_date") or "").strip()
        category = (request.form.get("category") or "").strip()
        blog_number = (request.form.get("blog_number") or "").strip()
        topic_1 = (request.form.get("topic_1") or "").strip()
        topic_2 = (request.form.get("topic_2") or "").strip()
        topic_3 = (request.form.get("topic_3") or "").strip()
        content = (request.form.get("content") or "").strip()

        if not title or not publish_date or not category or not blog_number or not content:
            return "Missing required fields.", 400

        new_slug = make_slug(title)
        tags = [t.strip() for t in [topic_1, topic_2, topic_3] if t and t.strip()]

        image_path = post.get("image", "img/default-blog.jpg")
        image_file = request.files.get("image")

        if image_file and image_file.filename:
            category_folder = CATEGORY_MAP.get(category, "misc")
            upload_path = UPLOAD_FOLDER / category_folder
            upload_path.mkdir(parents=True, exist_ok=True)

            filename = secure_filename(f"{blog_number}-{image_file.filename}")
            image_file.save(upload_path / filename)
            image_path = f"uploads/blog_images/{category_folder}/{filename}"

        updated_post = {
            "title": title,
            "publish_date": publish_date,
            "category": category,
            "blog_number": blog_number,
            "tags": tags,
            "image": image_path,
            "content": content,
            "slug": new_slug,
        }

        update_blog_post_by_slug(slug, updated_post)
        return redirect(url_for("blog_post", slug=new_slug))

    tags = post.get("tags", [])
    return render_template(
        "admin/admin_blog_edit.html",
        post=post,
        topic_1=tags[0] if len(tags) > 0 else "",
        topic_2=tags[1] if len(tags) > 1 else "",
        topic_3=tags[2] if len(tags) > 2 else "",
    )

@csrf.exempt

@app.route("/admin/whatsapp", methods=["GET", "POST"])
def admin_whatsapp_send():
    result = {}
    selected_date = date.today().isoformat()
    selected_mode = "morning"
    selected_topic = ""
    devotion_image = None

    prayer_topics = [
        "Strength",
        "Healing",
        "Peace",
        "Family",
        "Faith",
        "Guidance",
    ]

    if request.method == "POST":
        selected_date = request.form.get("date") or selected_date

        try:
            selected_date = datetime.strptime(selected_date, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

        selected_mode = request.form.get("mode") or "morning"
        selected_topic = request.form.get("topic") or ""

        image_mode = "morning" if selected_mode == "both" else selected_mode
        devotion_image = ensure_devotion_image(
            datetime.strptime(selected_date, "%Y-%m-%d").date(),
            image_mode,
        )

        if selected_mode == "both":
            morning_text = build_whatsapp_message(selected_date, "morning", selected_topic)
            night_text = build_whatsapp_message(selected_date, "night", selected_topic)

            result = {
                "text_morning": morning_text,
                "text_night": night_text,
                "share_wa_morning": "https://wa.me/?text=" + quote(morning_text, safe=""),
                "share_wa_night": "https://wa.me/?text=" + quote(night_text, safe=""),
                "share_web_morning": f"/today?date={selected_date}&mode=morning",
                "share_web_night": f"/today?date={selected_date}&mode=night",
            }

        else:
            text = build_whatsapp_message(selected_date, selected_mode, selected_topic)

            result = {
                "text": text,
                "share_wa": "https://wa.me/?text=" + quote(text, safe=""),
                "share_web": f"/today?date={selected_date}&mode={selected_mode}",
                "share_api": "#",
            }

    return render_template(
        "admin/admin_whatsapp.html",
        today=date.today(),
        selected_date=selected_date,
        selected_mode=selected_mode,
        selected_topic=selected_topic,
        prayer_topics=prayer_topics,
        result=result,
        devotion_image=devotion_image,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)