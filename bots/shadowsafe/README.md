# ShadowSafe

ShadowSafe is a privacy-first Telegram bot concept that inspects shared files for structural red flags and metadata leaks. This repo only contains the scaffolding, contracts, and design notes so future implementations stay aligned.

## Directory layout

```
bot/                # Telegram entry + handlers (no logic yet)
scanner/            # File analysis contracts per type
config/             # Example settings (no secrets)
logs/               # Runtime log target (empty placeholder)
tests/              # Placeholder tests referencing scanner modules
README.md           # Project overview (this file)
requirements.txt    # Dependency placeholder
```

## Scanner contracts

`scanner.core` defines a `ScanResult` dataclass returned by `scan_file(path, mime_hint=None)` with these notable fields:

- `file_name`, `size_bytes`, `detected_type`
- `extension_mismatch` (details string when mismatched)
- `hashes` containing at least `sha256` and `md5`
- `blocklist_hits` list
- `issues` list of `{severity, category, message}`
- `risk_score` integer (0-100) summarizing severity
- `metadata_summary` (EXIF, GPS, timestamps)
- `can_sanitize` + `sanitized_file_path`
- `per_scanner_details` storing module-specific findings

Each type-specific module (`pdf_scanner`, `image_scanner`, `video_scanner`, `archive_scanner`) receives the file path and returns a dict tailored to that medium. The orchestrator consults `filetype_registry` to decide which modules to run, `hash_checker` for fingerprints/blocklists, `metadata_utils` for privacy metadata, `yara_scanner` for signature hits, and `heuristics` for entropy/trailing-data analysis. Optional sanitizers can supply cleaned copies.

## Telegram flow (bot/main.py & bot/handlers.py)

1. Parse config from `config/settings.toml` (copy from `.example`) and read secrets from environment variables only.
2. Start the Telegram client, register `/start`, `/help`, `/privacy`, `/about`, and `/inspect`.
3. Handle chats differently based on context.

### Private chats (DMs)

- `/start` triggers a welcome/help message describing privacy rules and usage.
- Any file sent directly to the bot should be downloaded, scanned, and answered with the formatted report (no `/inspect` required).
- `/inspect` in DM can respond with a hint such as “just send me a file”.

### Groups/channels

- The bot must remain passive. Only act when `/inspect` is used as a reply to a message that already contains a file (document/photo/video/animation).
- Flow for `/inspect`:
  1. Ensure `message.reply_to_message` exists.
  2. Verify the replied message carries a supported file.
  3. If validations fail, respond: “Reply to a message with a file and send /inspect to analyze it.”
  4. Otherwise download the original file, run `scanner.core.scan_file()`, and post the report as a reply (either to the command or the original file message).
- Ignore all other files posted in the group when no command is used.

### Report formatting and cleanup

- Reports should follow the sample layout:
  > **ShadowSafe Report**\n>
  > File: `video.mov` (23.4 MB)\n>
  > Type: `video/mp4` (extension matches)\n>
  > Hash: SHA256 <shortened> (no blocklist hits)\n>
  > **Privacy**\n>
  > • EXIF: none\n>
  > • GPS: none\n>
  > **Structure**\n>
  > • Container atoms OK\n>
  > • No appended payload\n>
  > Overall: 🟢 Low risk indicators. No guarantees.
- Attach sanitized copy if `scan_result.can_sanitize` and feature enabled.
- Delete temp + sanitized files immediately after sending (or after a short configurable delay).

## Privacy & peace-of-mind rules

These rules go both in the README and the eventual `/about` command:

- Never store file contents; only optional metadata logs are allowed.
- Optional logs can only contain timestamp, file size, detected type, and verdict color.
- Do not upload files to third-party scanners by default. Hash-only lookups are acceptable.
- Delete downloaded files and sanitized copies promptly after processing.
- Communicate clearly that ShadowSafe cannot guarantee safety—only checks for common structural issues.

## Config expectations

`config/settings.example.toml` documents non-secret knobs such as `log_retention_days`, `max_file_size_mb`, `enable_sanitized_copy`, remote blocklist URLs, and privacy toggles. Real secrets (`BOT_TOKEN`, proxies) must stay in environment variables.

## Testing placeholders

`tests/` contains stub modules (`test_scanner_core.py`, `test_pdf_scanner.py`, etc.) that outline the future coverage. Once scanning logic exists, convert those `NotImplementedError` stubs into real tests.

## Instruction pack for future Codex

When ready to implement:

1. Install dependencies via `pip install -r requirements.txt` (includes `python-telegram-bot`, `pikepdf`, `oletools`, `yara-python`, `mutagen`).
2. Run the bot with `python -m ShadowSafe.bot.main` after exporting `SHADOWSAFE_BOT_TOKEN`.
3. Build `scanner/core.py` to orchestrate helpers and return a populated `ScanResult` dict/datatclass.
4. Flesh out each module in `scanner/` (`hash_checker`, `metadata_utils`, per-type scanners, optional `sanitizers`).
5. Load config via TOML using `config/settings.example.toml` as template (copy to `config/settings.toml`).
6. Add tests exercising scanner logic independent from Telegram integrations.

With this scaffolding, future coding sessions can concentrate entirely on implementation details without rehashing structure or privacy requirements.
