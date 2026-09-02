import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")  # optional — leave unset for private channels
WATERMARK_TEXT = os.environ.get("WATERMARK_TEXT", f"@{CHANNEL_USERNAME}" if CHANNEL_USERNAME else "")
ADMIN_IDS = {int(i) for i in os.environ["ADMIN_IDS"].split(",")}
