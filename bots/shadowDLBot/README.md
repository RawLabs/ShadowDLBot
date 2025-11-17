# TGbots Downloader Bot

A lightweight Telegram bot that downloads size‑constrained public videos using `yt-dlp` and sends them back from the bot account. It enforces strict duration/height/file-size rules and automatically re-encodes large downloads to stay under Telegram's 50 MB bot limit.

## Requirements
- Python 3.10+
- `ffmpeg` available on `PATH`
- Python packages listed in `requirements.txt` (inside this folder)

## Setup
```bash
cd /home/ghost/TGbots
python -m venv bots-env
source bots-env/bin/activate
cd bots/shadowDLBot
pip install --upgrade pip
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="1234567890:ABC..."
```

## Running the bot
```bash
cd /home/ghost/TGbots/bots/shadowDLBot
python main.py
```

## Commands
- `/start` – usage instructions.
- `/grab` – reply to a message that contains a public video link; downloads a <=360p copy, transcodes if required, then replies with the video + stats.
- `/stats` – prints cumulative totals for the current process.
- `/override <passcode>` – DM-only command for trusted users to bypass duration limits.

All temporary media is stored in `tmp/` under this folder and is removed after every successful upload.

## Downloader helper
`downloader/core.py` exposes `download_video(url, allow_long=False)` which performs host validation, metadata extraction, conservative format selection, soft/hard file-size enforcement, and optional `ffmpeg` transcodes to keep the final upload under ~49 MB. Other projects can import and reuse this helper.

## Testing / development tips
- Run the bot inside the shared `bots-env` virtual environment so it can access all dependencies and env vars.
- Use a test Telegram chat and reply to a message containing a video link when issuing `/grab`.
- Watch the console logs—the bot logs every download attempt, including resulting file sizes, which is helpful for diagnosing timeout issues.
