"OpenAI-powered link and insight generator."

from __future__ import annotations

import json
from typing import Sequence

from openai import AsyncOpenAI

from sudolink.exceptions import SearchProviderError
from sudolink.types import MetaInfo, SearchResult


class AIExpansionService:
    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        model: str,
        insight_limit: int,
    ) -> None:
        self._client = client
        self._model = model
        self._insight_limit = max(0, insight_limit)

    async def expand(self, meta: MetaInfo, *, limit: int) -> tuple[list[SearchResult], list[str]]:
        messages = self._build_messages(meta, limit)
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=messages,
            )
        except Exception as exc:  # pragma: no cover - network failure path
            raise SearchProviderError(f"OpenAI request failed: {exc}") from exc

        content = (
            response.choices[0].message.content if response.choices else None
        )
        if not content:
            raise SearchProviderError("OpenAI response did not include any content.")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:  # pragma: no cover - model misbehaviour
            raise SearchProviderError("OpenAI response was not valid JSON.") from exc

        related = self._parse_links(payload.get("related_links"), limit)
        insights = self._parse_insights(payload.get("insights"))
        return related, insights

    def _build_messages(self, meta: MetaInfo, limit: int) -> list[dict[str, str]]:
        keywords = ", ".join(meta.keywords) if meta.keywords else "n/a"
        description = meta.description or "n/a"
        title = meta.title or "Untitled"
        system_prompt = (
            "You are SudoLink, an assistant that widens a reader's perspective by "
            "finding reputable coverage of the same news story. Always respond with "
            "valid JSON containing two keys: 'related_links' and 'insights'. "
            "'related_links' must be an array of objects with fields "
            "title, url, source, and summary. 'insights' must be an array of short "
            "bullets highlighting angles, implications, or tensions between outlets."
        )
        user_prompt = (
            f"Original article URL: {meta.url}\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Keywords: {keywords}\n\n"
            f"Return up to {limit} distinct news links from established outlets that "
            "cover the same event. Explain why each linked article matters in the "
            "'summary' field and avoid speculation or invented outlets. "
            f"Also provide up to {self._insight_limit} concise insights about how the "
            "coverage differs, why it matters, or what readers should watch next."
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_links(
        self, data: Sequence[dict[str, object]] | None, limit: int
    ) -> list[SearchResult]:
        if not data:
            return []
        results: list[SearchResult] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url") or "").strip()
            if not url:
                continue
            title = str(entry.get("title") or "Untitled").strip() or "Untitled"
            summary = str(entry.get("summary") or "").strip() or None
            source = str(entry.get("source") or "").strip() or None
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    description=summary,
                    source=source,
                )
            )
            if len(results) >= limit:
                break
        return results

    def _parse_insights(self, data: Sequence[str] | None) -> list[str]:
        if not data or self._insight_limit <= 0:
            return []
        insights: list[str] = []
        for idea in data:
            snippet = str(idea).strip()
            if not snippet:
                continue
            insights.append(snippet)
            if len(insights) >= self._insight_limit:
                break
        return insights
