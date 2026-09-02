from PIL import Image, ImageDraw, ImageFont
import os
import logging

logger = logging.getLogger(__name__)

FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "font.ttf")


async def process_watermark(bot, file, watermark_text: str, unique_id: str) -> str:
    os.makedirs("downloads", exist_ok=True)
    dest = f"downloads/{unique_id}.jpg"
    await bot.download_file(file.file_path, dest)

    base = Image.open(dest).convert("RGBA")
    txt_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))

    try:
        font = ImageFont.truetype(FONT_PATH, 36)
    except (IOError, OSError):
        logger.warning("font.ttf not found, falling back to default font")
        font = ImageFont.load_default()

    tile = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((10, 30), watermark_text, font=font, fill=(255, 255, 255, 80))
    tile = tile.rotate(30, expand=True)

    for y in range(-100, base.height, 150):
        for x in range(-100, base.width, 250):
            txt_layer.paste(tile, (x, y), tile)

    out = Image.alpha_composite(base, txt_layer).convert("RGB")
    out_path = dest.replace(".jpg", "_wm.jpg")
    out.save(out_path, quality=95)
    return out_path
