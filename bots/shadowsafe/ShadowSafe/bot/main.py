"""
ShadowSafe Telegram bot entrypoint.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

from telegram.ext import Application

from . import handlers

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for 3.10
    import tomli as tomllib  # type: ignore


LOG = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def run() -> None:
    """Load configuration, initialize the Telegram client, and start polling."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    token = os.getenv("SHADOWSAFE_BOT_TOKEN")
    if not token:
        raise RuntimeError("SHADOWSAFE_BOT_TOKEN environment variable is required.")

    settings = _load_settings()
    application = Application.builder().token(token).build()
    handlers.register(application, settings)

    LOG.info("ShadowSafe bot started.")
    application.run_polling()


def _load_settings() -> Dict[str, Any]:
    primary = CONFIG_DIR / "settings.toml"
    fallback = CONFIG_DIR / "settings.example.toml"
    path = primary if primary.exists() else fallback
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


if __name__ == "__main__":
    run()
