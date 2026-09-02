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
    width, height = base.size

    # scale everything relative to image width so watermark density/size
    # looks consistent regardless of the source photo's resolution
    font_size = max(18, int(width * 0.030))
    fill_alpha = 75
    tile_w, tile_h = int(width * 0.30), int(width * 0.10)
    spacing_x, spacing_y = int(width * 0.50), int(width * 0.30)

    txt_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except (IOError, OSError):
        logger.warning("font.ttf not found, falling back to default font")
        font = ImageFont.load_default(size=font_size)

    tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text(
        (tile_w * 0.05, tile_h * 0.35), watermark_text, font=font, fill=(255, 255, 255, fill_alpha)
    )
    # angle=0 keeps text horizontal

    for y in range(-spacing_y, height, spacing_y):
        for x in range(-spacing_x, width, spacing_x):
            txt_layer.paste(tile, (x, y), tile)

    out = Image.alpha_composite(base, txt_layer).convert("RGB")
    out_path = dest.replace(".jpg", "_wm.jpg")
    out.save(out_path, quality=95)
    return out_path
