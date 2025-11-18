"Download an article and extract lightweight metadata."

from __future__ import annotations

from collections import OrderedDict
from typing import Sequence

import httpx
from bs4 import BeautifulSoup

from sudolink.exceptions import MetadataFetchError
from sudolink.types import MetaInfo


class MetaFetcher:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        user_agent: str,
        timeout: float,
    ) -> None:
        self._client = client
        self._timeout = timeout
        self._headers = {"User-Agent": user_agent}

    async def fetch(self, url: str) -> MetaInfo:
        try:
            response = await self._client.get(
                url, headers=self._headers, follow_redirects=True, timeout=self._timeout
            )
            response.raise_for_status()
        except (httpx.HTTPError, httpx.RequestError) as exc:
            raise MetadataFetchError(f"Unable to fetch the original link: {exc}") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        title = _pick_first(
            soup.title.string.strip() if soup.title and soup.title.string else "",
            _meta(soup, "og:title"),
            _meta(soup, "twitter:title"),
        )
        description = _pick_first(
            _meta(soup, "description"),
            _meta(soup, "og:description"),
            _meta(soup, "twitter:description"),
        )
        keywords = tuple(_collect_keywords(soup))
        return MetaInfo(url=url, title=title or None, description=description, keywords=keywords)


def _meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name}) or soup.find(
        "meta", attrs={"property": name}
    )
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def _collect_keywords(soup: BeautifulSoup) -> Sequence[str]:
    keywords: list[str] = []
    raw = _meta(soup, "keywords")
    if raw:
        keywords.extend([kw.strip() for kw in raw.split(",") if kw.strip()])
    # Use ordered dict to preserve order but drop duplicates.
    deduped = OrderedDict((kw.lower(), kw) for kw in keywords)
    return tuple(deduped.values())


def _pick_first(*candidates: str) -> str:
    for candidate in candidates:
        if candidate:
            return candidate
    return ""
