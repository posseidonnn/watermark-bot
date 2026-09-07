from PIL import Image, ImageChops, ImageDraw, ImageFont
import os
import logging

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
# thin/regular weight matches the reference watermark better than the bold cut
FONT_CANDIDATES = [
    os.path.join(_BASE_DIR, "Gotham Regular.otf"),
    os.path.join(_BASE_DIR, "font.ttf"),
]

# --- watermark look ---
# Every size below is a fraction of the image's "reference size": the geometric
# mean of width and height, i.e. the side of a square with the same area. Using
# that instead of the width makes the mark identical on a portrait, landscape,
# or square crop of the same resolution, and keeps it proportional from 720p to
# 4K. Scaling off the width alone would make text on a 1080x1920 portrait
# noticeably smaller than on a 1920x1080 landscape.
FONT_SCALE = 0.0125       # cap height of the text
MIN_FONT_SIZE = 8
TRACKING_SCALE = 0.38     # extra space between letters, as a fraction of font size
STEP_X_SCALE = 0.35       # horizontal distance between repeats
STEP_Y_SCALE = 0.25       # vertical distance between repeats
ROW_OFFSET = 0.5          # every other row is shifted by half a step (staggered grid)
UPPERCASE = True

# The mark is drawn as a light glyph wrapped in a dark hairline outline. The
# light part carries it on dark photos, the dark outline carries it on light
# photos, so it never disappears on either. Both are low enough to read as
# texture at normal zoom.
LIGHT_COLOR = (255, 255, 255)
LIGHT_OPACITY = 30        # 0-255
DARK_COLOR = (0, 0, 0)
DARK_OPACITY = 26         # 0-255
OUTLINE_SCALE = 0.10      # outline thickness as a fraction of font size (min 1px)


def _reference_size(width: int, height: int) -> float:
    """Aspect-ratio-independent scale basis: the side of an equal-area square."""
    return (width * height) ** 0.5


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    logger.warning("no bundled font found, falling back to default font")
    return ImageFont.load_default(size=size)


def _tracked_width(text: str, font: ImageFont.FreeTypeFont, tracking: float) -> float:
    if not text:
        return 0.0
    return sum(font.getlength(ch) for ch in text) + tracking * (len(text) - 1)


def _draw_tracked_text(draw: ImageDraw.ImageDraw, xy, text, font, tracking: float, stroke_width: int = 0):
    """Draw text one glyph at a time onto an 8-bit mask so we can add letter spacing."""
    x, y = xy
    for ch in text:
        draw.text(
            (x, y), ch, font=font, fill=255,
            stroke_width=stroke_width, stroke_fill=255,
        )
        x += font.getlength(ch) + tracking


def _build_mask(size, text, font, tracking, step_x, step_y, stroke_width) -> Image.Image:
    """Full-coverage tiled mask of the watermark text, 255 where ink lands."""
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    row = 0
    y = -step_y
    while y < height + step_y:
        x = -step_x + int(step_x * ROW_OFFSET) * (row % 2)
        while x < width + step_x:
            _draw_tracked_text(draw, (x, y), text, font, tracking, stroke_width)
            x += step_x
        y += step_y
        row += 1

    return mask


def _tint(mask: Image.Image, color, opacity: int) -> Image.Image:
    """Turn a coverage mask into a flat colour layer at the given opacity."""
    layer = Image.new("RGBA", mask.size, color + (0,))
    layer.putalpha(mask.point(lambda v: v * opacity // 255))
    return layer


def apply_watermark(base: Image.Image, watermark_text: str) -> Image.Image:
    """Tile a faint, letter-spaced, horizontal watermark across the whole image."""
    base = base.convert("RGBA")
    width, height = base.size

    text = watermark_text.upper() if UPPERCASE else watermark_text
    if not text.strip():
        return base

    ref = _reference_size(width, height)
    font_size = max(MIN_FONT_SIZE, int(ref * FONT_SCALE))
    tracking = font_size * TRACKING_SCALE
    font = _load_font(font_size)
    stroke_width = max(1, round(font_size * OUTLINE_SCALE))

    text_w = _tracked_width(text, font, tracking)
    ascent, descent = font.getmetrics()
    text_h = ascent + descent

    step_x = max(int(text_w * 1.35), int(ref * STEP_X_SCALE))
    step_y = max(int(text_h * 2.0), int(ref * STEP_Y_SCALE))

    args = (base.size, text, font, tracking, step_x, step_y)
    body = _build_mask(*args, 0)
    # outline only, so the dark hairline never sits underneath the light glyph
    outline = ImageChops.subtract(_build_mask(*args, stroke_width), body)

    out = Image.alpha_composite(base, _tint(outline, DARK_COLOR, DARK_OPACITY))
    out = Image.alpha_composite(out, _tint(body, LIGHT_COLOR, LIGHT_OPACITY))
    return out


async def process_watermark(bot, file, watermark_text: str, unique_id: str) -> str:
    os.makedirs("downloads", exist_ok=True)
    dest = f"downloads/{unique_id}.jpg"
    await bot.download_file(file.file_path, dest)

    with Image.open(dest) as base:
        out = apply_watermark(base, watermark_text).convert("RGB")

    out_path = dest.replace(".jpg", "_wm.jpg")
    out.save(out_path, quality=95)
    return out_path
