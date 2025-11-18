"Telegram command handlers."

from __future__ import annotations

import logging
from typing import Sequence

from telegram import Update
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import ContextTypes

from sudolink.config import Settings
from sudolink.core.link_extractor import first_url_from_message, normalize_url
from sudolink.exceptions import (
    LinkExtractionError,
    MetadataFetchError,
    SearchProviderError,
    SudoLinkError,
)
from sudolink.services.link_service import LinkService
from sudolink.ui.formatter import format_bundle

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(_start_text())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(_help_text())


async def chishiki_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Context-only command for plain text posts."""

    message = update.effective_message
    service = _get_service(context)
    settings = _get_settings(context)

    context_text = _extract_context_text(message, context.args)
    if not context_text:
        await message.reply_text(
            "Share a quick summary or reply to a message so I have context to work with."
        )
        return

    label = context_text.strip().splitlines()[0][:80]
    if update.effective_chat:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

    try:
        bundle = await service.generate_from_context(
            context_text=context_text,
            limit=settings.max_results,
            reference_label=label,
        )
    except SearchProviderError as exc:
        logger.warning("Context search provider error: %s", exc)
        await message.reply_text(str(exc))
        return
    except SudoLinkError as exc:
        logger.exception("Unexpected context error")
        await message.reply_text(f"Something went wrong: {exc}")
        return

    response_text = format_bundle(bundle)
    logger.debug("chishiki response:\n%s", response_text)
    await message.reply_text(
        response_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def links_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    service = _get_service(context)
    settings = _get_settings(context)

    try:
        url = _resolve_url(message, context.args)
    except LinkExtractionError as exc:
        await message.reply_text(str(exc))
        return

    if update.effective_chat:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

    try:
        bundle = await service.generate_bundle(url, limit=settings.max_results)
    except MetadataFetchError as exc:
        logger.warning("Metadata fetch failed: %s", exc)
        await message.reply_text("I couldn't read that link. Is it reachable?")
        return
    except SearchProviderError as exc:
        logger.warning("Search provider error: %s", exc)
        await message.reply_text(str(exc))
        return
    except SudoLinkError as exc:
        logger.exception("Unexpected link error")
        await message.reply_text(f"Something went wrong: {exc}")
        return

    response_text = format_bundle(bundle)
    logger.debug("links_command response:\n%s", response_text)
    await message.reply_text(
        response_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def private_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat or chat.type != ChatType.PRIVATE:
        return
    message = update.effective_message
    if not message or not message.text:
        return
    service = _get_service(context)
    settings = _get_settings(context)
    url = first_url_from_message(message)
    if not url:
        return
    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
    try:
        bundle = await service.generate_bundle(url, limit=settings.max_results)
    except (MetadataFetchError, SearchProviderError) as exc:
        await message.reply_text(str(exc))
        return
    response_text = format_bundle(bundle)
    logger.debug("private response:\n%s", response_text)
    await message.reply_text(
        response_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


def _resolve_url(message, args: Sequence[str]) -> str:
    if args:
        normalized = normalize_url(args[0])
        if normalized:
            return normalized
    if message.reply_to_message:
        url = first_url_from_message(message.reply_to_message)
        if url:
            return url
    url = first_url_from_message(message)
    if url:
        return url
    raise LinkExtractionError("I need a link to get started. Try /links <url>.")


def _extract_context_text(message, args: Sequence[str]) -> str | None:
    if args:
        joined = " ".join(args).strip()
        if joined:
            return joined
    if message.reply_to_message:
        replied = _message_text(message.reply_to_message)
        if replied:
            return replied.strip()
    return None


def _message_text(message) -> str | None:
    return message.text or message.caption


def _get_service(context: ContextTypes.DEFAULT_TYPE) -> LinkService:
    return context.application.bot_data["link_service"]


def _get_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _start_text() -> str:
    return (
        "Hi, I’m SudoLink.\n\n"
        "Send /links while replying to a message with a URL, or DM me a link directly, "
        "and I’ll fetch more coverage of the same story. I only respond when invoked — no constant monitoring, no fact checking, no judgments."
    )


def _help_text() -> str:
    return (
        "Usage:\n"
        "• `/links <url>` — fetch related articles.\n"
        "• `/chishiki <summary>` — share plain text context and I’ll hunt down coverage.\n"
        "• Reply with `/links` to a link message to avoid retyping.\n"
        "• DM me a link to get results privately.\n\n"
        "I only find more links; I do not rate credibility or store full chat histories."
    )
