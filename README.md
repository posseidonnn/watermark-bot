# Watermark Bot

Telegram bot that watermarks images before posting them to your channel.

## Setup

1. **Font**: Place a `.ttf` font file named `font.ttf` in the project root.
   A good free option: [Roboto Bold](https://fonts.google.com/specimen/Roboto) — download `Roboto-Bold.ttf` and rename it.

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure**:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

4. **Bot permissions**: Add the bot to your channel as an **admin** with the
   "Post Messages" permission.

5. **Run**:
   ```bash
   python bot.py
   ```

## Systemd (Ubuntu VPS)

Create `/etc/systemd/system/watermark-bot.service`:

```ini
[Unit]
Description=Watermark Bot
After=network.target

[Service]
WorkingDirectory=/path/to/watermark-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
EnvironmentFile=/path/to/watermark-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now watermark-bot
```

## Usage

Send a photo (or multiple photos) directly to the bot to start the post flow.

| Command   | Description             |
|-----------|-------------------------|
| `/cancel` | Cancel the current flow |

### Post flow

1. Send one or more photos — you can send them all at once or one by one.
2. Use **➕ Add photo** to add more, or **✅ Done** when finished.
3. Send a caption, or use the buttons:
   - **⏭ Skip Caption** — posts without a caption.
   - **📋 Use Default Caption** — uses the `DEFAULT_CAPTION` value from `.env`.
4. Tap **Post to channel** on the preview to publish.

### Caption formatting

Every caption — whether typed manually or using the default — is automatically
posted with **bold**, _italic_, and blockquote formatting. You do not need to
apply any formatting yourself; just type plain text.

### Default caption

Set `DEFAULT_CAPTION` in `.env` to any plain text string:

```
DEFAULT_CAPTION=Follow us for more content!
```

When you tap **📋 Use Default Caption**, this text is used and automatically
formatted as bold + italic + blockquote. If `DEFAULT_CAPTION` is not set, the
button will not appear.
