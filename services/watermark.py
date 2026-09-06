from PIL import Image, ImageDraw, ImageFont
import os
import logging

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
# thin/regular weight matches the reference watermark better than the bold cut
FONT_CANDIDATES = [
    os.path.join(_BASE_DIR, "Gotham Regular.otf"),
    os.path.join(_BASE_DIR, "font.ttf"),
]

# --- watermark look (all sizes are fractions of the image width, so the
# --- result looks identical on a 720p photo and a 4K one) ---
FONT_SCALE = 0.026        # cap height of the text
TRACKING_SCALE = 0.30     # extra space between letters, as a fraction of font size
OPACITY = 48              # 0-255. reference watermark is barely there
STEP_X_SCALE = 0.46       # horizontal distance between repeats
STEP_Y_SCALE = 0.33       # vertical distance between repeats
ROW_OFFSET = 0.5          # every other row is shifted by half a step (staggered grid)
UPPERCASE = True


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    logger.warning("no bundled font found, falling back to default font")
    return ImageFont.load_default(size=size)


def _draw_tracked_text(draw: ImageDraw.ImageDraw, xy, text, font, fill, tracking: float):
    """Draw text one glyph at a time so we can add letter spacing."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking


def _tracked_width(text: str, font: ImageFont.FreeTypeFont, tracking: float) -> float:
    if not text:
        return 0.0
    return sum(font.getlength(ch) for ch in text) + tracking * (len(text) - 1)


def apply_watermark(base: Image.Image, watermark_text: str) -> Image.Image:
    """Tile a faint, letter-spaced, horizontal watermark across the whole image."""
    base = base.convert("RGBA")
    width, height = base.size

    text = watermark_text.upper() if UPPERCASE else watermark_text
    if not text.strip():
        return base

    font_size = max(11, int(width * FONT_SCALE))
    tracking = font_size * TRACKING_SCALE
    font = _load_font(font_size)

    text_w = _tracked_width(text, font, tracking)
    ascent, descent = font.getmetrics()
    text_h = ascent + descent

    step_x = max(int(text_w * 1.35), int(width * STEP_X_SCALE))
    step_y = max(int(text_h * 2.0), int(width * STEP_Y_SCALE))

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    fill = (255, 255, 255, OPACITY)

    row = 0
    y = -step_y
    while y < height + step_y:
        x_start = -step_x + int(step_x * ROW_OFFSET) * (row % 2)
        x = x_start
        while x < width + step_x:
            _draw_tracked_text(draw, (x, y), text, font, fill, tracking)
            x += step_x
        y += step_y
        row += 1

    return Image.alpha_composite(base, layer)


async def process_watermark(bot, file, watermark_text: str, unique_id: str) -> str:
    os.makedirs("downloads", exist_ok=True)
    dest = f"downloads/{unique_id}.jpg"
    await bot.download_file(file.file_path, dest)

    with Image.open(dest) as base:
        out = apply_watermark(base, watermark_text).convert("RGB")

    out_path = dest.replace(".jpg", "_wm.jpg")
    out.save(out_path, quality=95)
    return out_path
