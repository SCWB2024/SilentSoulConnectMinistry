# util/study.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, render_template, Response  # type: ignore

bp = Blueprint("study", __name__, url_prefix="/studies")


def _templates_root() -> Path:
    # Flask template_folder is usually "<project>/templates"
    return Path(current_app.template_folder or "templates")


def _study_dir() -> Path:
    return _templates_root() / "study"


def _meta_file() -> Path:
    # project root is usually one level up from templates/
    # templates/ -> project/
    proj_root = _templates_root().parent
    return proj_root / "data" / "studies.json"


def load_study_meta() -> dict[str, dict[str, Any]]:
    """
    Optional metadata for study series from data/studies.json.

    Recommended shape:
      {
        "series1": {"title": "Series 1 – New Life", "tagline": "..."},
        "series2": {"title": "Series 2 – Growing in Grace", "tagline": "..."}
      }

    If missing or invalid -> returns {} (no crashes).
    """
    f = _meta_file()
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@bp.get("")
@bp.get("/")
def index():
    """List all available study series (series*.html) with optional metadata."""
    meta = load_study_meta()
    items: list[dict[str, str]] = []

    sdir = _study_dir()
    if sdir.exists():
        for p in sorted(sdir.glob("series*.html")):
            key = p.stem  # e.g., "series1"
            default_title = key.replace("series", "Series ").title()
            m = meta.get(key, {})
            title = str(m.get("title", default_title))
            tagline = str(m.get("tagline", ""))
            items.append({"key": key, "title": title, "tagline": tagline})

    return render_template(
        "study/index.html",
        title="Study Series",
        series=items,
        active="study",
    )


@bp.get("/<series_name>")
def detail(series_name: str):
    """Render HTML study page: templates/study/<series_name>.html"""
    if not series_name.startswith("series"):
        abort(404)

    rel = Path("study") / f"{series_name}.html"
    abs_path = _templates_root() / rel
    if not abs_path.exists():
        abort(404)

    meta = load_study_meta()
    default_title = series_name.replace("series", "Series ").title()
    page_title = str(meta.get(series_name, {}).get("title", default_title))

    return render_template(
        str(rel).replace("\\", "/"),
        title=page_title,
        active="study",
    )


@bp.get("/<series_name>.xml")
def series_xml(series_name: str):
    """
    Render XML for a series:
      templates/study/xml/<series_name>.xml
    """
    if not series_name.startswith("series"):
        abort(404)

    rel = Path("study") / "xml" / f"{series_name}.xml"
    abs_path = _templates_root() / rel
    if not abs_path.exists():
        abort(404)

    xml = render_template(str(rel).replace("\\", "/"))
    return Response(xml, mimetype="application/xml")
