"""Telegram bot entry point for TicTocDoc."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telegram import Message, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import Config, DEFAULT_CONFIG
from humour_engine import generate_diagnosis
from tiktok_handler import extract_first_tiktok_url, fetch_tiktok_info


LOGGER = logging.getLogger(__name__)


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tictocdoc commands."""
    if not update.effective_message:
        return

    args = [arg.lower() for arg in context.args]
    if not args or args[0] == "help":
        text = (
            "🩺 TicTocDoc online.\n"
            "Drop a TikTok link and I will issue a very professional diagnosis.\n"
            "Use /snatch in replies to trigger scans in busy chats.\n"
            "Optional subcommands:\n"
            "/tictocdoc help – show this message\n"
            "/tictocdoc mode – list humour presets (coming soon)"
        )
        await update.effective_message.reply_text(text)
        return

    if args[0] == "mode":
        await update.effective_message.reply_text(
            "Modes still incubating. Default mode: deadpan absurdist clinician."
        )
        return

    await update.effective_message.reply_text("Unknown subcommand. Try /tictocdoc help for guidance.")


async def handle_snatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run diagnosis when /snatch is used, preferably in reply to a TikTok."""
    message = update.effective_message
    if not message:
        return

    candidate_messages = [message.reply_to_message, message]
    url = None
    for candidate in candidate_messages:
        if not candidate:
            continue
        candidate_text = candidate.text or candidate.caption or ""
        url = extract_first_tiktok_url(candidate_text)
        if url:
            break

    if not url:
        await message.reply_text("Reply to a TikTok link or include the link after /snatch.")
        return

    await _diagnose_and_respond(message, url, context)


async def handle_private_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-handle TikTok links in private chats or forwarded to the bot."""
    message = update.effective_message
    if not message:
        return
    url = extract_first_tiktok_url((message.text or "") + " " + (message.caption or ""))
    if not url:
        return

    await _diagnose_and_respond(message, url, context)


async def _diagnose_and_respond(message: Message, url: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data.get("config", DEFAULT_CONFIG)
    info = await asyncio.to_thread(fetch_tiktok_info, url, config)

    diagnosis = generate_diagnosis(
        {
            "video_id": info.video_id,
            "title": info.title,
            "uploader": info.uploader,
        }
    )

    extra_lines: list[str] = []
    if info.error:
        extra_lines.append(f"⚠️ Download hiccup: {info.error}")
    if not info.local_file_path:
        extra_lines.append(info.normalized_url)

    payload_text = "\n".join([diagnosis] + extra_lines)

    if info.local_file_path and info.local_file_path.is_file():
        await _send_video_with_caption(message, info.local_file_path, payload_text)
    else:
        await message.reply_text(payload_text)


async def _send_video_with_caption(message: Message, path: Path, caption: str) -> None:
    """Upload a locally downloaded TikTok clip."""
    with path.open("rb") as video_file:
        await message.reply_video(video=video_file, caption=caption)


def build_application(config: Config) -> Application:
    """Create the telegram-application."""
    application = Application.builder().token(config.bot_token).build()
    application.bot_data["config"] = config

    private_filter = filters.ChatType.PRIVATE & (~filters.COMMAND)
    application.add_handler(CommandHandler("tictocdoc", handle_command))
    application.add_handler(CommandHandler("start", handle_command))
    application.add_handler(CommandHandler("snatch", handle_snatch))
    application.add_handler(MessageHandler(private_filter, handle_private_tiktok))
    return application


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    config = DEFAULT_CONFIG
    if not config.bot_token:
        raise SystemExit("Set TICTOCDOC_BOT_TOKEN before running the bot.")

    setup_logging(config.log_level)
    application = build_application(config)
    LOGGER.info("TicTocDoc starting...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
