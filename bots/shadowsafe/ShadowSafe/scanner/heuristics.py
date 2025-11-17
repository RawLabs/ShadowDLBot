"""Generic heuristics used across scanners."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict


def analyze_entropy(path: Path, *, block_size: int = 4096) -> Dict[str, object]:
    """Compute Shannon entropy per block to flag obfuscated payloads."""
    file_size = path.stat().st_size or 1
    high_entropy_blocks = 0
    entropy_samples = []
    trailing_ratio = _trailing_data_ratio(path)

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(block_size)
            if not chunk:
                break
            entropy = _shannon_entropy(chunk)
            entropy_samples.append(entropy)
            if entropy > 7.5:
                high_entropy_blocks += 1

    mean_entropy = round(sum(entropy_samples) / len(entropy_samples), 3) if entropy_samples else 0
    return {
        "mean_entropy": mean_entropy,
        "high_entropy_blocks": high_entropy_blocks,
        "high_entropy_ratio": round(high_entropy_blocks / max(len(entropy_samples), 1), 3),
        "trailing_data_ratio": trailing_ratio,
    }


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = {}
    for byte in data:
        freq[byte] = freq.get(byte, 0) + 1
    entropy = 0.0
    length = len(data)
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def _trailing_data_ratio(path: Path) -> float:
    """Simple heuristic: look for long stretches of zero/one values near EOF."""
    size = path.stat().st_size or 1
    window = min(65536, size)
    if window <= 0:
        return 0.0
    with path.open("rb") as handle:
        handle.seek(-window, 2)
        tail = handle.read()
    junk = tail.rstrip(b"\x00\xff")
    if not junk:
        return 0.0
    trailing_len = len(tail) - len(junk)
    return round(trailing_len / window, 3)
