"Render Telegram-ready responses."

from __future__ import annotations

from datetime import datetime
from html import escape
from urllib.parse import urlparse

from sudolink.types import LinkBundle, SearchResult


def format_bundle(bundle: LinkBundle) -> str:
    body = ["<b>SudoLink results:</b>"]
    if not bundle.related:
        body.append("<i>No additional coverage found right now.</i>")
    else:
        for item in bundle.related:
            body.append(_render_result(item))
    if bundle.insights:
        body.append("")
        body.append("<b>Insights:</b>")
        for idea in bundle.insights:
            body.append(f"• {escape(idea)}")
    body.append("")
    if bundle.original.url.startswith("context://"):
        context_snippet = bundle.original.description or bundle.original.title or "Conversation snippet"
        preview = escape(context_snippet[:180])
        body.append(f"<i>Original context:</i> {preview}")
    else:
        original_title = escape(bundle.original.title or "Original link")
        original_url = escape(bundle.original.url, quote=True)
        body.append(f"<i>Original source:</i> <a href=\"{original_url}\">{original_title}</a>")
    return "\n".join(body)


def _render_result(result: SearchResult) -> str:
    title = escape(result.title or "untitled")
    url = escape(result.url, quote=True)
    source_name = result.source or urlparse(result.url).netloc or "source"
    source = escape(source_name)
    extras: list[str] = []
    if result.published_at:
        extras.append(_format_date(result.published_at))
    if result.description:
        extras.append(f"<i>{escape(result.description)}</i>")
    suffix = f" — {source}"
    if extras:
        suffix += " | " + " ".join(extras)
    return f"• <a href=\"{url}\">{title}</a>{suffix}"


def _format_date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")
