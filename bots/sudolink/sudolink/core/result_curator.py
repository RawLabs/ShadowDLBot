"Curate search results for diversity and deduplication."

from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

from sudolink.types import SearchResult


class ResultCurator:
    def __init__(self, max_per_domain: int = 1) -> None:
        self._max_per_domain = max_per_domain

    def curate(self, results: list[SearchResult], limit: int) -> list[SearchResult]:
        if not results:
            return []
        seen: set[str] = set()
        domain_counts: Counter[str] = Counter()
        preferred: list[SearchResult] = []
        overflow: list[SearchResult] = []

        for result in results:
            fingerprint = result.fingerprint()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            domain = urlparse(result.url).netloc.lower()
            if domain_counts[domain] < self._max_per_domain:
                domain_counts[domain] += 1
                preferred.append(result)
            else:
                overflow.append(result)

        combined = preferred + overflow
        return combined[:limit]
