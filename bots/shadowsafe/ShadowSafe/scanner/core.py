"""
Core orchestrator for ShadowSafe file scans.
"""
from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import (
    archive_scanner,
    filetype_registry,
    hash_checker,
    heuristics,
    image_scanner,
    metadata_utils,
    pdf_scanner,
    sanitizers,
    video_scanner,
    yara_scanner,
)


@dataclass
class Issue:
    severity: str
    category: str
    message: str
    explanation: str | None = None


@dataclass
class ScanResult:
    file_name: str
    size_bytes: int
    detected_type: str
    extension_mismatch: Optional[str] = None
    hashes: Dict[str, str] = field(default_factory=dict)
    blocklist_hits: List[str] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    metadata_summary: Dict[str, str] = field(default_factory=dict)
    can_sanitize: bool = False
    sanitized_file_path: Optional[Path] = None
    per_scanner_details: Dict[str, Dict[str, object]] = field(default_factory=dict)
    risk_score: int = 0


def scan_file(
    path: Path, mime_hint: Optional[str] = None, *, enable_sanitization: bool = False
) -> ScanResult:
    """Run the configured scanners for the provided file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    detected_type = filetype_registry.detect_type(path, mime_hint)
    hashes = hash_checker.calculate_hashes(path)
    blocklist_hits = hash_checker.check_blocklists(path, hashes)
    metadata = metadata_utils.extract_metadata(path, detected_type)
    metadata_summary = metadata_utils.summarize_for_report(metadata)
    per_scanner_details: Dict[str, Dict[str, object]] = {}
    issues: List[Issue] = []

    pdf_details = None
    for scanner_key in filetype_registry.get_scanners_for(detected_type):
        details = _run_scanner(scanner_key, path)
        per_scanner_details[scanner_key] = details
        issues.extend(_issues_from_details(scanner_key, details))
        if scanner_key == "pdf":
            pdf_details = details

    heuristic_details = heuristics.analyze_entropy(path)
    per_scanner_details["heuristics"] = heuristic_details
    issues.extend(_issues_from_heuristics(heuristic_details))

    yara_matches = yara_scanner.scan_with_yara(path)
    if yara_matches:
        severity, explanation = _evaluate_yara_context(yara_matches, pdf_details)
        per_scanner_details["yara"] = {"matches": yara_matches}
        issues.append(
            Issue(
                severity,
                "yara",
                f"Matched YARA rules: {', '.join(yara_matches[:5])}",
                explanation=explanation,
            )
        )

    extension_mismatch = _extension_mismatch(path, detected_type)

    sanitized_file_path = None
    can_sanitize = False
    if enable_sanitization:
        if detected_type.startswith("image/"):
            sanitized_file_path = sanitizers.sanitize_image(path)
            can_sanitize = True
        elif detected_type == "application/pdf":
            sanitized_file_path = sanitizers.sanitize_pdf(path)
            can_sanitize = True
    else:
        can_sanitize = detected_type.startswith(("image/", "application/pdf"))

    size_bytes = path.stat().st_size
    risk_score = _calculate_risk_score(issues)

    return ScanResult(
        file_name=path.name,
        size_bytes=size_bytes,
        detected_type=detected_type,
        extension_mismatch=extension_mismatch,
        hashes=hashes,
        blocklist_hits=blocklist_hits,
        issues=issues,
        metadata_summary=metadata_summary,
        can_sanitize=can_sanitize,
        sanitized_file_path=sanitized_file_path,
        per_scanner_details=per_scanner_details,
        risk_score=risk_score,
    )


def _run_scanner(scanner_key: str, path: Path) -> Dict[str, object]:
    if scanner_key == "pdf":
        return pdf_scanner.scan_pdf(path)
    if scanner_key == "image":
        return image_scanner.scan_image(path)
    if scanner_key == "video":
        return video_scanner.scan_video(path)
    if scanner_key == "archive":
        return archive_scanner.scan_archive(path)
    return {}


def _issues_from_details(scanner_key: str, details: Dict[str, object]) -> List[Issue]:
    issues: List[Issue] = []
    if scanner_key == "pdf":
        if details.get("has_javascript"):
            issues.append(
                Issue(
                    "yellow",
                    "pdf",
                    "Embedded JavaScript detected",
                    explanation="PDF contains names referencing JavaScript objects.",
                )
            )
        if details.get("embedded_files", 0):
            issues.append(
                Issue(
                    "yellow",
                    "pdf",
                    f"{details.get('embedded_files')} embedded files",
                    explanation="Embedded files may hide payloads that execute on open.",
                )
            )
        if details.get("auto_actions", 0):
            issues.append(
                Issue(
                    "yellow",
                    "pdf",
                    "Auto actions present",
                    explanation="OpenAction entries can run code when the document opens.",
                )
            )
    elif scanner_key == "image":
        if details.get("gps_present") == "yes":
            issues.append(
                Issue(
                    "yellow",
                    "image",
                    "GPS metadata found",
                    explanation="Embedded GPS metadata can reveal location data.",
                )
            )
        if details.get("has_appended_data"):
            issues.append(
                Issue(
                    "yellow",
                    "image",
                    "Image contains appended data",
                    explanation="Appended data may carry hidden payloads or steganography.",
                )
            )
    elif scanner_key == "video":
        if not details.get("container_ok", True):
            issues.append(
                Issue(
                    "yellow",
                    "video",
                    "Video container header missing",
                    explanation="Container header anomalies may indicate tampered files.",
                )
            )
        if details.get("has_appended_data"):
            issues.append(
                Issue(
                    "yellow",
                    "video",
                    "Video has unexpected trailer data",
                    explanation="Unexpected data at the end of the file can hide payloads.",
                )
            )
    elif scanner_key == "archive":
        if details.get("has_executables"):
            issues.append(
                Issue(
                    "red",
                    "archive",
                    "Archive contains executable files",
                    explanation="Executables inside archives can deliver malware.",
                )
            )
        if details.get("has_macros"):
            issues.append(
                Issue(
                    "yellow",
                    "archive",
                    "Archive may contain macros",
                    explanation="Office macros often deliver malicious payloads.",
                )
            )
    return issues


def _issues_from_heuristics(details: Dict[str, object]) -> List[Issue]:
    issues: List[Issue] = []
    if details.get("high_entropy_ratio", 0) > 0.4:
        issues.append(
            Issue(
                "yellow",
                "entropy",
                "Large portions of the file look highly obfuscated",
                explanation="High entropy sections are typical for encrypted or compressed payloads.",
            )
        )
    if details.get("trailing_data_ratio", 0) > 0.2:
        issues.append(
            Issue(
                "yellow",
                "structure",
                "Significant trailing data found past expected EOF",
                explanation="Files that carry data beyond their expected end can hide extra payloads.",
            )
        )
    return issues


def _calculate_risk_score(issues: List[Issue]) -> int:
    weights = {"red": 50, "yellow": 20, "green": 0}
    score = sum(weights.get(issue.severity, 10) for issue in issues)
    return min(score, 100)


def _evaluate_yara_context(matches: List[str], pdf_details: Dict[str, object] | None) -> tuple[str, str | None]:
    if not pdf_details:
        return "red", "YARA rule hit; review manually."
    risky = any(
        pdf_details.get(flag_key, 0)
        for flag_key in ("has_javascript", "embedded_files", "auto_actions")
    )
    if risky:
        return "red", "YARA hit coincides with active PDF features (JS/embeds/actions)."
    return "yellow", "Rule matched but no active PDF features were detected."


def _extension_mismatch(path: Path, detected_type: str) -> Optional[str]:
    guessed_ext = mimetypes.guess_extension(detected_type or "") or ""
    real_ext = path.suffix.lower()
    if guessed_ext and real_ext and guessed_ext != real_ext:
        return f"Expected {guessed_ext}, got {real_ext}"
    return None
