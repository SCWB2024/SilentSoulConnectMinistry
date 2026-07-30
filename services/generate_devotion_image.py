import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# =========================================================
# PATHS
# =========================================================

APP_ROOT = Path(__file__).resolve().parents[1]

DEVOTION_FILE = APP_ROOT / "devotions" / "devotions_2026.json"
BACKGROUND_DIR = APP_ROOT / "static" / "img" / "devotion" / "backgrounds"
OUTPUT_ROOT = APP_ROOT / "static" / "img" / "devotion" / "hero"

# =========================================================
# IMAGE SETTINGS
# =========================================================

WIDTH = 1600
HEIGHT = 900

MORNING_GRADIENT = (
    "#dff6ea",
    "#8fd3a8",
    "#2b7a57",
)

NIGHT_GRADIENT = (
    "#0f1f3a",
    "#1f3b73",
    "#5f7ccf",
)


# =========================================================
# JSON
# =========================================================

def load_json(path: Path) -> list:
    if not path.exists():
        raise FileNotFoundError(
            f"Devotion JSON not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            "Devotion JSON must contain a list of devotion records."
        )

    return data


def find_devotion(
    devotions: list,
    target_date: str,
) -> Optional[dict]:

    for item in devotions:
        if item.get("date") == target_date:
            return item

    return None


# =========================================================
# TEXT HELPERS
# =========================================================

def safe_short_line(
    text: str,
    max_len: int = 90,
) -> str:

    text = (text or "").strip()

    if len(text) <= max_len:
        return text

    return text[: max_len - 1].rstrip() + "…"


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
) -> list[str]:

    words = (text or "").split()

    if not words:
        return []

    lines = []
    current = words[0]

    for word in words[1:]:
        test_line = f"{current} {word}"

        box = draw.textbbox(
            (0, 0),
            test_line,
            font=font,
        )

        line_width = box[2] - box[0]

        if line_width <= max_width:
            current = test_line
        else:
            lines.append(current)
            current = word

    lines.append(current)

    return lines


# =========================================================
# BACKGROUND
# =========================================================

def get_background_image(
    target_date: str,
) -> Optional[Path]:

    if not BACKGROUND_DIR.exists():
        print(
            f"Background folder not found: "
            f"{BACKGROUND_DIR}"
        )
        return None

    images = sorted(
        file
        for file in BACKGROUND_DIR.rglob("*")
        if file.is_file()
        and file.suffix.lower()
        in {".jpg", ".jpeg", ".png", ".webp"}
    )

    if not images:
        print(
            f"No background images found in: "
            f"{BACKGROUND_DIR}"
        )
        return None

    target_day = date.fromisoformat(target_date)

    day_index = target_day.toordinal() % len(images)

    return images[day_index]


def hex_to_rgb(
    value: str,
) -> tuple[int, int, int]:

    value = value.lstrip("#")

    return tuple(
        int(value[index:index + 2], 16)
        for index in (0, 2, 4)
    )


def lerp_color(
    first: tuple[int, int, int],
    second: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:

    return tuple(
        int(
            first[index]
            + (second[index] - first[index]) * ratio
        )
        for index in range(3)
    )


def make_gradient_background(
    size: tuple[int, int],
    mode: str,
) -> Image.Image:

    width, height = size

    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)

    colors = (
        MORNING_GRADIENT
        if mode == "morning"
        else NIGHT_GRADIENT
    )

    top = hex_to_rgb(colors[0])
    middle = hex_to_rgb(colors[1])
    bottom = hex_to_rgb(colors[2])

    for y in range(height):
        ratio = y / max(height - 1, 1)

        if ratio < 0.5:
            color = lerp_color(
                top,
                middle,
                ratio / 0.5,
            )
        else:
            color = lerp_color(
                middle,
                bottom,
                (ratio - 0.5) / 0.5,
            )

        draw.line(
            [(0, y), (width, y)],
            fill=color,
        )

    return image


def fit_background(
    background: Image.Image,
    size: tuple[int, int],
) -> Image.Image:

    target_width, target_height = size
    source_width, source_height = background.size

    source_ratio = source_width / source_height
    target_ratio = target_width / target_height

    if source_ratio > target_ratio:
        new_height = target_height
        new_width = int(
            new_height * source_ratio
        )
    else:
        new_width = target_width
        new_height = int(
            new_width / source_ratio
        )

    background = background.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS,
    )

    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2

    return background.crop(
        (
            left,
            top,
            left + target_width,
            top + target_height,
        )
    )


# =========================================================
# FONTS
# =========================================================

def load_font(
    size: int,
    bold: bool = False,
):
    candidates = [
        (
            "C:/Windows/Fonts/arialbd.ttf"
            if bold
            else "C:/Windows/Fonts/arial.ttf"
        ),
        (
            "C:/Windows/Fonts/segoeuib.ttf"
            if bold
            else "C:/Windows/Fonts/segoeui.ttf"
        ),
        (
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans-Bold.ttf"
            if bold
            else
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans.ttf"
        ),
    ]

    for candidate in candidates:
        font_path = Path(candidate)

        if font_path.exists():
            return ImageFont.truetype(
                str(font_path),
                size=size,
            )

    return ImageFont.load_default()


# =========================================================
# OVERLAY
# =========================================================

def add_overlay(
    base: Image.Image,
    mode: str,
) -> Image.Image:

    overlay = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(overlay)

    if mode == "morning":
        dark_fill = (10, 20, 10, 105)
        card_fill = (255, 255, 255, 22)
        card_outline = (255, 255, 255, 60)
    else:
        dark_fill = (8, 14, 32, 150)
        card_fill = (255, 255, 255, 14)
        card_outline = (255, 255, 255, 45)

    draw.rectangle(
        [0, 0, WIDTH, HEIGHT],
        fill=dark_fill,
    )

    draw.rounded_rectangle(
        [70, 70, WIDTH - 70, HEIGHT - 70],
        radius=38,
        fill=card_fill,
        outline=card_outline,
        width=2,
    )

    return Image.alpha_composite(
        base.convert("RGBA"),
        overlay,
    )


# =========================================================
# TEXT
# =========================================================

def add_text_block(
    image: Image.Image,
    record: dict,
    mode: str,
) -> Image.Image:

    draw = ImageDraw.Draw(image)

    label_font = load_font(42, bold=True)
    title_font = load_font(74, bold=True)
    verse_font = load_font(34, bold=True)
    verse_text_font = load_font(32)
    brand_font = load_font(26, bold=True)

    main_color = (255, 255, 255, 245)
    soft_color = (245, 245, 245, 230)

    x = 120
    y = 120
    content_width = 900

    section = record.get(mode, {}) or {}

    label = (
        "Morning Devotion"
        if mode == "morning"
        else "Night Devotion"
    )

    theme = safe_short_line(
        record.get("theme", ""),
        100,
    )

    verse_ref = (
        section.get("verse_ref")
        or record.get("verse_ref")
        or ""
    ).strip()

    verse_text = safe_short_line(
        section.get("verse_text")
        or record.get("verse_text")
        or "",
        125,
    )

    draw.text(
        (x, y),
        label,
        font=label_font,
        fill=main_color,
    )

    y += 80

    theme_lines = wrap_text(
        draw,
        theme,
        title_font,
        content_width,
    )

    for line in theme_lines[:2]:
        draw.text(
            (x, y),
            line,
            font=title_font,
            fill=main_color,
        )
        y += 88

    if verse_ref:
        y += 12

        draw.text(
            (x, y),
            verse_ref,
            font=verse_font,
            fill=soft_color,
        )

        y += 56

    if verse_text:
        verse_lines = wrap_text(
            draw,
            verse_text,
            verse_text_font,
            content_width,
        )

        for line in verse_lines[:3]:
            draw.text(
                (x, y),
                line,
                font=verse_text_font,
                fill=soft_color,
            )
            y += 43

    brand_text = "Silent SoulConnect Ministry"
    date_text = record.get("date", "")

    footer_y = HEIGHT - 100

    draw.text(
        (x, footer_y),
        brand_text,
        font=brand_font,
        fill=soft_color,
    )

    date_box = draw.textbbox(
        (0, 0),
        date_text,
        font=brand_font,
    )

    date_width = date_box[2] - date_box[0]

    draw.text(
        (
            WIDTH - 120 - date_width,
            footer_y,
        ),
        date_text,
        font=brand_font,
        fill=soft_color,
    )

    return image


# =========================================================
# GENERATOR
# =========================================================

def generate_devotion_image(
    target_date: str,
) -> Path:
    """
    Generate one devotion image for the selected date.

    The same image is used for both morning and night.
    Night mode is created on the website with a darker CSS overlay.
    """

    try:
        date.fromisoformat(target_date)

    except ValueError as exc:
        raise ValueError(
            "Date must use YYYY-MM-DD format."
        ) from exc

    devotions = load_json(
        DEVOTION_FILE
    )

    record = find_devotion(
        devotions,
        target_date,
    )

    if not record:
        raise ValueError(
            f"No devotion found for date {target_date}"
        )

    year = target_date[:4]

    year_output_directory = (
        OUTPUT_ROOT / year
    )

    year_output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        year_output_directory
        / f"{target_date}.jpg"
    )

    # Do not regenerate the image if it already exists.
    if output_path.exists():
        return output_path

    background_file = get_background_image(
        target_date
    )

    if (
        background_file
        and background_file.exists()
    ):
        with Image.open(background_file) as source:
            background = source.convert("RGB")

        background = fit_background(
            background,
            (WIDTH, HEIGHT),
        )

    else:
        # Create one normal daytime image.
        # Night styling will be handled by CSS.
        background = make_gradient_background(
            (WIDTH, HEIGHT),
            "morning",
        )

    background = background.filter(
        ImageFilter.GaussianBlur(
            radius=1.2
        )
    )

    image = add_overlay(
        background,
        "morning",
    )

    image = add_text_block(
        image,
        record,
        "morning",
    )

    image = image.convert("RGB")

    image.save(
        output_path,
        format="JPEG",
        quality=92,
        optimize=True,
    )

    return output_path

# =========================================================
# COMMAND-LINE TEST
# =========================================================

if __name__ == "__main__":
    target_date = (
        sys.argv[1]
        if len(sys.argv) > 1
        else date.today().isoformat()
    )

    mode = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "morning"
    )

    output = generate_devotion_image(
        target_date,
        mode,
    )

    print(f"Generated: {output}")