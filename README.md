# TGbots Workspace

A single workspace for multiple Telegram bots plus their helper scripts. Each bot now lives in its own folder so you can focus on one project at a time without digging through unrelated files.

## Layout
- `bots/` – all bot projects. Each folder contains its own code, docs, and supporting files.
  - `shadowDLBot/` – Downloader bot + `downloader/` helper, tmp directory, requirements, and tests (see `bots/shadowDLBot/README.md`).
  - `shadowpi/` – CAS-aware moderator bot (see `bots/shadowpi/README.md`) with `shadowpi_data/` alongside for the SQLite DB.
  - `shadowpi_data/` – persistent data directory used by ShadowPI (keep the path mounted when deploying).
  - `shadowsafe/` – ShadowSafe project files.
  - `tictocdoc/` – other TikTok tooling/bot.
  - `transkrypt/` – transcript-to-PDF bot built in this session (see `bots/transkrypt/README.md`).
- `bots-env/` – shared Python virtual environment for local development.
- `media/` – loose downloads (captions, mp4s) that don't belong to a specific bot yet.
- `shared/` – staging area for future shared utilities. (Currently empty.)

## Working on a Bot
1. Activate the shared environment (only once per shell):
   ```bash
   source bots-env/bin/activate
   ```
2. Change into the bot folder you want (e.g. `cd bots/transkrypt`).
3. Follow that bot's README for setup, env vars, and run commands.

Each bot keeps its own requirements/documentation so they can evolve independently. When you add a new bot, drop it under `bots/` and update this README with a short description.

## Starting every bot at once
1. Copy `.env.example` to `.env` and paste the real tokens:
   ```bash
   cp .env.example .env
   # edit .env with your SHADOWDL/SHADOWPI/TRANSKRYPT/SHADOWSAFE/TICTOCDOC tokens
   ```

Prefer not to store tokens on disk? Export them for the current shell only:

```bash
export SHADOWDL_TELEGRAM_BOT_TOKEN=...
export SHADOWPI_BOT_TOKEN=...
export TRANSKRYPT_TELEGRAM_BOT_TOKEN=...
export SHADOWSAFE_BOT_TOKEN=...
export TICTOCDOC_BOT_TOKEN=...
python scripts/start_all.py
```

2. Activate the shared venv and install each bot's requirements (once).
3. Launch all bots (runs them in parallel and writes logs to `./logs/<bot>.log`):
   ```bash
   source bots-env/bin/activate
   python scripts/start_all.py
   ```
   Press `Ctrl+C` to stop every process cleanly. To run a single bot, `cd` into its folder and start it manually as documented in its README.


## Monitoring logs the easy way
Run `python scripts/watch_logs.py` (add `--show-http` if you really want Telegram polling noise). The watcher tails every `logs/*.log`, filters out the httpx chatter, and colorizes warnings/errors so issues stand out immediately.
