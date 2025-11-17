"""
Video container inspections for MP4/MOV and similar formats.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

try:  # pragma: no cover
    import subprocess
except Exception:
    subprocess = None


def scan_video(path: Path) -> Dict[str, object]:
    with path.open("rb") as handle:
        header = handle.read(4096)

    container_ok = b"ftyp" in header[:16]
    weird_atoms: List[str] = []
    if not container_ok:
        weird_atoms.append("Missing ftyp atom")

    has_appended = _has_trailing_payload(path)
    probe = _probe_with_ffprobe(path)

    return {
        "container_ok": container_ok,
        "weird_atoms": weird_atoms,
        "has_appended_data": has_appended,
        "ffprobe_streams": probe.get("streams"),
        "duration": probe.get("duration"),
    }


def _has_trailing_payload(path: Path) -> bool:
    size = path.stat().st_size
    if size <= 0:
        return False
    with path.open("rb") as handle:
        handle.seek(-16, 2)
        tail = handle.read()
    # Quick heuristic: MP4 should end with 'mdat' or 'moov' atoms, not random data.
    return not (b"moov" in tail or b"mdat" in tail)


def _probe_with_ffprobe(path: Path) -> Dict[str, object]:
    if subprocess is None:
        return {}
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            check=True,
            text=True,
        )
    except Exception:
        return {}
    import json

    try:
        data = json.loads(result.stdout)
    except Exception:
        return {}
    duration = data.get("format", {}).get("duration")
    stream_summaries = [
        {
            "codec": stream.get("codec_name"),
            "type": stream.get("codec_type"),
            "width": stream.get("width"),
            "height": stream.get("height"),
        }
        for stream in data.get("streams", [])
    ]
    return {"duration": duration, "streams": stream_summaries}
