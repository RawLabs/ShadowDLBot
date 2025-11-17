"""
Maps file signatures/MIME hints to scanner pipelines.
"""
from __future__ import annotations

import imghdr
import mimetypes
from pathlib import Path
from typing import List

_MAGIC_MAP = {
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/zip",
    b"\x1F\x8B": "application/gzip",
}


def detect_type(path: Path, mime_hint: str | None = None) -> str:
    """Return MIME-like detected type string."""
    if mime_hint:
        return mime_hint

    mime, _ = mimetypes.guess_type(path.name)
    if mime:
        return mime

    with path.open("rb") as handle:
        header = handle.read(8)
    for magic, detected in _MAGIC_MAP.items():
        if header.startswith(magic):
            return detected

    image_kind = imghdr.what(str(path))
    if image_kind:
        return f"image/{image_kind}"

    return "application/octet-stream"


def get_scanners_for(detected_type: str) -> List[str]:
    """
    Translate a detected type (e.g. `application/pdf`) into a list of logical
    scanner keys.
    """
    if detected_type.startswith("image/"):
        return ["image"]
    if detected_type.startswith("video/"):
        return ["video"]
    if detected_type in {"application/pdf"}:
        return ["pdf"]
    if detected_type in {
        "application/zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.android.package-archive",
    }:
        return ["archive"]
    return []
