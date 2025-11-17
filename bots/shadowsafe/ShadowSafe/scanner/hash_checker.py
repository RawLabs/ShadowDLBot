"""
Hashing and blocklist helper functions.

The real project can later plug in remote blocklist feeds. For now we provide a
deterministic implementation that calculates hashes and checks them against a
small optional in-memory deny list so the rest of the pipeline keeps working.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

# Simple built-in deny list used for tests/manual demos. Real deployment can
# replace this with a file/database lookup.
_STATIC_DENY_LIST: Sequence[str] = ()


def calculate_hashes(path: Path) -> Dict[str, str]:
    """Return SHA256 and MD5 hashes for the provided file."""
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(chunk)
            md5.update(chunk)
    return {"sha256": sha256.hexdigest(), "md5": md5.hexdigest()}


def check_blocklists(path: Path, hashes: Dict[str, str]) -> List[str]:
    """
    Compare hashes to configured blocklists. Implementation intentionally only
    performs hash-based comparisons to avoid shipping file contents elsewhere.
    """
    del path  # unused for now but kept to preserve the contract.
    return _match_blocklist(hashes.values(), _STATIC_DENY_LIST)


def _match_blocklist(
    candidate_hashes: Iterable[str], blocklist: Iterable[str]
) -> List[str]:
    """Return the intersection of candidate hashes and a blocklist."""
    block_set = {entry.lower() for entry in blocklist}
    return [value for value in candidate_hashes if value.lower() in block_set]
