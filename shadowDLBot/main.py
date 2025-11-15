"""Telegram bot that ties into the downloader package."""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from telegram import InputFile, Update
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from downloader.core import DownloadValidationError, download_video

logger = logging.getLogger(__name__)

TOTAL_DOWNLOADS = 0
PLATFORM_COUNTS = Counter()
URL_REGEX = r"https?://\S+"


def _extract_url_from_replied_message(update: Update) -> Optional[str]:
    """Pull the first URL from the replied-to message."""

    message = update.message
    if not message or not message.reply_to_message:
        return None

    replied = message.reply_to_message
    for attr in ("text", "caption"):
        content = getattr(replied, attr, None)
        if not content:
            continue
        match = re.search(URL_REGEX, content)
        if match:
            return match.group(0)
    return None


def _sorted_platform_counts() -> list[tuple[str, int]]:
    return sorted(
        PLATFORM_COUNTS.items(),
        key=lambda item: (-item[1], item[0]),
    )


def _format_duration(duration: int | float) -> str:
    total_seconds = max(int(duration), 0)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _build_stats_block() -> str:
    lines = [
        "Stats (this bot instance):",
        f"- Total videos downloaded: {TOTAL_DOWNLOADS}",
    ]
    for platform, count in _sorted_platform_counts():
        lines.append(f"- {platform}: {count}")
    return "\n".join(lines)


def _build_caption(title: str, url: str, platform: str, duration: int | float) -> str:
    """Create the caption accompanying the downloaded video."""

    duration_text = _format_duration(duration)
    stats_block = _build_stats_block()
    caption = (
        f"{title}\n\n"
        f"Source: {platform}\n"
        f"Link: {url}\n"
        f"Duration: {duration_text}\n\n"
        "Credits: All rights remain with the original creator and hosting platform.\n"
        "This bot only fetches already-public content for personal offline viewing.\n\n"
        "Hosted & paid by: RCD\n"
        "Downloader engine: yt-dlp (supports many public sites such as YouTube, TikTok, "
        "X/Twitter, Instagram, Reddit, Vimeo, and more).\n\n"
        f"{stats_block}"
    )
    return caption


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explain how to use the bot."""

    message = (
        "Send /grab as a reply to any message that contains a public video link.\n\n"
        "This bot downloads a 360p (or nearest) version with strict duration/size limits.\n\n"
        "Use /stats to view total download counters."
    )
    await update.message.reply_text(message)


def _make_input_file(file_path: Path) -> InputFile:
    """Create an InputFile object from disk contents."""

    return InputFile(file_path.read_bytes(), filename=file_path.name)


async def grab(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /grab command which must be sent as a reply."""

    message = update.message
    if not message:
        return

    if not message.reply_to_message:
        await message.reply_text(
            "Please reply to a message that contains a link and send /grab."
        )
        return

    url = _extract_url_from_replied_message(update)
    if not url:
        await message.reply_text("I couldn’t find a link in the message you replied to.")
        return

    await message.reply_text("Got it — downloading a safe-size 360p copy…")

    try:
        result = download_video(url)
    except DownloadValidationError as exc:
        await message.reply_text(str(exc))
        return
    except Exception:  # pylint: disable=broad-except
        logger.exception("Unexpected error while downloading from url=%s", url)
        await message.reply_text(
            "Something went wrong while downloading that video. Please try another link."
        )
        return

    file_path = Path(result["file_path"])
    if not file_path.exists():
        await message.reply_text("Download failed unexpectedly; please try again.")
        return

    size_bytes = file_path.stat().st_size
    logger.info("Sending file %s (%d bytes) for %s", file_path, size_bytes, url)

    global TOTAL_DOWNLOADS  # pylint: disable=global-statement
    TOTAL_DOWNLOADS += 1
    platform = result.get("platform") or "unknown"
    PLATFORM_COUNTS[platform] += 1

    caption = _build_caption(
        result.get("title") or "Untitled",
        url,
        platform,
        result.get("duration") or 0,
    )

    file_sent = False
    try:
        await message.reply_video(
            video=file_path.open("rb"),
            caption=caption,
            read_timeout=300,
            write_timeout=300,
        )
        file_sent = True
    except Exception:  # pylint: disable=broad-except
        logger.exception("Failed to send video; falling back to document for %s", url)
        try:
            await message.reply_document(
                document=file_path.open("rb"),
                caption=caption,
                read_timeout=300,
                write_timeout=300,
            )
            file_sent = True
        except Exception:
            logger.exception("Failed to send document for %s", url)
            await message.reply_text(
                "I downloaded the file but could not send it back. Please try again later."
            )

    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete temporary file %s", file_path)

    if not file_sent:
        # Roll back stats because user never received the file.
        TOTAL_DOWNLOADS = max(TOTAL_DOWNLOADS - 1, 0)
        PLATFORM_COUNTS[platform] = max(PLATFORM_COUNTS[platform] - 1, 0)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the stats block."""

    await update.message.reply_text(_build_stats_block())


def main() -> None:
    """Entrypoint for running the bot."""

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    request = HTTPXRequest(
        connect_timeout=20,
        read_timeout=300,
        write_timeout=300,
        media_write_timeout=300,
        pool_timeout=60,
    )

    application = (
        ApplicationBuilder()
        .token(token)
        .request(request)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("grab", grab))
    application.add_handler(CommandHandler("stats", stats))

    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
