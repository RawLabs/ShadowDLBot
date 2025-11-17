# TicTocDoc

Absurdist TikTok triage bot for Telegram chats. Drop a TikTok link, get a mock-clinical report and optionally the clip itself.

## Features

- Detects TikTok URLs in chat text or captions.
- Probes metadata with `yt-dlp` and (optionally) downloads the clip to relay.
- Generates deterministic “doctor” responses from curated word pools and templates.
- Keeps components modular: Telegram wiring, TikTok handler, humour engine, and configuration live in separate modules.

## Requirements

- Python 3.10+
- `python-telegram-bot` v20 (asyncio based)
- `yt-dlp` available as a module or CLI executable.

Install dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Environment variables drive the runtime:

| Variable | Purpose | Default |
| --- | --- | --- |
| `TICTOCDOC_BOT_TOKEN` | Telegram bot token | **required** |
| `TICTOCDOC_DOWNLOADS` | `1` to download clips, `0` for diagnosis-only mode | `1` |
| `TICTOCDOC_TEMP_DIR` | Directory to store temporary downloads | `/tmp` |
| `TICTOCDOC_LOG_LEVEL` | Logging level | `INFO` |
| `TICTOCDOC_YT_DLP` | Custom path to `yt-dlp` CLI if module import fails | `yt-dlp` |

## Running

```bash
export TICTOCDOC_BOT_TOKEN=123456:ABCDEF
python bot_main.py
```

Telegram usage:

- In private chats (or when forwarding a message to the bot), simply send a TikTok link and it will respond.
- In busy group chats, reply to a TikTok message with `/snatch` (or send `/snatch https://...`) to trigger a diagnosis on demand.
- `/tictocdoc help` – feature overview.
- `/tictocdoc mode` – placeholder for future humour settings.

## Project Structure

- `bot_main.py` – Telegram wiring and handlers.
- `config.py` – environment-driven configuration helpers.
- `humour_engine.py` – deterministic absurdist copy generator.
- `tiktok_handler.py` – URL detection, normalization, and `yt-dlp` plumbing.

Tune the word pools or templates directly inside `humour_engine.py` to reshape the persona without touching core logic.
