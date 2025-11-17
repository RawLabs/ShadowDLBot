"""Configuration helpers for TicTocDoc."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Runtime configuration derived from environment variables."""

    bot_token: str
    download_videos: bool = True
    temp_dir: Path = Path("/tmp")
    yt_dlp_path: str | None = None
    log_level: str = "INFO"

    @staticmethod
    def from_env() -> "Config":
        token = os.getenv("TICTOCDOC_BOT_TOKEN") or ""
        download_flag = os.getenv("TICTOCDOC_DOWNLOADS", "1") not in {"0", "false", "False"}
        custom_temp = os.getenv("TICTOCDOC_TEMP_DIR")
        temp_dir = Path(custom_temp) if custom_temp else Path("/tmp")
        yt_dlp_path = os.getenv("TICTOCDOC_YT_DLP")
        log_level = os.getenv("TICTOCDOC_LOG_LEVEL", "INFO")
        return Config(
            bot_token=token,
            download_videos=download_flag,
            temp_dir=temp_dir,
            yt_dlp_path=yt_dlp_path,
            log_level=log_level,
        )


DEFAULT_CONFIG = Config.from_env()
