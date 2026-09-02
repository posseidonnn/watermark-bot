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

| Command   | Description              |
|-----------|--------------------------|
| `/post`   | Start the post flow      |
| `/cancel` | Cancel the current flow  |
