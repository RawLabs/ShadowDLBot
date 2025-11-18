"Coordinates the end-to-end link discovery workflow."

from __future__ import annotations

from sudolink.core.meta_fetcher import MetaFetcher
from sudolink.core.result_curator import ResultCurator
from sudolink.services.ai_expansion import AIExpansionService
from sudolink.types import LinkBundle, MetaInfo


class LinkService:
    def __init__(
        self,
        *,
        meta_fetcher: MetaFetcher,
        ai_service: AIExpansionService,
        result_curator: ResultCurator,
    ) -> None:
        self._meta_fetcher = meta_fetcher
        self._ai_service = ai_service
        self._curator = result_curator

    async def generate_bundle(self, url: str, *, limit: int) -> LinkBundle:
        original = await self._fetch_meta(url)
        suggestions, insights = await self._ai_service.expand(original, limit=limit)
        curated = self._curator.curate(suggestions, limit)
        return LinkBundle(original=original, related=curated, insights=tuple(insights))

    async def generate_from_context(
        self,
        *,
        context_text: str,
        limit: int,
        reference_label: str | None = None,
    ) -> LinkBundle:
        snippet = context_text.strip()
        title = reference_label or (snippet[:80] if snippet else "Conversation snippet")
        meta = MetaInfo(
            url="context://chishiki",
            title=title,
            description=snippet or None,
            keywords=(),
        )
        suggestions, insights = await self._ai_service.expand(meta, limit=limit)
        curated = self._curator.curate(suggestions, limit)
        return LinkBundle(original=meta, related=curated, insights=tuple(insights))

    async def _fetch_meta(self, url: str) -> MetaInfo:
        return await self._meta_fetcher.fetch(url)
