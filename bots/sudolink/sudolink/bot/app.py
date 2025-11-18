"Application setup for python-telegram-bot."

from __future__ import annotations

import logging

from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters

from sudolink.bot.handlers import (
    chishiki_command,
    help_command,
    links_command,
    private_plain_text,
    start_command,
)
from sudolink.config import Settings
from sudolink.services.link_service import LinkService

logger = logging.getLogger(__name__)


def create_application(settings: Settings, service: LinkService) -> Application:
    application = (
        ApplicationBuilder()
            .token(settings.telegram_bot_token)
            .build()
    )
    application.bot_data["link_service"] = service
    application.bot_data["settings"] = settings

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("links", links_command))
    application.add_handler(CommandHandler("chishiki", chishiki_command))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            private_plain_text,
        )
    )
    return application
