"Shared data models used across the SudoLink pipeline."

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence
from urllib.parse import urlparse


@dataclass(slots=True)
class MetaInfo:
    url: str
    title: str | None = None
    description: str | None = None
    keywords: Sequence[str] = field(default_factory=tuple)

    @property
    def host(self) -> str:
        return urlparse(self.url).netloc


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    description: str | None = None
    source: str | None = None
    published_at: datetime | None = None

    def fingerprint(self) -> str:
        """Return a normalized fingerprint for deduplication."""
        parsed = urlparse(self.url)
        path = parsed.path.rstrip("/")
        return f"{parsed.netloc.lower()}|{path.lower()}|{self.title.strip().lower()}"


@dataclass(slots=True)
class LinkBundle:
    original: MetaInfo
    related: Sequence[SearchResult]
    insights: Sequence[str] = field(default_factory=tuple)

    def as_iterable(self) -> Iterable[SearchResult]:
        return tuple(self.related)
