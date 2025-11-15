"""Core downloader logic built around yt-dlp.

The high-level workflow implemented in :func:`download_video` is:

1. Validate the URL (https only, host must be in :mod:`downloader.config`).
2. Use yt-dlp to extract metadata without downloading the media.
3. Reject videos that exceed :data:`config.MAX_DURATION_SECONDS`.
4. Choose a format whose height is at most :data:`config.MAX_HEIGHT` and whose
   estimated size is preferably below :data:`config.SOFT_TARGET_BYTES`.
5. Download into :data:`config.TEMP_DIR`.
6. Enforce :data:`config.HARD_CAP_BYTES` after download.
7. Return an easy-to-consume dict describing the downloaded file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

import yt_dlp

from downloader import config

BOT_SOFT_LIMIT_BYTES = int(49.0 * 1024 * 1024)  # ~49 MB
BOT_HARD_LIMIT_BYTES = int(49.6 * 1024 * 1024)  # ~49.6 MB


class DownloadValidationError(ValueError):
    """Raised whenever the provided URL cannot be downloaded safely."""


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise DownloadValidationError("Only https URLs are allowed.")
    hostname = parsed.hostname or ""
    if hostname.lower() not in config.ALLOWED_HOSTS:
        raise DownloadValidationError("Host is not allowed.")
    return url


def _extract_info(url: str) -> Dict[str, Any]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def _select_format(formats: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the best MP4 format between 240p and 360p."""

    def is_allowed_codec(fmt: dict[str, Any]) -> bool:
        vcodec = (fmt.get("vcodec") or "").lower()
        acodec = (fmt.get("acodec") or "").lower()
        has_video = vcodec not in ("", "none")
        has_audio = acodec not in ("", "none")
        if not (has_video and has_audio):
            return False
        is_h264 = "h264" in vcodec or "avc" in vcodec
        is_aac = "aac" in acodec or "m4a" in acodec or "mp4a" in acodec
        return is_h264 and is_aac

    mp4_video = [
        fmt
        for fmt in formats
        if (fmt.get("ext") or "").lower() == "mp4"
        and fmt.get("vcodec") != "none"
        and is_allowed_codec(fmt)
        and isinstance(fmt.get("height"), int)
    ]

    filtered = [fmt for fmt in mp4_video if 240 <= fmt.get("height", 0) <= 360]

    if not filtered:
        raise DownloadValidationError("No MP4 video between 240 and 360p was found.")

    def size_of(fmt: dict[str, Any]) -> float:
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        return float(size) if isinstance(size, (int, float)) else float("inf")

    under_soft_cap = [
        fmt for fmt in filtered if size_of(fmt) <= config.SOFT_TARGET_BYTES
    ]

    candidates = under_soft_cap if under_soft_cap else filtered
    candidates = sorted(candidates, key=size_of)

    return candidates[0]


def _download(url: str, format_id: str, temp_dir: Path) -> Dict[str, Any]:
    temp_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(temp_dir / "%(id)s.%(ext)s")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": format_id,
        "outtmpl": outtmpl,
        "restrictfilenames": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=True)


def _resolve_file_path(result: Dict[str, Any]) -> Path:
    requested = result.get("requested_downloads") or []
    for entry in requested:
        filepath = entry.get("filepath")
        if filepath:
            return Path(filepath)
    filename = result.get("_filename")
    if not filename:
        raise RuntimeError("yt-dlp did not return a file path.")
    return Path(filename)


def _transcode_for_bot(file_path: Path, duration: int | float) -> Path:
    """Transcode oversized files so they fit under Telegram's hard limit."""

    try:
        size = file_path.stat().st_size
    except OSError as exc:
        raise RuntimeError("Could not read file size for transcoding.") from exc

    if duration <= 0 or size <= BOT_HARD_LIMIT_BYTES:
        return file_path

    out_path = file_path.with_suffix(".bot.mp4")
    target_bits = BOT_SOFT_LIMIT_BYTES * 8
    total_bps = max(int(target_bits / max(int(duration), 1)), 64_000)
    audio_bps = 96_000
    video_bps = max(total_bps - audio_bps, 64_000)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(file_path),
        "-vf",
        f"scale=-2:{config.MAX_HEIGHT}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        str(video_bps),
        "-maxrate",
        str(video_bps),
        "-bufsize",
        str(video_bps * 2),
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.decode("utf-8", errors="ignore")) from exc

    new_size = out_path.stat().st_size
    if new_size > BOT_HARD_LIMIT_BYTES:
        out_path.unlink(missing_ok=True)
        raise DownloadValidationError("Video is too large for Telegram’s 50 MB bot limit.")

    file_path.unlink(missing_ok=True)
    return out_path


def download_video(url: str) -> dict:
    """
    Implement the downloader logic described in the module docstring.
    Use yt-dlp.
    This function will be written with the help of Codex suggestions.
    """
    _validate_url(url)
    info = _extract_info(url)
    duration = info.get("duration")
    if not isinstance(duration, (int, float)):
        raise DownloadValidationError("Missing duration information.")
    if duration > config.MAX_DURATION_SECONDS:
        raise DownloadValidationError("Video is too long.")

    raw_formats = info.get("formats") or []
    if not isinstance(raw_formats, list):
        raise DownloadValidationError("Unexpected format list returned by extractor.")
    selected = _select_format(raw_formats)
    format_id = selected.get("format_id")
    if not format_id:
        raise DownloadValidationError("Selected format is missing an identifier.")

    result = _download(url, str(format_id), config.TEMP_DIR)
    file_path = _resolve_file_path(result)
    if not file_path.exists():
        raise RuntimeError("Download completed but file was not found.")

    size_bytes = file_path.stat().st_size
    if size_bytes > config.HARD_CAP_BYTES:
        file_path.unlink(missing_ok=True)
        raise DownloadValidationError("Downloaded file exceeds the hard cap.")

    file_path = _transcode_for_bot(file_path, duration)
    size_bytes = file_path.stat().st_size

    platform = urlparse(url).hostname or "unknown"
    return {
        "file_path": str(file_path),
        "title": info.get("title") or result.get("title") or "Untitled",
        "duration": int(duration),
        "platform": platform,
        "filesize_bytes": size_bytes,
    }
