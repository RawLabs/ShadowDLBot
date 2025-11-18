## SudoLink – Build Plan

### 1. Product boundaries
* **Promise:** take one submitted URL and reply with a curated list of other sources discussing the same event or topic.
* **Non-goals:** labeling content as true/false, ranking credibility, or running in the background without explicit commands.
* **Tagline:** _“I don’t fact-check. I just find more coverage of the same story.”_

### 2. User flows
1. **Group reply**
   * User replies to any message containing a link with `/links`.
   * Bot checks the replied-to message for the first URL. If none, it answers with a friendly reminder that it needs a link.
   * Response stays in the same thread: headline helper text + bullet list of 3–5 related articles + original link.
2. **Command in chat (`/links <url>`)**
   * Works in both groups and DM.
   * Parses the argument for a valid URL, falling back to the reply-to message.
3. **Plain-text context (`/chishiki <summary>`)**
   * Samurai nod to “knowledge.” Accepts raw descriptions when no link exists.
   * User can reply to a message with `/chishiki` or type `/chishiki The minister just...`.
   * Bot treats that text as the seed and still replies with third-party coverage + insights.
4. **Direct message drop**
   * User sends only a URL. Bot treats it like `/links <url>` and replies privately.
5. **`/start` & `/help`**
   * `/start`: explain what SudoLink does, that it only acts when invoked, privacy stance, and top-level usage instructions.
   * `/help`: one-page reminder of commands, rate limits, logging policy, and the “no fact-checking” promise.

### 3. System architecture
```
Telegram Update ──▶ Command Router
                    │
                    ├──▶ LinkExtractor (parses replied message / args / raw text)
                    └──▶ UsagePolicy (rate limits, DM-only blocks, etc.)
                                  │
                                  ▼
MetaFetcher (original page title, description, key terms)
                                  │
                                  ▼
AIExpansionService (OpenAI prompt that returns related links + insights)
                                  │
                                  ▼
ResultCurator (dedupe by domain+path hash, prefer diverse domains, cap at 5)
                                  │
                                  ▼
ReplyFormatter (markdown-safe bullets + “original link” footer)
```
* **Config:** `.env`/environment variables for Telegram token, OpenAI API key/model, and presentation tweaks.
* **Persistence:** lightweight SQLite (or Redis later) only if rate limiting is needed; otherwise keep everything stateless.
* **Logging:** structured info-level logs for command, chat id, number of results, latency. No payload storage.

### 4. Components & responsibilities
| Component | Responsibilities | Notes |
|-----------|-----------------|-------|
| `start_all` script | Wrapper that loads env vars and runs the Python entry point. | Aligns with other TG bots in this repo. |
| `bot/main.py` | Wiring for python-telegram-bot (v20+) application, command handlers, and startup. | Async `ApplicationBuilder` with webhook ready but start in polling mode. |
| `core/link_extractor.py` | Validates commands, finds URLs in replies or arguments, normalizes them. | Use `urllib.parse` + regex fallback. |
| `core/meta_fetcher.py` | Fetches the original URL, pulls `<title>`, meta description, publishes keywords. | Use `httpx` + `readability-lxml` or `BeautifulSoup`. |
| `services/ai_expansion.py` | Calls OpenAI with the original article context and asks for related coverage + insights. | Uses JSON-mode to keep replies structured. |
| `core/result_curator.py` | Deduplication, domain diversity, ensures 3–5 links + original. | Keep track of host counts to encourage variety. |
| `ui/formatter.py` | Renders Telegram-safe response with summary headline + insights block. | Adds context footer when `/chishiki` is used. |
| `bot/handlers.py` | `/links`, `/chishiki`, `/start`, `/help`, and DM glue. | Keeps responses friendly and privacy-focused. |

### 5. Command behaviors
* `/start`: static text template with privacy statement, usage instructions, tagline.
* `/help`: same copy as `/start` plus rate limit hints and supported languages (initially EN).
* `/links`:
  * accepts optional argument URL,
  * if replying to message with URL, uses that,
  * DM fallback: if plain URL message, treat as command.
  * Errors: “Need at least one link”, “Could not fetch metadata”, “Search returned nothing”.
* `/chishiki`:
  * accepts inline summary text or uses the replied-to message text,
  * seeds the OpenAI expansion with that context instead of a fetched page,
  * Errors: “Share a quick summary...”, “Search provider error”.

### 6. Security & privacy posture
* Respect Telegram terms: no background scraping.
* Use `asyncio.Semaphore` or queue to avoid API overuse.
* Mask URLs in logs; store only hostnames.
* Config flag to disable LLM keyword extraction if no key is set.

### 7. Implementation roadmap
1. **Bootstrap project**
   * `pyproject.toml` with `python-telegram-bot`, `httpx`, `beautifulsoup4`, `python-dotenv`, `pydantic`.
   * `start_all` script loading `.env` and invoking `python -m sudolink`.
2. **Core bot skeleton**
   * Command handlers and message handler for plain URLs in DM.
   * Logging middleware + graceful shutdown.
3. **Link pipeline**
   * Build `LinkExtractor`, `MetaFetcher` (with fallback to OpenGraph only).
   * Implement `AIExpansionService` that prompts OpenAI for related coverage + insight bullets.
4. **Response polish**
   * Markdown formatting, domain diversity, include original link at bottom.
   * Friendly errors and optional “insights” section when the model shares takeaways.
6. **Deployment readiness**
   * Container file or Procfile (optional).
   * README instructions for local testing, environment variables, and privacy policy statement.

### 8. Open questions / assumptions
* Which OpenAI model/tier is acceptable for production (4o mini vs 4o vs omne)? Any cost ceiling?
* Need to cap usage per chat/day?
* Should the bot support languages other than English at MVP?
* Any preference for hosting stack (Docker, systemd, etc.)?

This plan keeps SudoLink narrowly focused on “link expansion” and prepares the codebase for future extras like grouping results or domain blocklists without deviating into fact checking.
