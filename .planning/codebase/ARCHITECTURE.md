# Architecture

**Analysis Date:** 2026-04-11

## Pattern Overview

**Overall:** Layered pipeline with independent stages chained via data models

**Key Characteristics:**
- Five-stage processing pipeline: Parse → Extract → Store → Synthesize → Export/Chat
- Heavy use of LLM APIs with optional local models (Ollama support)
- Local-first storage with SQLite + vector embeddings
- Pluggable parser interface for multi-source data ingestion
- Persona artifact (core.md) as central output used by multiple consumers

## Layers

**Data Parser Layer:**
- Purpose: Normalize raw exports from diverse sources into standardized `DataChunk` objects
- Location: `percent/parsers/`
- Contains: Source-specific parsers (WeChat, Telegram, YouTube, Bilibili, WhatsApp, Xiaohongshu)
- Depends on: `percent.models.DataChunk`, external file formats (CSV, JSON, SQLite)
- Used by: CLI import commands, PersonaEngine

**LLM Integration Layer:**
- Purpose: Unified interface to multiple LLM providers with usage tracking and cost estimation
- Location: `percent/llm/client.py`
- Contains: `LLMClient` (provider abstraction), `UsageStats` (cost tracking)
- Depends on: litellm library, provider API keys
- Used by: Extractor, Synthesizer, Validator, ChatEngine, ExportEngine

**Persona Extraction & Processing Layer:**
- Purpose: Convert raw data chunks into personality findings, manage fragment store, validate and synthesize profiles
- Location: `percent/persona/`
- Contains:
  - `engine.py`: Orchestrates full pipeline (extract → embed → store → synthesize → validate)
  - `extractor.py`: LLM-based finding extraction from chunks
  - `fragments.py`: SQLite store with embeddings and deduplication
  - `synthesizer.py`: Condenses findings into core.md
  - `validator.py`: PersonaBench validation against actual data
  - `cross_validate.py`: Cross-source corroboration and confidence adjustment
  - `fingerprint.py`: Statistical behavior extraction (no LLM, pure analysis)
  - `spectrum.py`: Personality dimension scoring (rule-based, no LLM)
  - `big_five.py`: Big Five trait computation via LLM
  - `bench.py`: Test suite for benchmarking
  - `manifest.py`: Track import history
- Depends on: LLMClient, DataChunk, Fragment models, sentence-transformers
- Used by: CLI commands, Web API, ChatEngine

**Data Models Layer:**
- Purpose: Pydantic schemas for type safety across pipeline stages
- Location: `percent/models.py`
- Contains: `DataChunk`, `Finding`, `Fragment`, enums (ChunkType, FindingCategory)
- Depends on: pydantic
- Used by: All layers

**Configuration Layer:**
- Purpose: Centralized config management for API keys, LLM settings, paths
- Location: `percent/config.py`
- Contains: `PercentConfig`, `load_config()`, `save_config()` (YAML-based)
- Depends on: YAML file at `~/.percent/config.yaml`
- Used by: CLI init, all services requiring LLM credentials

**Chat & Conversation Layer:**
- Purpose: Persona-grounded conversational interface with memory retrieval
- Location: `percent/chat/engine.py`
- Contains: `ChatEngine` (maintains conversation history, retrieves relevant fragments)
- Depends on: core.md, FragmentStore, LLMClient, sentence-transformers
- Used by: CLI chat command, Web chat endpoint

**Export Layer:**
- Purpose: Convert core.md into other formats for external use
- Location: `percent/export/soul_md.py`
- Contains: `SoulMdExporter` (exports to OpenClaw SOUL.md format)
- Depends on: LLMClient, core.md
- Used by: `percent export soul` command, Web API

**CLI Entry Point:**
- Purpose: Command-line interface to all Percent functionality
- Location: `percent/cli.py`
- Contains: Typer app with subcommands (init, import, persona, export, chat, config)
- Depends on: All layers
- Used by: End users, shell scripts

**Web Server:**
- Purpose: FastAPI-based UI for persona viewing, chat, insights
- Location: `percent/web.py`
- Contains: REST endpoints for persona/stats/insights/spectrum, chat endpoint
- Depends on: All layers, FastAPI, uvicorn
- Used by: Web UI (JavaScript frontend in static/)

## Data Flow

**Import & Extraction (percent import run):**

1. User runs `percent import run <source> <path>`
2. Parser loads raw data, validates format, yields `DataChunk` objects
3. PersonaEngine receives chunks, passes to PersonaExtractor
4. Extractor groups chunks into batches, sends to LLM with extract.md prompt
5. LLM returns findings (JSON with category, content, confidence, evidence)
6. Findings are embedded using sentence-transformers
7. Embeddings stored in FragmentStore (SQLite with deduplication by content hash)
8. ImportManifest records metadata (timestamp, source, artifacts generated)

**Synthesis (PersonaEngine.run):**

1. Retrieve all fragments from store
2. Convert to Finding objects
3. Pass to PersonaSynthesizer with synthesize.md prompt
4. LLM generates core.md (structured markdown with sections)
5. core.md written to `~/.percent/core.md`
6. BehavioralFingerprint extracted from original chunks (statistical analysis)
7. Fingerprint written to `~/.percent/fingerprint.json`

**Chat Session (ChatEngine.send):**

1. User sends message
2. Message embedding computed via sentence-transformers
3. Query fragments from store (similarity search, top-k=5)
4. System prompt built: core.md + relevant fragments + chat_system.md template
5. Full conversation history + system prompt sent to LLM
6. Response captured, added to history, returned to user

**State Management:**

- **Persistent state:** `~/.percent/` directory structure:
  - `config.yaml`: LLM provider, model, API key, embedding model
  - `core.md`: Current personality profile
  - `fragments.db`: SQLite with all findings, embeddings, evidence
  - `fingerprint.json`: Behavioral statistics
  - `imports.json`: Import history metadata
  - `big_five.json`: Big Five scoring result (optional)
  - `raw/`: Raw data exports (optional storage)

- **In-memory state:** PersonaEngine, ChatEngine maintain references to config, stores, embedder

## Key Abstractions

**DataParser:**
- Purpose: Abstract interface for source-specific parsers
- Location: `percent/parsers/base.py`
- Pattern: Abstract base class with `validate()`, `parse()`, `get_import_guide()` methods
- Examples: `WeChatParser`, `TelegramParser`, `YouTubeParser`, `BilibiliParser`

**LLMClient:**
- Purpose: Abstraction over multiple LLM providers (Claude, GPT-4, DeepSeek, Ollama)
- Location: `percent/llm/client.py`
- Pattern: Constructor takes provider string, automatically routes to litellm
- Features: Automatic usage tracking, cost estimation from pricing table

**FragmentStore:**
- Purpose: Unified interface to SQLite persistence with embedding search
- Location: `percent/persona/fragments.py`
- Pattern: Wraps sqlite3.Connection with deduplication, migration support, vector similarity
- Key methods: `add()`, `get_all()`, `get_similar()`, `stats()`, `get_cross_source_insights()`

**PersonaEngine:**
- Purpose: Orchestrates the complete pipeline from chunks to core.md
- Location: `percent/persona/engine.py`
- Pattern: Constructor takes LLMClient + config paths, `run()` method executes full pipeline
- Coordinates: Extractor, FragmentStore, Synthesizer, Validator, BehavioralFingerprint

## Entry Points

**CLI (percent/cli.py):**
- Location: `percent/cli.py`
- Triggers: User shell commands (e.g., `percent import run wechat ~/data.csv`)
- Responsibilities:
  - Parse command-line arguments via typer
  - Load config from `~/.percent/`
  - Instantiate parsers, engines, services
  - Format and display output (Rich tables, text)
  - Handle errors with user-friendly messages

**Web Server (percent/web.py):**
- Location: `percent/web.py`
- Triggers: User runs `percent web` or `python -m percent.web`
- Responsibilities:
  - Load config on startup
  - Initialize ChatEngine (if core.md exists)
  - Serve REST API (GET /api/persona, /api/stats, /api/insights, /api/spectrum, POST /api/chat)
  - Serve static assets (HTML, JS, CSS)
  - Handle CORS for frontend

**Tests (tests/):**
- Location: `tests/` with mirrored structure
- Triggers: `pytest` command
- Responsibilities:
  - Fixture setup (tmp_percent_dir, mock_llm_response)
  - End-to-end pipeline tests
  - Parser validation tests
  - Component unit tests

## Error Handling

**Strategy:** Validate early, fail with helpful messages

**Patterns:**

1. **Parser validation:** `validate()` before `parse()` prevents silent failures
   - Example: WeChatParser checks CSV column names before reading
   - Raises: typer.Exit(1) with colored error message

2. **Config validation:** Pydantic models auto-validate on construction
   - Example: LLMClient requires valid provider string
   - Raises: ValueError if fields are invalid

3. **LLM response parsing:** JSON extraction with fallback templates
   - Example: PersonaExtractor searches for `[...]` blocks, catches JSONDecodeError
   - Returns: Empty list if parsing fails, logs warning

4. **Storage errors:** SQLite deduplication via content_hash prevents duplicate fragments
   - Example: FragmentStore.add() checks hash before INSERT
   - Returns: Existing fragment ID if duplicate detected

## Cross-Cutting Concerns

**Logging:**
- Approach: Mix of rich.console for CLI output and Python logging for Web API
- Pattern: No centralized logger; each module uses print() or logging.getLogger(__name__)
- Verbosity: Minimal by default; use Rich progress bars for long operations

**Validation:**
- Approach: Pydantic BaseModel for all data structures
- Pattern: Enums (ChunkType, FindingCategory) for type safety
- Pipeline: Parser output → Pydantic DataChunk → LLM extraction → Pydantic Finding → Storage

**Authentication:**
- Approach: Environment variables + config file for API keys
- Pattern: LLMClient accepts api_key parameter, passes to litellm
- Storage: `~/.percent/config.yaml` (user responsible for securing)

**Embedding & Similarity:**
- Approach: sentence-transformers (all-MiniLM-L6-v2 default, configurable)
- Pattern: Encode all findings during extraction, store as JSON in DB
- Search: Cosine similarity over normalized vectors in FragmentStore

**Monitoring:**
- Approach: UsageStats tracks input/output tokens per LLM call
- Pattern: LLMClient._track_usage() called after every completion
- Output: format_report() shows total cost estimate per provider/model

---

*Architecture analysis: 2026-04-11*
