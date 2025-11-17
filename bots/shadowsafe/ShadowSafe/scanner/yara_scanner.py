"""YARA integration for ShadowSafe."""
from __future__ import annotations

from pathlib import Path
from typing import List

try:  # pragma: no cover - optional dependency
    import yara  # type: ignore
except Exception:  # pragma: no cover
    yara = None

_DEFAULT_RULE = r"""
rule SuspiciousPDFJS {
    strings:
        $js = "/AA" ascii nocase
        $launch = "/Launch" ascii nocase
        $powershell = "powershell" ascii nocase
    condition:
        any of them
}

rule SuspiciousMacroStrings {
    strings:
        $autoopen = "AutoOpen"
        $createmacro = "CreateObject" ascii nocase
        $shell = "WScript.Shell" ascii nocase
    condition:
        2 of them
}
"""


def scan_with_yara(path: Path) -> List[str]:
    if yara is None:
        return []
    rules = yara.compile(source=_DEFAULT_RULE)
    matches = rules.match(str(path))
    return [match.rule for match in matches]
