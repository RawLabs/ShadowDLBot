# TGbots Downloader Bot

This repository contains a lightweight Telegram bot that downloads size‑constrained public videos using `yt-dlp` and then serves them back from the bot account. The implementation enforces strict duration/height/file-size rules and automatically re-encodes large downloads so they stay below Telegram's 50 MB bot limit.

## Requirements

- Python 3.10+
- `ffmpeg` available on `PATH` (used for the post-download transcode step)
- The Python packages listed in `requirements.txt`

## Setup

```bash
python -m venv bots-env
source bots-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Export your bot token before running:

```bash
export TELEGRAM_BOT_TOKEN="1234567890:ABC..."
```

## Running the bot

```bash
python -m shadowDLBot.main
```

The bot exposes the following commands:

- `/start` – show usage instructions.
- `/grab` – **must** be sent as a reply to a message containing a public video link. The bot validates the URL, downloads a <=360p version, transcodes it if necessary, and replies with the file plus stats.
- `/stats` – prints cumulative totals per platform for the current process.

All temporary media is stored in `tmp/` and is removed after each successful upload. Counters are kept in memory only (they reset when the process restarts).

## Downloader module

`downloader/core.py` exposes `download_video(url)` which performs:

1. Host validation using `downloader/config.py`.
2. Metadata extraction via `yt-dlp`.
3. Format selection (MP4, 240‑360p, H.264/AAC).
4. Enforced duration, height, soft/hard byte limits.
5. Optional ffmpeg transcode to keep the final size under ~49 MB for Telegram uploads.

You can import and reuse this helper outside the bot if desired.

## Testing / Development Tips

- Run the bot inside the virtual environment so it can access the installed dependencies and environment variables.
- Use a test Telegram chat and reply to a message containing a video link when issuing `/grab`.
- Watch the console logs; the bot logs every download attempt, including the file size it is about to upload, which is helpful when diagnosing timeout issues.
