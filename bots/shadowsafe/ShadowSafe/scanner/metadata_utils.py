"""
Utilities for extracting EXIF/XMP/general metadata.

The helpers here intentionally stick to the standard library so the project
works without heavyweight dependencies. If Pillow/exifread become available
later the functions can be extended easily.
"""
from __future__ import annotations

import datetime as _dt
import imghdr
from pathlib import Path
from typing import Dict, Optional

try:  # pragma: no cover - optional dependencies
    from PIL import Image, ExifTags  # type: ignore
except Exception:
    Image = None
    ExifTags = None

try:  # pragma: no cover - optional dependency
    from mutagen import File as MutagenFile  # type: ignore
except Exception:
    MutagenFile = None


def extract_metadata(path: Path, mime: str | None = None) -> Dict[str, str]:
    """Parse EXIF/metadata summary for the file."""
    metadata: Dict[str, str] = {}
    mime = mime or _guess_mime_from_path(path)
    if mime and mime.startswith("image/"):
        metadata.update(_extract_image_metadata(path))
    elif mime and mime.startswith("audio/"):
        metadata.update(_extract_audio_metadata(path))
    metadata["collected_at_utc"] = _dt.datetime.utcnow().isoformat() + "Z"
    metadata["file_name"] = path.name
    metadata["file_size_bytes"] = str(path.stat().st_size)
    if mime:
        metadata["mime"] = mime
    return metadata


def summarize_for_report(metadata: Dict[str, str]) -> Dict[str, str]:
    """Reduce verbose metadata into concise privacy-centric bullet points."""
    summary = {
        "exif_present": metadata.get("exif_present", "unknown"),
        "gps_present": metadata.get("gps_present", "unknown"),
        "camera_model": metadata.get("camera_model", "unknown"),
    }
    return summary


def _guess_mime_from_path(path: Path) -> Optional[str]:
    import mimetypes

    mime, _ = mimetypes.guess_type(path.name)
    if mime:
        return mime

    detected = imghdr.what(str(path))
    if detected:
        return f"image/{detected}"
    if MutagenFile is not None:
        audio = MutagenFile(path)
        if audio is not None and audio.mime:
            return audio.mime[0]
    return None


def _extract_image_metadata(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {"exif_present": "no", "gps_present": "no"}
    if Image is None:
        return data

    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return data
            data["exif_present"] = "yes"
            tag_lookup = {v: k for k, v in ExifTags.TAGS.items()} if ExifTags else {}
            gps_tag = tag_lookup.get("GPSInfo")
            if gps_tag and gps_tag in exif:
                data["gps_present"] = "yes"
            model_tag = tag_lookup.get("Model")
            if model_tag and model_tag in exif:
                data["camera_model"] = str(exif.get(model_tag))
    except Exception:
        # Ignore Pillow parsing issues; the summary will fall back to defaults.
        pass
    return data


def _extract_audio_metadata(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if MutagenFile is None:
        return data
    try:
        audio = MutagenFile(path)
    except Exception:
        return data
    if not audio:
        return data
    info = audio.info
    if info:
        if getattr(info, "length", None):
            data["duration_seconds"] = f"{info.length:.2f}"
        if getattr(info, "bitrate", None):
            data["bitrate"] = str(info.bitrate)
    tags = audio.tags or {}
    if tags:
        if "TPE1" in tags:
            data["artist"] = str(tags["TPE1"])
        if "TIT2" in tags:
            data["title"] = str(tags["TIT2"])
    return data
