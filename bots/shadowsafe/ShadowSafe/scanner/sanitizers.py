"""
Optional sanitization helpers.

The implementations here deliberately keep things simple: they duplicate the
file into a new path so the calling code can treat it as a sanitized artifact.
Real metadata stripping/transcoding can replace these helpers later.
"""
from __future__ import annotations

import shutil
from pathlib import Path


def sanitize_image(path: Path) -> Path:
    return _copy_for_sanitized_output(path, suffix="-sanitized")


def sanitize_pdf(path: Path) -> Path:
    return _copy_for_sanitized_output(path, suffix="-sanitized")


def _copy_for_sanitized_output(path: Path, suffix: str) -> Path:
    sanitized_path = path.with_name(f"{path.stem}{suffix}{path.suffix}")
    shutil.copy2(path, sanitized_path)
    return sanitized_path
