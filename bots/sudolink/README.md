# SudoLink

Link-expanding Telegram bot: give it one URL and it returns a handful of other sources covering the same story. It does not judge credibility or label anything as true/false – it simply widens your reading list.

## Requirements
* Python 3.10+
* Telegram Bot token (`@BotFather`)
* OpenAI API key (GPT-4o mini or better recommended)

Install dependencies (choose one):

```bash
pip install -e .
# or
pip install -r requirements.txt
./start_all
```

Provide configuration through environment variables or a local `.env` file:

| Variable | Description |
|----------|-------------|
| `SUDOLINK_TELEGRAM_BOT_TOKEN` (or legacy `TELEGRAM_BOT_TOKEN`) | Required. Bot token from BotFather. |
| `SUDOLINK_OPENAI_API_KEY` (or legacy `OPENAI_API_KEY`) | Required. Powers the GPT call that finds related coverage + insights. |
| `SUDOLINK_OPENAI_MODEL` | Optional. Model name passed to OpenAI (default `gpt-4o-mini`). |
| `SUDOLINK_RESULT_LIMIT` | Optional. Number of links to return (default 4, max 8). |
| `SUDOLINK_INSIGHT_LIMIT` | Optional. Insight bullets to include under the links (default 3, max 6). |
| `SUDOLINK_LOG_LEVEL` | Optional. Python logging level (default `INFO`). |
| `SUDOLINK_USER_AGENT` | Optional. Override the browser User-Agent string used to download the original article (defaults to a recent Chrome build because some publishers block obvious bots). |

## Architecture
`docs/plan.md` dives into the full roadmap. At a high level:

1. `/links` and DM handlers collect a URL from a message or command argument.
2. `/chishiki` (“knowledge”) accepts plain-text summaries when no URL is available.
2. `MetaFetcher` loads the source page to capture title/description/keywords.
3. `AIExpansionService` feeds that context to OpenAI, which returns related links plus short “why read this” blurbs and broader insights. `ResultCurator` keeps the list diverse and deduped.
4. Responses are rendered for Telegram with both the curated links and the extra “insights” section so readers know how the conversation around the story is evolving.

## Commands at a glance
| Command | Purpose |
|---------|---------|
| `/links <url>` | Reply to or paste a link; SudoLink fetches more coverage of that exact story. |
| `/chishiki <summary>` | Share plain-text context (or reply to a message with `/chishiki`) when no link exists; SudoLink interprets the scenario and surfaces relevant reporting. |
| `/start`, `/help` | Usage instructions plus privacy stance (no background monitoring, no chatter logging). |
