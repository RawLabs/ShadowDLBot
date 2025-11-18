"Entrypoint for running SudoLink."

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import signal

import httpx
from openai import AsyncOpenAI

from sudolink.bot.app import create_application
from sudolink.config import Settings
from sudolink.core.meta_fetcher import MetaFetcher
from sudolink.core.result_curator import ResultCurator
from sudolink.services.ai_expansion import AIExpansionService
from sudolink.services.link_service import LinkService

logger = logging.getLogger(__name__)


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)


def main() -> None:
    _load_local_env()
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Starting SudoLink")
    asyncio.run(_run(settings))


async def _run(settings: Settings) -> None:
    async with httpx.AsyncClient(timeout=settings.http_timeout) as http_client:
        meta_fetcher = MetaFetcher(
            client=http_client, user_agent=settings.user_agent, timeout=settings.http_timeout
        )
        curator = ResultCurator()
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        ai_service = AIExpansionService(
            client=openai_client,
            model=settings.openai_model,
            insight_limit=settings.insight_limit,
        )
        service = LinkService(
            meta_fetcher=meta_fetcher,
            ai_service=ai_service,
            result_curator=curator,
        )
        application = create_application(settings, service)
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Bot is polling for updates.")
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                pass
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            stop_event.set()
            raise
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()


if __name__ == "__main__":
    main()
