"""Downloader configuration values used across the project."""

from __future__ import annotations

from pathlib import Path

# Hosts we are willing to download from.
ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "vt.tiktok.com",
    "vm.tiktok.com",
}

# Limits defined by the user/instructions.
MAX_DURATION_SECONDS = 66 * 60  # 66 minutes
MAX_HEIGHT = 320  # 320p
SOFT_TARGET_BYTES = 50 * 1024 * 1024  # ~50 MB
HARD_CAP_BYTES = 80 * 1024 * 1024  # ~80 MB

ROOT_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = ROOT_DIR / "tmp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
