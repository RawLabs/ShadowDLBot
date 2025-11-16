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

import logging
import re
import subprocess
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

import httpx
import yt_dlp

from downloader import config

BOT_SOFT_LIMIT_BYTES = int(49.0 * 1024 * 1024)  # ~49 MB
BOT_HARD_LIMIT_BYTES = int(49.6 * 1024 * 1024)  # ~49.6 MB
TRANSCRIPT_LANG_PRIORITY = (
    "en",
    "en-US",
    "en-GB",
    "en-CA",
    "en-AU",
    "en-IN",
)
TRANSCRIPT_EXT_PRIORITY = ("srt", "vtt", "srv3")
SUPPORTED_TRANSCRIPT_EXTS = set(TRANSCRIPT_EXT_PRIORITY)

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


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

    def size_of(fmt: dict[str, Any]) -> float:
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        return float(size) if isinstance(size, (int, float)) else float("inf")

    def pick_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        under_soft_cap = [
            fmt for fmt in candidates if size_of(fmt) <= config.SOFT_TARGET_BYTES
        ]
        pool = under_soft_cap if under_soft_cap else candidates
        pool = sorted(pool, key=size_of)
        return pool[0]

    if filtered:
        return pick_candidate(filtered)

    # Fallback: pick the smallest allowed MP4, even if height is outside 240-360p.
    # TikTok videos are often short, so we trust the Telegram transcode step to
    # shrink them if needed.
    if mp4_video:
        sorted_by_height = sorted(
            mp4_video,
            key=lambda fmt: (
                fmt.get("height") if isinstance(fmt.get("height"), int) else float("inf"),
                size_of(fmt),
            ),
        )
        return pick_candidate(sorted_by_height)

    raise DownloadValidationError("No compatible MP4 formats were returned.")


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


def _pick_entry_for_language(entries: Sequence[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not isinstance(entries, Sequence):
        return None
    normalized = [entry for entry in entries if isinstance(entry, dict)]
    for ext in TRANSCRIPT_EXT_PRIORITY:
        for entry in normalized:
            entry_ext = (entry.get("ext") or "").lower()
            if entry_ext == ext and entry.get("url"):
                return entry
    for entry in normalized:
        entry_ext = (entry.get("ext") or "").lower()
        if entry_ext in SUPPORTED_TRANSCRIPT_EXTS and entry.get("url"):
            return entry
    return None


def _pick_language_track(tracks: Dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(tracks, dict):
        return None
    for lang in TRANSCRIPT_LANG_PRIORITY:
        entry = _pick_entry_for_language(tracks.get(lang) or [])
        if entry:
            return entry
    for entries in tracks.values():
        entry = _pick_entry_for_language(entries or [])
        if entry:
            return entry
    return None


def _select_transcript_entry(info: Dict[str, Any]) -> Optional[dict[str, Any]]:
    for key in ("subtitles", "automatic_captions"):
        tracks = info.get(key) or {}
        entry = _pick_language_track(tracks)
        if entry:
            return entry
    return None


def _timestamp_to_seconds(value: str) -> float:
    value = (value or "").strip().replace(",", ".")
    if not value:
        return 0.0
    parts = value.split(":")
    total = 0.0
    for part in parts:
        try:
            number = float(part)
        except ValueError:
            return 0.0
        total = total * 60 + number
    return total


def _clean_caption_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


_TIME_RANGE_RE = re.compile(
    r"(?P<start>[0-9:\.,]+)\s*-->\s*(?P<end>[0-9:\.,]+)", re.IGNORECASE
)


def _parse_srt_vtt_segments(content: str) -> List[TranscriptSegment]:
    segments: List[TranscriptSegment] = []
    raw = (content or "").replace("\r\n", "\n")
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in raw.split("\n"):
        stripped = line.strip("\ufeff")
        if stripped.strip() == "":
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(stripped)
    if current:
        blocks.append(current)

    for lines in blocks:
        if not lines:
            continue
        idx = 0
        if lines[idx].strip().upper().startswith("WEBVTT"):
            continue
        if re.fullmatch(r"\d+", lines[idx].strip()):
            idx += 1
        while idx < len(lines) and "-->" not in lines[idx]:
            idx += 1
        if idx >= len(lines):
            continue
        match = _TIME_RANGE_RE.search(lines[idx])
        if not match:
            continue
        idx += 1
        text = " ".join(line.strip() for line in lines[idx:])
        cleaned = _clean_caption_text(text)
        if not cleaned:
            continue
        start = _timestamp_to_seconds(match.group("start"))
        end = _timestamp_to_seconds(match.group("end"))
        segments.append(TranscriptSegment(start=start, end=end, text=cleaned))
    return segments


def _parse_srv3_segments(content: str) -> List[TranscriptSegment]:
    segments: List[TranscriptSegment] = []
    try:
        root = ET.fromstring(content or "")
    except ET.ParseError:
        return segments
    for node in root.iter("p"):
        start_ms = float(node.attrib.get("t", "0") or 0.0)
        duration_ms = float(node.attrib.get("d", "0") or 0.0)
        start = start_ms / 1000.0
        duration = duration_ms / 1000.0 if duration_ms else 2.0
        end = start + duration
        text = "".join(node.itertext())
        cleaned = _clean_caption_text(text)
        if cleaned:
            segments.append(TranscriptSegment(start=start, end=end, text=cleaned))
    return segments


def _parse_transcript_content(content: str, ext: str) -> List[TranscriptSegment]:
    ext = (ext or "").lower()
    if ext in {"srt", "vtt"}:
        return _parse_srt_vtt_segments(content)
    if ext == "srv3":
        return _parse_srv3_segments(content)
    return []


def _format_transcript_timestamp(seconds: float) -> str:
    total = max(int(seconds), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _build_timestamp_lines(segments: Sequence[TranscriptSegment]) -> str:
    lines = [
        f"[{_format_transcript_timestamp(segment.start)}] {segment.text}"
        for segment in segments
    ]
    return "\n".join(lines)


def _build_paragraph_text(segments: Sequence[TranscriptSegment]) -> str:
    paragraphs: List[str] = []
    current: List[str] = []
    prev_end: Optional[float] = None
    for segment in segments:
        text = segment.text
        if not text:
            continue
        gap = segment.start - prev_end if prev_end is not None else 0
        should_break = gap >= 6.0 or (
            current and current[-1].rstrip().endswith((".", "!", "?")) and len(
                " ".join(current)
            )
            >= 240
        )
        if should_break and current:
            paragraphs.append(" ".join(current))
            current = []
        current.append(text)
        prev_end = segment.end if segment.end > segment.start else segment.start
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _write_transcript_files(
    base_name: str, segments: Sequence[TranscriptSegment]
) -> dict[str, Path]:
    if not segments:
        return {}
    safe_base = re.sub(r"[^A-Za-z0-9._-]", "_", base_name or "") or "transcript"
    unique_suffix = uuid.uuid4().hex[:8]
    timestamp_path = config.TEMP_DIR / f"{safe_base}.{unique_suffix}.timestamps.txt"
    clean_path = config.TEMP_DIR / f"{safe_base}.{unique_suffix}.clean.txt"
    timestamp_path.write_text(_build_timestamp_lines(segments), encoding="utf-8")
    clean_text = _build_paragraph_text(segments)
    clean_path.write_text(clean_text, encoding="utf-8")
    return {"timestamped": timestamp_path, "plain": clean_path}


def _maybe_create_transcripts(info: Dict[str, Any], base_name: str) -> dict[str, Path]:
    try:
        entry = _select_transcript_entry(info)
    except Exception:  # pylint: disable=broad-except
        logger.exception("Failed to select transcript track.")
        return {}
    if not entry:
        return {}
    url = entry.get("url")
    ext = (entry.get("ext") or "").lower()
    if not url or ext not in SUPPORTED_TRANSCRIPT_EXTS:
        return {}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        )
    }
    try:
        response = httpx.get(url, timeout=30, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Transcript download failed: %s", exc)
        return {}
    segments = _parse_transcript_content(response.text, ext)
    if not segments:
        return {}
    return _write_transcript_files(base_name, segments)


def download_video(url: str, *, allow_long: bool = False) -> dict:
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
    if not allow_long and duration > config.MAX_DURATION_SECONDS:
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
        if allow_long:
            logger.info(
                "Override enabled: continuing despite raw size %.2f MB (> hard cap).",
                size_bytes / (1024 * 1024),
            )
        else:
            file_path.unlink(missing_ok=True)
            raise DownloadValidationError("Downloaded file exceeds the hard cap.")

    file_path = _transcode_for_bot(file_path, duration)
    size_bytes = file_path.stat().st_size

    platform = urlparse(url).hostname or "unknown"
    transcript_paths = _maybe_create_transcripts(info, file_path.stem)
    return {
        "file_path": str(file_path),
        "title": info.get("title") or result.get("title") or "Untitled",
        "duration": int(duration),
        "platform": platform,
        "filesize_bytes": size_bytes,
        "transcript_with_timestamps": str(transcript_paths["timestamped"])
        if transcript_paths.get("timestamped")
        else None,
        "transcript_plain": str(transcript_paths["plain"])
        if transcript_paths.get("plain")
        else None,
    }
