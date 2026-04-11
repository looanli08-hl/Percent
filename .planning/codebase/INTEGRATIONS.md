# External Integrations

**Analysis Date:** 2026-04-11

## APIs & External Services

**Personality LLM (Primary):**
- **Claude (Anthropic)** - Default personality modeling and synthesis
  - SDK/Client: `litellm` (unified wrapper)
  - Auth: Environment variable via LLM provider config (`llm_api_key` in `~/.percent/config.yaml`)
  - Model: `claude-sonnet-4-20250514` (default, configurable)
  - Usage: `percent.llm.client.LLMClient` class
  - Endpoints: Via LiteLLM routing

**Alternative LLM Providers:**
- **OpenAI (GPT-4, GPT-4o-mini)** - Switchable via config
  - Provider: "openai" - Set `llm_provider` in config
- **DeepSeek** - Fast, cost-effective alternative
  - Provider: "deepseek" - Set `llm_provider` in config
- **Ollama** - Local LLM processing (privacy-first)
  - Provider: "ollama" - Set `llm_provider` in config
- **OpenRouter** - Multi-model aggregation
  - Provider: "openrouter" - Set `llm_provider` in config

**Platform Data APIs (Real-time):**

**Bilibili (B站):**
- API: `https://api.bilibili.com/x/web-interface/history/cursor` - Watch history fetch
  - SDK/Client: `requests` library
  - Auth: Browser cookie (`SESSDATA`, etc.) - stored in `~/.percent/raw/bilibili/bilibili_cookie.txt`
  - Implementation: `percent.parsers.bilibili_api.fetch_bilibili_history()`
  - Features: Pagination via `view_at` cursor, rate-limited to 50 pages (~1000 videos)
  - Data: Video title, URL, watch timestamp

**YouTube:**
- API: `https://www.youtube.com/youtubei/v1/browse` - Internal browsing API
  - SDK/Client: `requests` library
  - Auth: Browser cookie (SID, HSID, SSID, etc.) - stored in `~/.percent/raw/youtube/youtube_cookie.txt`
  - SAPISIDHASH header: Generated from cookie for authorization
  - Implementation: `percent.parsers.youtube_api.fetch_youtube_history()`
  - Features: Continuation tokens for pagination (up to 20 pages)
  - Data: Video title, channel, watch timestamp

**Telegram (Instant Messaging):**
- API: Telegram Client API (via Telethon SDK)
  - SDK/Client: **Telethon** 1.36+ (optional dependency, installed separately)
  - Auth: API credentials (api_id, api_hash from `my.telegram.org`) + phone number
  - Phone-based auth flow: User provides credentials, receives one-time code
  - Implementation: `percent.parsers.telegram_api.fetch_telegram_history()` (async)
  - Features: Fetch personal chats only (DMs), message content + timestamps
  - Session persistence: Stored locally as `.percent_telegram`
  - Limits: Max 5000 messages per chat, recent 50 dialogs

## Data Sources (File-based)

**WeChat:**
- Format: CSV export or SQLite database backup
- Parsers: 
  - `percent.parsers.wechat.WeChatParser` - CSV file parsing
  - `percent.parsers.wechat_db.WeChatDBParser` - SQLite DB parsing
- Data: Message content, timestamps, contact metadata
- Import flow: User exports via WeChat client → `~/.percent/raw/wechat/` → parser extracts

**WhatsApp:**
- Format: Chat export (txt file with timestamp)
- Parser: `percent.parsers.whatsapp.WhatsAppParser` (`percent.parsers.whatsapp`)
- Data: Message content, contact, timestamps
- Import: User exports chat → `~/.percent/raw/whatsapp/` → parser extracts

**小红书 (Xiaohongshu/Little Red Book):**
- Format: Browser export via JavaScript utility
- Parser: `percent.parsers.xiaohongshu.XiaohongshuParser`
- Export method: Web scraping utility (`percent/static/xhs_export.js`) - Run in browser console
- Data: Post content, likes, comments, timestamps
- Import: User runs export script → Downloads JSON → `~/.percent/raw/xiaohongshu/`

## Data Storage

**Databases:**
- **SQLite** (local file)
  - Location: `~/.percent/fragments.db`
  - Client: `sqlite3` (built-in Python module, wrapped by `FragmentStore`)
  - Purpose: Stores personality fragments with embeddings and metadata
  - Schema: `fragments` table with columns: id, category, content, confidence, source, embedding, created_at, content_hash, evidence

**File Storage:**
- **Local filesystem only** - No cloud storage
  - Core profile: `~/.percent/core.md` (Markdown text)
  - Import history: `~/.percent/imports.json` (JSON)
  - Behavioral fingerprint: `~/.percent/fingerprint.json` (JSON)
  - Big Five scores: `~/.percent/big_five.json` (JSON)
  - Raw imported data: `~/.percent/raw/{source}/` (source-specific files)

**Caching:**
- None - No dedicated caching layer
- Embeddings cached in SQLite fragments table (`embedding` column)

## Authentication & Identity

**Auth Provider:**
- **Custom/Multi-provider approach** - No single auth provider
  - Claude: Anthropic API key
  - OpenAI: OpenAI API key
  - DeepSeek: DeepSeek API key
  - Telegram: Phone-based OAuth (via Telethon)
  - Bilibili/YouTube: Browser cookies (no API keys)

**Implementation:**
- CLI: `percent init` prompts user for LLM API key, stored in `~/.percent/config.yaml`
- Web: Uses config from file (no web-specific auth)
- Privacy: Keys stored locally, never transmitted except to respective LLM APIs

## Monitoring & Observability

**Error Tracking:**
- None detected - No error tracking service integration
- Local error handling: Try-catch blocks in parsers, console output via `rich`

**Logs:**
- **Console output** - Rich terminal formatting (`rich` library)
  - Log levels: Status messages, warnings, errors via Rich console
  - Implementation: `console.print()` in CLI, Uvicorn logs for web
- **Web logs:** Uvicorn server logs (log_level="warning" in `percent.web:start_server()`)
- No persistent logging to files or services

## CI/CD & Deployment

**Hosting:**
- **Local-first:** User's machine (`~/.percent/` directory)
- **Optional web:** Self-hosted Uvicorn server (localhost:18900)
- No cloud hosting, SaaS backend, or remote server (privacy-first design)

**CI Pipeline:**
- **GitHub Actions** - CI workflow detected (`.github/workflows/ci.yml`)
- Runs: Pytest, Ruff linting, MyPy type checking
- Triggered on: Git push, pull requests

**Deployment:**
- **CLI:** Install via `pip install percent` or `uv sync` from source
- **Web:** Run `percent web` command (starts Uvicorn on localhost)
- Package: Published to PyPI (referenced in `pyproject.toml`)

## Environment Configuration

**Required env vars:**
- `LLM_API_KEY` - API key for chosen LLM provider (or stored in `~/.percent/config.yaml`)
- No other environment variables required (all config via YAML file)

**Optional env vars:**
- None detected - All configuration via interactive `percent init` or YAML editing

**Secrets location:**
- `~/.percent/config.yaml` - Contains `llm_api_key` (plaintext file, user's home dir)
- Browser cookies (for Bilibili/YouTube APIs) - Stored in `~/.percent/raw/{source}/` (plaintext)
- Telegram session file - Stored as `~/.percent/.percent_telegram` (binary session data, user-controlled)

**Security notes:**
- All data stays local unless explicitly sent to LLM provider
- No telemetry, analytics, or remote logging
- User controls what data is shared with which LLM
- Cookies stored locally - user responsible for security

## Webhooks & Callbacks

**Incoming:**
- Web upload endpoint: `POST /api/import/upload` - File upload handler
- Web import endpoint: `POST /api/import/analyze` - Trigger analysis pipeline
- Chat endpoint: `POST /api/chat` - Send message to persona

**Outgoing:**
- None - No outbound webhooks or callbacks to external services
- One-way API calls to: Bilibili, YouTube, Telegram (data fetch only)
- LLM provider calls (OpenAI, Anthropic, DeepSeek, etc.) via LiteLLM

## Data Processing & AI Pipeline

**Embedding Service (Local):**
- **sentence-transformers** (Hugging Face models)
- Model: `all-MiniLM-L6-v2` (default)
- Process: Runs locally, no external API
- Used for: Fragment semantic similarity search in `ChatEngine`
- Output: Dense vector embeddings stored in SQLite

**Personality Extraction:**
- LLM-powered analysis of imported data chunks
- Implementation: `percent.persona.extractor.PersonaExtractor`
- Process: Batch chunks (default batch_size=20), send to LLM for analysis
- Output: `Fragment` objects (content, confidence, category, source)

**Cross-source Validation:**
- Validates fragments across multiple data sources
- Implementation: `percent.persona.cross_validate.DeepAnalyzer`
- Process: Checks consistency of findings across sources
- Output: Confidence adjustments, evidence linking

**Synthesis:**
- Generates `core.md` (personality profile markdown)
- Implementation: `percent.persona.synthesizer.PersonaSynthesizer`
- Process: Summarizes fragments into readable personality description
- Uses: LLM to synthesize, template system

---

*Integration audit: 2026-04-11*
