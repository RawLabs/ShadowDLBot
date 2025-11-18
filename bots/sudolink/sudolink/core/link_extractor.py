"Utilities for locating and normalizing URLs from Telegram messages."

from __future__ import annotations

import re
from typing import Iterable, Optional
from urllib.parse import urlparse, urlunparse

from telegram import Message, MessageEntity

URL_RE = re.compile(
    r"(?P<url>(?:https?://|www\.)[\w\-\._~:/?#\[\]@!$&'()*+,;=%]+)", re.IGNORECASE
)


def normalize_url(raw: str | None) -> str | None:
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if not parsed.scheme.startswith("http"):
        return None
    if not parsed.netloc:
        return None
    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)


def _extract_from_entities(message: Message) -> Iterable[str]:
    if not message.entities:
        return ()
    results: list[str] = []
    entity_map = message.parse_entities(
        [MessageEntity.URL, MessageEntity.TEXT_LINK, MessageEntity.MENTION]
    )
    for entity, text in entity_map.items():
        if entity.type == MessageEntity.TEXT_LINK and entity.url:
            results.append(entity.url)
        elif entity.type == MessageEntity.URL:
            results.append(text)
    return results


def _extract_from_text(text: Optional[str]) -> Iterable[str]:
    if not text:
        return ()
    return [match.group("url") for match in URL_RE.finditer(text)]


def first_url_from_message(message: Message) -> str | None:
    for candidate in _extract_from_entities(message):
        normalized = normalize_url(candidate)
        if normalized:
            return normalized

    for candidate in _extract_from_text(message.text or message.caption):
        normalized = normalize_url(candidate)
        if normalized:
            return normalized
    return None
