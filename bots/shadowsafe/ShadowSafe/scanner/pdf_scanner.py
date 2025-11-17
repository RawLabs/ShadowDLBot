"""
PDF-specific heuristics for ShadowSafe.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

try:  # pragma: no cover - optional dependency
    import pikepdf
except Exception:  # pragma: no cover
    pikepdf = None

_JS_PATTERN = re.compile(rb"/(JS|JavaScript)\b", re.IGNORECASE)
_EMBED_PATTERN = re.compile(rb"/EmbeddedFile\b")
_ACTION_PATTERN = re.compile(rb"/OpenAction\b", re.IGNORECASE)
_LINK_PATTERN = re.compile(rb"(https?://[^\s<>]+)", re.IGNORECASE)


def scan_pdf(path: Path) -> Dict[str, object]:
    if pikepdf is not None:
        try:
            return _scan_with_pikepdf(path)
        except Exception:
            pass  # fallback to regex heuristics
    return _scan_with_regex(path)


def _scan_with_pikepdf(path: Path) -> Dict[str, object]:
    suspicious_links: List[str] = []
    embedded_files = 0
    auto_actions = 0
    has_js = False
    with pikepdf.open(path) as pdf:
        root = pdf.root
        names = getattr(root, "Names", None)
        if names and "/JavaScript" in names:
            has_js = True
        if names and "/EmbeddedFiles" in names:
            embedded_files = len(names["/EmbeddedFiles"]["/Names"]) // 2
        if "/OpenAction" in root:
            auto_actions = 1
        for page in pdf.pages:
            annots = page.get("/Annots")
            if not annots:
                continue
            for annot in annots:
                a = annot.get("/A")
                if a and a.get("/URI"):
                    suspicious_links.append(str(a["/URI"]))
    return {
        "has_javascript": has_js,
        "embedded_files": embedded_files,
        "auto_actions": auto_actions,
        "suspicious_links": suspicious_links[:10],
    }


def _scan_with_regex(path: Path) -> Dict[str, object]:
    data = path.read_bytes()
    has_javascript = bool(_JS_PATTERN.search(data))
    embedded_count = len(_EMBED_PATTERN.findall(data))
    open_actions = len(_ACTION_PATTERN.findall(data))
    suspicious_links: List[str] = []
    try:
        suspicious_links = [
            match.decode("utf-8", errors="ignore")[:200] for match in _LINK_PATTERN.findall(data)
        ]
    except Exception:
        pass

    return {
        "has_javascript": has_javascript,
        "embedded_files": embedded_count,
        "auto_actions": open_actions,
        "suspicious_links": suspicious_links[:10],
    }
