#!/usr/bin/env python3
"""
Walks the templates directory and injects nonce="{{ csp_nonce() }}" into:
  - inline <script> tags without a src=
  - inline <style> tags without a href=
Skips tags that already have a nonce attribute.
Backs up original files as <name>.bak once.

Usage:
  python tools/add_nonce.py
"""

import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

# Regex: matches <script ...> ... </script> without src=
SCRIPT_TAG_RE = re.compile(
    r'(<script\b(?![^>]*\bsrc=)[^>]*)(>)',
    flags=re.IGNORECASE
)
# Regex: matches <style ...> ... </style> (style never uses href= in HTML)
STYLE_TAG_RE = re.compile(
    r'(<style\b[^>]*)(>)',
    flags=re.IGNORECASE
)
# Detect existing nonce attribute
NONCE_ATTR_RE = re.compile(r'\bnonce\s*=\s*["\']', flags=re.IGNORECASE)

def add_nonce_to_tag(match):
    start, end = match.group(1), match.group(2)
    if NONCE_ATTR_RE.search(start):
        return match.group(0)  # already has nonce
    # inject nonce before the closing '>'
    return f'{start} nonce="{{{{ csp_nonce() }}}}"{end}'

def process_file(path: Path):
    orig = path.read_text(encoding="utf-8")
    out = orig

    # Only consider files that look like Jinja/HTML
    if path.suffix.lower() not in {".html", ".jinja", ".jinja2"}:
        return False, "skip_ext"

    # Add nonce to inline <script> (no src=)
    out = SCRIPT_TAG_RE.sub(add_nonce_to_tag, out)
    # Add nonce to <style> (always inline in templates)
    out = STYLE_TAG_RE.sub(add_nonce_to_tag, out)

    if out != orig:
        # Backup once
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            bak.write_text(orig, encoding="utf-8")
        path.write_text(out, encoding="utf-8")
        return True, "updated"
    return False, "nochange"

def main():
    if not TEMPLATES_DIR.exists():
        print(f"Templates folder not found: {TEMPLATES_DIR}")
        return
    changed = 0
    for p in TEMPLATES_DIR.rglob("*"):
        if p.is_file():
            did, status = process_file(p)
            if did:
                changed += 1
                print(f"[nonce] updated: {p.relative_to(TEMPLATES_DIR)}")
    print(f"Done. Files updated: {changed}")

if __name__ == "__main__":
    main()
