import json
import random
import sys
from pathlib import Path
from datetime import date
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter


PROJECT_ROOT = Path(__file__).resolve().parents[1]   # .../soulstart
APP_ROOT = PROJECT_ROOT.parent                       # .../SSCM_New

DEVOTION_FILE = APP_ROOT / "devotions" / "devotions_2026.json"
OUTPUT_ROOT = APP_ROOT / "static" / "img" / "devotion" / "hero" / "2026"

# ✅ FIXED PATHS
BACKGROUND_DIR = APP_ROOT / "static" / "img" / "devotion" / "backgrounds"

WIDTH = 1600
HEIGHT = 900

MORNING_GRADIENT = ("#dff6ea", "#8fd3a8", "#2b7a57")
NIGHT_GRADIENT = ("#0f1f3a", "#1f3b73", "#5f7ccf")


def load_json(path: Path) -> list:
    if not path.exists():
        raise FileNotFoundError(f"Devotion JSON not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_devotion(devotions: list, target_date: str) -> Optional[dict]:
    for item in devotions:
        if item.get("date") == target_date:
            return item
    return None


def safe_short_line(text: str, max_len: int = 90) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def get_background_image(target_date):

    # 🔍 DEBUG — put here
    print("BACKGROUND_DIR:", BACKGROUND_DIR)
    print("EXISTS:", BACKGROUND_DIR.exists())
    print("FILES:", list(BACKGROUND_DIR.glob("*")))

    if not BACKGROUND_DIR.exists():
        return None

    images = sorted([
        f for f in BACKGROUND_DIR.glob("*")
        if f.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ])

    print("FILTERED IMAGES:", images)

    if not images:
        return None

    index = int(target_date.split("-")[2]) % len(images)
    selected = images[index]

    print("SELECTED:", selected)

    return selected


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_gradient_background(size: tuple[int, int], mode: str) -> Image.Image:
    width, height = size
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)

    colors = MORNING_GRADIENT if mode == "morning" else NIGHT_GRADIENT
    top = hex_to_rgb(colors[0])
    mid = hex_to_rgb(colors[1])
    bottom = hex_to_rgb(colors[2])

    for y in range(height):
        ratio = y / max(height - 1, 1)
        if ratio < 0.5:
            local = ratio / 0.5
            color = lerp_color(top, mid, local)
        else:
            local = (ratio - 0.5) / 0.5
            color = lerp_color(mid, bottom, local)
        draw.line([(0, y), (width, y)], fill=color)

    return img


def fit_background(bg: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = bg.size

    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / src_ratio)

    bg = bg.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return bg.crop((left, top, left + target_w, top + target_h))


def load_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]

    for path in candidates:
        font_path = Path(path)
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)

    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines = []
    current = words[0]

    for word in words[1:]:
        test = current + " " + word
        bbox = draw.textbbox((0, 0), test, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current = test
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def add_overlay(base: Image.Image, mode: str) -> Image.Image:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if mode == "morning":
        draw.rectangle([0, 0, WIDTH, HEIGHT], fill=(10, 20, 10, 105))
        draw.rounded_rectangle(
            [70, 70, WIDTH - 70, HEIGHT - 70],
            radius=38,
            fill=(255, 255, 255, 20),
            outline=(255, 255, 255, 55),
            width=2,
        )
    else:
        draw.rectangle([0, 0, WIDTH, HEIGHT], fill=(8, 14, 32, 145))
        draw.rounded_rectangle(
            [70, 70, WIDTH - 70, HEIGHT - 70],
            radius=38,
            fill=(255, 255, 255, 14),
            outline=(255, 255, 255, 45),
            width=2,
        )

    return Image.alpha_composite(base.convert("RGBA"), overlay)


def add_text_block(img: Image.Image, record: dict, mode: str) -> Image.Image:
    draw = ImageDraw.Draw(img)

    label_font = load_font(42, bold=True)
    title_font = load_font(74, bold=True)
    verse_font = load_font(34, bold=True)
    line_font = load_font(32, bold=False)
    brand_font = load_font(26, bold=True)

    text_color = (255, 255, 255, 245)
    soft_color = (245, 245, 245, 230)

    x = 120
    y = 120
    content_width = 860

    label = "🌅 Morning Devotion" if mode == "morning" else "🌙 Night Devotion"
    theme = safe_short_line(record.get("theme", "").strip(), 100)
    section = record.get(mode, {}) or {}
    verse_ref = (section.get("verse_ref") or "").strip()
    verse_text = safe_short_line((section.get("verse_text") or "").strip(), 120)

    draw.text((x, y), label, font=label_font, fill=text_color)
    y += 78

    theme_lines = wrap_text(draw, theme, title_font, content_width)
    for line in theme_lines[:2]:
        draw.text((x, y), line, font=title_font, fill=text_color)
        y += 88

    if verse_ref:
        y += 10
        draw.text((x, y), verse_ref, font=verse_font, fill=soft_color)
        y += 54

    if verse_text:
        verse_lines = wrap_text(draw, verse_text, line_font, content_width)
        for line in verse_lines[:2]:
            draw.text((x, y), line, font=line_font, fill=soft_color)
            y += 42

    brand_text = "Silent SoulConnect Ministry"
    date_text = record.get("date", "")
    footer_y = HEIGHT - 100

    draw.text((x, footer_y), brand_text, font=brand_font, fill=soft_color)
    date_bbox = draw.textbbox((0, 0), date_text, font=brand_font)
    date_width = date_bbox[2] - date_bbox[0]
    draw.text((WIDTH - 120 - date_width, footer_y), date_text, font=brand_font, fill=soft_color)

    return img


def generate_devotion_image(target_date: str, mode: str = "morning") -> Path:
    devotions = load_json(DEVOTION_FILE)
    record = find_devotion(devotions, target_date)

    if not record:
        raise ValueError(f"No devotion found for date {target_date}")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_ROOT / f"{target_date}.jpg"

    bg_file = get_background_image(target_date)
    if bg_file and bg_file.exists():
        bg = Image.open(bg_file).convert("RGB")
        bg = fit_background(bg, (WIDTH, HEIGHT))
    else:
        bg = make_gradient_background((WIDTH, HEIGHT), mode)

    bg = bg.filter(ImageFilter.GaussianBlur(radius=1.2))
    img = add_overlay(bg, mode)

    img = img.convert("RGB")
    img.save(out_path, format="JPEG", quality=92, optimize=True)
    return out_path


if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else date.today().strftime("%Y-%m-%d")
    output = generate_devotion_image(target_date, mode="morning")
    print(f"Generated: {output}")