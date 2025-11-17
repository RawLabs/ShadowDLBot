"""TikTok URL detection and yt-dlp integration for TicTocDoc."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from config import Config, DEFAULT_CONFIG

LOGGER = logging.getLogger(__name__)

TIKTOK_URL_RE = re.compile(r"(https?://(?:www\.|vm\.)?tiktok\.com/[^\s]+)", re.IGNORECASE)

try:
    import yt_dlp  # type: ignore
except Exception:  # pragma: no cover - yt-dlp optional
    yt_dlp = None


@dataclass
class TikTokInfo:
    url: str
    normalized_url: str
    video_id: str
    title: str | None
    uploader: str | None
    local_file_path: Path | None
    error: str | None
    metadata: Mapping[str, Any]


def extract_first_tiktok_url(text: str) -> str | None:
    """Return the first TikTok URL from arbitrary text."""
    if not text:
        return None
    match = TIKTOK_URL_RE.search(text)
    if not match:
        return None
    return match.group(1)


def normalize_tiktok_url(url: str) -> str:
    """Strip obvious tracking parameters and normalize schemes."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"

    allowed_params = {"lang"}
    query_params = {k: v for k, v in parse_qs(parsed.query, keep_blank_values=False).items() if k in allowed_params}
    query = urlencode({k: values[0] for k, values in query_params.items()}) if query_params else ""

    return urlunparse((scheme, netloc, path, "", query, ""))


def fetch_tiktok_info(url: str, config: Config | None = None) -> TikTokInfo:
    """Fetch TikTok metadata and optionally download the clip."""
    cfg = config or DEFAULT_CONFIG
    normalized = normalize_tiktok_url(url)
    metadata: dict[str, Any] = {}
    local_file: Path | None = None
    error: str | None = None

    try:
        metadata, local_file = _run_yt_dlp(normalized, cfg)
    except Exception as exc:  # pragma: no cover - defensive
        error = str(exc)
        LOGGER.warning("yt-dlp failed for %s: %s", normalized, error)

    video_id = metadata.get("id") if metadata else None
    title = metadata.get("title") if metadata else None
    uploader = metadata.get("uploader") if metadata else None

    return TikTokInfo(
        url=url,
        normalized_url=normalized,
        video_id=video_id or "unknown",
        title=title,
        uploader=uploader,
        local_file_path=local_file,
        error=error,
        metadata=metadata,
    )


def _run_yt_dlp(url: str, config: Config) -> tuple[dict[str, Any], Path | None]:
    """Use yt-dlp module or CLI to gather info."""
    download_enabled = config.download_videos

    if yt_dlp is not None:
        return _run_via_module(url, config, download_enabled)

    return _run_via_cli(url, config, download_enabled)


def _run_via_module(url: str, config: Config, download: bool) -> tuple[dict[str, Any], Path | None]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": not download,
    }
    temp_dir: Path | None = None
    if download:
        temp_dir = Path(tempfile.mkdtemp(prefix="tictocdoc_", dir=str(config.temp_dir)))
        opts["outtmpl"] = str(temp_dir / "%(id)s.%(ext)s")

    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[attr-defined]
        info = ydl.extract_info(url, download=download)

    local_file = Path(info["_filename"]) if download and "_filename" in info else None
    if local_file and temp_dir and not local_file.is_file():
        possible = next(iter(temp_dir.glob(f"{info.get('id', '*')}.*")), None)
        local_file = possible

    return info, local_file


def _run_via_cli(url: str, config: Config, download: bool) -> tuple[dict[str, Any], Path | None]:
    cmd = [config.yt_dlp_path or "yt-dlp", "--dump-json", url]
    temp_dir: Path | None = None
    if download:
        temp_dir = Path(tempfile.mkdtemp(prefix="tictocdoc_", dir=str(config.temp_dir)))
        cmd.extend(["-o", str(temp_dir / "%(id)s.%(ext)s")])
    else:
        cmd.append("--skip-download")

    LOGGER.debug("Running %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"yt-dlp exited with {proc.returncode}")

    line = proc.stdout.strip().splitlines()[-1]
    info = json.loads(line)

    local_file = None
    if download and temp_dir:
        guessed = next(iter(temp_dir.glob(f"{info.get('id', '*')}.*")), None)
        local_file = guessed

    return info, local_file
