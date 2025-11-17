"""
Archive/DOCX/APK scanner placeholder.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, List

try:  # pragma: no cover - optional dependency
    from oletools.olevba import VBA_Parser  # type: ignore
except Exception:
    VBA_Parser = None


def scan_archive(path: Path) -> Dict[str, object]:
    details: Dict[str, object] = {
        "file_list": [],
        "has_executables": False,
        "has_macros": False,
        "compression_ratio": 0.0,
    }

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            details.update(_scan_zip(archive))
    elif path.suffix.lower() in {".doc", ".xls"}:
        details.update(_scan_ole(path))
    else:
        details["notes"] = "Unsupported archive format"
    return details


def _scan_zip(archive: zipfile.ZipFile) -> Dict[str, object]:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    has_executables = any(_is_executable(name) for name in names)
    has_macros = any("vbaProject.bin" in name for name in names)
    total_size = sum(info.file_size for info in infos) or 1
    total_compress = sum(info.compress_size for info in infos) or 1
    compression_ratio = round(total_size / max(total_compress, 1), 2)
    return {
        "file_list": names[:15],
        "has_executables": has_executables,
        "has_macros": has_macros,
        "compression_ratio": compression_ratio,
    }


def _scan_ole(path: Path) -> Dict[str, object]:
    details: Dict[str, object] = {
        "file_list": [],
        "has_executables": False,
        "has_macros": False,
        "compression_ratio": 1.0,
    }
    if VBA_Parser is None:
        details["notes"] = "oletools not installed"
        return details
    vba = VBA_Parser(str(path))
    try:
        if vba.detect_vba_macros():
            details["has_macros"] = True
            macro_names = {f"{vba_sub.filename}:{vba_sub.stream_path}" for (_, _, _, vba_sub) in vba.extract_macros()}  # type: ignore
            details["file_list"] = list(macro_names)[:10]
    finally:
        vba.close()
    return details


def _is_executable(name: str) -> bool:
    lower = name.lower()
    return lower.endswith((".exe", ".dll", ".scr", ".bat", ".com", ".ps1", ".js"))
