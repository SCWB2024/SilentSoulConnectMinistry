# -*- coding: utf-8 -*-
"""
SoulStart Sunset video generator (with sign-language PIP).
- Reads JSON: devotions/September/SoulStart_Sunset_Sep.json
- Outputs: videos/sunset_YYYY-MM-DD.mp4 + .srt
- MoviePy 2.x compatible (with_* / subclipped / resized)

Install:
  pip install moviepy pillow imageio[ffmpeg] numpy
"""

import os
import json
import argparse
import math
from datetime import datetime, date
from zoneinfo import ZoneInfo
import numpy as np
from moviepy import ColorClip, ImageClip, VideoFileClip, CompositeVideoClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont

# ---------- CONFIG ----------
TZ = ZoneInfo("America/Nassau")
W, H = 1920, 1080
FPS = 30
BG_COLOR = (9, 16, 28)        # deep navy
PANEL = (245, 248, 252)       # light panel
INK = (31, 41, 55)            # text color

FONT_PATHS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    r"/System/Library/Fonts/Supplemental/Arial.ttf",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSON = os.path.join(BASE_DIR, "devotions", "September", "SoulStart_Sunset_Sep.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DEFAULT_SIGN_MP4 = os.path.join(STATIC_DIR, "sign_sample.mp4")
DEFAULT_SIGN_IMG = os.path.join(STATIC_DIR, "sign_placeholder.jpg")
SSCM_LOGO = os.path.join(STATIC_DIR, "sscm_logo.png")
SOULSTART_LOGO = os.path.join(STATIC_DIR, "soulstart_logo.png")

OUT_DIR = os.path.join(BASE_DIR, "videos")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------- HELPERS ----------
def find_font(size=64):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
    return ImageFont.load_default()

def wrap_text(text, font, max_width):
    lines = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        words, current = para.split(), ""
        for w in words:
            trial = (current + " " + w).strip()
            if font.getlength(trial) <= max_width:
                current = trial
            else:
                if current: lines.append(current)
                current = w
        if current: lines.append(current)
    return lines

def render_panel(text, title=None, subtitle=None, width=W-320, padding=40, title_size=70, text_size=52):
    title_font = find_font(title_size)
    sub_font   = find_font(36)
    body_font  = find_font(text_size)

    inner_w = width - padding*2
    lines = []
    if title:    lines.append(("title", title))
    if subtitle: lines.append(("sub", subtitle))
    for line in wrap_text(text, body_font, inner_w):
        lines.append(("body", line))

    est_h = padding*2
    for kind, _ in lines:
        est_h += (title_font.size + 10) if kind=="title" else (sub_font.size + 8 if kind=="sub" else body_font.size + 8)

    img = Image.new("RGB", (width, est_h), PANEL)
    draw = ImageDraw.Draw(img)
    x, y = padding, padding
    for kind, ln in lines:
        if kind=="title":
            draw.text((x, y), ln, font=title_font, fill=INK); y += title_font.size + 10
        elif kind=="sub":
            draw.text((x, y), ln, font=sub_font, fill=(75, 85, 99)); y += sub_font.size + 8
        else:
            draw.text((x, y), ln, font=body_font, fill=INK); y += body_font.size + 8
    return img

def text_panel_clip(text, title=None, subtitle=None, dur=6.0):
    frame = np.array(render_panel(text=text, title=title, subtitle=subtitle))
    return ImageClip(frame).with_duration(dur)

def dur_for(text, base=4.5, per_char=0.028, min_d=4.0, max_d=14.0):
    est = base + len(text)*per_char
    return max(min_d, min(max_d, est))

def fmt_date(d: date):
    return d.strftime("%A, %B %d, %Y")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def pick_entry(entries, day_iso):
    for x in entries:
        if x.get("date") == day_iso:
            return x
    try:
        dated = [x for x in entries if x.get("date")]
        dated.sort(key=lambda x: abs((datetime.fromisoformat(x["date"]).date()
                                      - datetime.fromisoformat(day_iso).date()).days))
        return dated[0] if dated else (entries[0] if entries else None)
    except Exception:
        return entries[0] if entries else None

def sign_pip(sign_path, total_dur):
    src_mp4 = sign_path if (sign_path and os.path.exists(sign_path)) else (
              DEFAULT_SIGN_MP4 if os.path.exists(DEFAULT_SIGN_MP4) else None)
    src_img = DEFAULT_SIGN_IMG if os.path.exists(DEFAULT_SIGN_IMG) else None

    if src_mp4:
        v = VideoFileClip(src_mp4)
        if v.duration >= total_dur:
            v = v.subclipped(0, total_dur)
        else:
            loops = max(1, math.ceil(total_dur / max(v.duration, 0.1)))
            v = concatenate_videoclips([v]*loops).subclipped(0, total_dur)
        v = v.resized(height=360)
        border = ColorClip((int(v.w)+16, int(v.h)+16), color=(255,255,255)).with_duration(total_dur)
        return CompositeVideoClip(
            [border.with_position(("right","bottom")), v.with_position(("right","bottom"))],
            size=(W,H)
        ).with_duration(total_dur)

    if src_img:
        img = ImageClip(src_img).resized(height=360).with_duration(total_dur)
        border = ColorClip((int(img.w)+16, int(img.h)+16), color=(255,255,255)).with_duration(total_dur)
        return CompositeVideoClip(
            [border.with_position(("right","bottom")), img.with_position(("right","bottom"))],
            size=(W,H)
        ).with_duration(total_dur)

    return ColorClip((1,1), color=(0,0,0)).with_opacity(0).with_duration(total_dur)

def logo_strip():
    elems = []
    x = 36
    for logo in (SOULSTART_LOGO, SSCM_LOGO):
        if os.path.exists(logo):
            clip = ImageClip(logo).resized(height=70).with_position((x, 16)).with_duration(999)
            elems.append(clip)
            x += int(clip.w) + 24
    return elems

def sec_to_srt(ts):
    h = int(ts // 3600); m = int((ts % 3600) // 60); s = int(ts % 60); ms = int((ts - int(ts)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def make_srt(path, clips, texts):
    t, lines = 0.0, []
    for i, clip in enumerate(clips, start=1):
        start, end = t, t + clip.duration
        caption = texts[i-1][1]
        lines.append(f"{i}\n{sec_to_srt(start)} --> {sec_to_srt(end)}\n{caption}\n")
        t = end
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ---------- MAIN ----------
def build_video(args):
    day = args.date or os.getenv("SOULSTART_DATE") or datetime.now(TZ).date().isoformat()
    day_iso = day.isoformat() if isinstance(day, date) else day

    entries = load_json(args.json)
    entry = pick_entry(entries, day_iso)
    if not entry:
        raise SystemExit("No entry found in JSON.")

    verse_ref  = (entry.get("verse_ref") or "").strip()
    verse_text = (entry.get("verse_text") or "").strip()
    reflection = (entry.get("reflection") or "").strip()
    prayer     = (entry.get("prayer") or "").strip()
    pretty_date = fmt_date(datetime.fromisoformat(entry.get("date", day_iso)).date())

    bg = ColorClip((W, H), color=BG_COLOR)

    # Slides
    clips = []

    # 1) Title
    title_txt = f"🌙 SoulStart Sunset — {pretty_date}"
    c1p = text_panel_clip("", title=title_txt, dur=3.5)
    c1  = CompositeVideoClip(
        [bg.with_duration(c1p.duration), c1p.with_position(("center","center"))],
        size=(W,H)
    )
    clips.append(c1)

    # 2) Scripture
    verse_full = f"“{verse_text}”"
    sub = verse_ref
    d2 = dur_for(verse_text, base=5.5)
    c2p = text_panel_clip(verse_full, title="📖 Scripture", subtitle=sub, dur=d2)
    c2  = CompositeVideoClip(
        [bg.with_duration(c2p.duration), c2p.with_position(("center","center"))],
        size=(W,H)
    )
    clips.append(c2)

    # 3) Reflection
    d3 = dur_for(reflection, base=5.0)
    c3p = text_panel_clip(reflection, title="🕊️ Reflection", dur=d3)
    c3  = CompositeVideoClip(
        [bg.with_duration(c3p.duration), c3p.with_position(("center","center"))],
        size=(W,H)
    )
    clips.append(c3)

    # 4) Prayer
    d4 = dur_for(prayer, base=5.0)
    c4p = text_panel_clip(prayer, title="✨ PRAYER", dur=d4)
    c4  = CompositeVideoClip(
        [bg.with_duration(c4p.duration), c4p.with_position(("center","center"))],
        size=(W,H)
    )
    clips.append(c4)

    base = concatenate_videoclips(clips, method="compose")
    total = base.duration

    sign_clip = sign_pip(args.sign, total)
    logos = logo_strip()

    final = CompositeVideoClip([base, sign_clip] + logos, size=(W, H))
    out_mp4 = os.path.join(OUT_DIR, f"sunset_{entry.get('date', day_iso)}.mp4")
    final.write_videofile(out_mp4, fps=FPS, codec="libx264", audio=False, threads=4, preset="medium")

    # SRT captions
    srt_path = os.path.join(OUT_DIR, f"sunset_{entry.get('date', day_iso)}.srt")
    make_srt(srt_path, [c1, c2, c3, c4], [
        ("Title", title_txt),
        ("Scripture", verse_full + (" " + sub if sub else "")),
        ("Reflection", reflection),
        ("Prayer", prayer),
    ])
    print(f"✅ Done: {out_mp4}\n📝 Captions: {srt_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (defaults to local Nassau date or SOULSTART_DATE)")
    ap.add_argument("--json", default=DEFAULT_JSON, help="Path to Sunset JSON")
    ap.add_argument("--sign", default=None, help="Path to sign-language video (mp4)")
    args = ap.parse_args()
    build_video(args)
