"""
Image-focused validators.
"""
from __future__ import annotations

import imghdr
from pathlib import Path
from typing import Dict, List

from .metadata_utils import extract_metadata


def scan_image(path: Path) -> Dict[str, object]:
    notes: List[str] = []
    detected_format = imghdr.what(str(path))
    suffix = path.suffix.lower().lstrip(".")
    if detected_format and suffix and detected_format != suffix:
        notes.append(f"Extension .{suffix} differs from detected {detected_format}")

    has_appended = _has_appended_data(path, detected_format)
    if has_appended:
        notes.append("File has unexpected data after the image trailer")

    metadata = extract_metadata(path, mime=f"image/{detected_format}" if detected_format else None)
    return {
        "detected_format": detected_format or "unknown",
        "has_exif": metadata.get("exif_present", "no"),
        "gps_present": metadata.get("gps_present", "no"),
        "camera_model": metadata.get("camera_model", "unknown"),
        "has_appended_data": has_appended,
        "notes": notes,
    }


def _has_appended_data(path: Path, detected_format: str | None) -> bool:
    """Very small heuristic to flag JPEG/PNG extra payloads."""
    if detected_format == "jpeg":
        with path.open("rb") as handle:
            data = handle.read()
        end_marker = data.rfind(b"\xFF\xD9")
        return bool(end_marker != -1 and end_marker < len(data) - 2)
    if detected_format == "png":
        # PNG files end with the IEND chunk (12 bytes).
        with path.open("rb") as handle:
            data = handle.read()
        iend = data.rfind(b"IEND\xAE\x42\x60\x82")
        return bool(iend != -1 and iend + 8 < len(data))
    return False
