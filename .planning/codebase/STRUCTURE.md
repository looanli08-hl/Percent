# Codebase Structure

**Analysis Date:** 2026-04-11

## Directory Layout

```
percent/                          # Root package
├── __init__.py                   # Version string
├── cli.py                         # CLI entry point (Typer app)
├── config.py                      # Config model + YAML persistence
├── models.py                      # Pydantic data models
├── web.py                         # FastAPI server + static serving
│
├── llm/                           # LLM provider abstraction
│   ├── __init__.py
│   └── client.py                 # LLMClient, UsageStats
│
├── parsers/                       # Data source adapters
│   ├── __init__.py               # Exports public parsers
│   ├── base.py                   # DataParser abstract base
│   ├── wechat.py                 # WeChat CSV/JSON parser
│   ├── wechat_db.py              # WeChat SQLite DB parser
│   ├── telegram.py               # Telegram JSON parser
│   ├── telegram_api.py           # Telegram API via Telethon
│   ├── youtube.py                # YouTube Takeout parser
│   ├── youtube_api.py            # YouTube API via cookie
│   ├── bilibili.py               # Bilibili history parser
│   ├── bilibili_api.py           # Bilibili API
│   ├── whatsapp.py               # WhatsApp text export
│   └── xiaohongshu.py            # Xiaohongshu history
│
├── persona/                       # Personality modeling engine
│   ├── __init__.py
│   ├── engine.py                 # PersonaEngine (orchestrator)
│   ├── extractor.py              # PersonaExtractor (LLM findings)
│   ├── fragments.py              # FragmentStore (SQLite + vector)
│   ├── synthesizer.py            # PersonaSynthesizer (core.md)
│   ├── validator.py              # PersonaValidator (PersonaBench)
│   ├── cross_validate.py         # Cross-source corroboration
│   ├── fingerprint.py            # BehavioralFingerprint (stats)
│   ├── spectrum.py               # SpectrumEngine (8 dimensions)
│   ├── big_five.py               # Big Five personality traits
│   ├── bench.py                  # PersonaBench test suite
│   └── manifest.py               # ImportManifest (history)
│
├── chat/                          # Conversation engine
│   ├── __init__.py
│   └── engine.py                 # ChatEngine (persona + memory)
│
├── export/                        # Output formatters
│   ├── __init__.py
│   └── soul_md.py                # SOUL.md exporter
│
├── prompts/                       # LLM prompt templates
│   ├── __init__.py
│   ├── extract.md                # Finding extraction template
│   ├── synthesize.md             # Profile synthesis template
│   ├── validate.md               # PersonaBench validation
│   ├── deep_analyze.md           # Cross-source analysis
│   ├── chat_system.md            # Chat system prompt
│   ├── big_five.md               # Big Five computation
│   ├── soul_export.md            # SOUL.md generation
│   └── spectrum_label.md         # Dimension interpretation
│
├── static/                        # Web UI assets
│   ├── index.html
│   ├── style.css
│   └── app.js
│
└── docs/                          # Project documentation
    └── specs/                     # Feature specifications

tests/                            # Test suite (mirrors src structure)
├── conftest.py                   # Shared fixtures
├── test_chat.py
├── test_config.py
├── test_export.py
├── test_llm.py
├── test_models.py
├── test_cross_validate.py
├── test_big_five.py
├── test_web_*.py                 # Web endpoint tests
├── test_parsers/                 # Parser tests
│   ├── test_bilibili.py
│   ├── test_bilibili_api.py
│   ├── test_telegram.py
│   ├── test_wechat.py
│   ├── test_whatsapp.py
│   ├── test_xiaohongshu.py
│   └── test_youtube.py
└── test_persona/                 # Persona component tests
    ├── test_bench.py
    └── test_engine.py

pyproject.toml                    # Project metadata, dependencies, build config
uv.lock                           # Lock file (uv package manager)
README.md                         # English docs
README_CN.md                      # Chinese docs
ROADMAP.md                        # Feature roadmap
LICENSE                           # MIT license

.planning/
└── codebase/                     # GSD mapping documents
    ├── ARCHITECTURE.md
    └── STRUCTURE.md
```

## Directory Purposes

**percent/:**
- Purpose: Main package
- Contains: Core logic, CLI, Web server
- Key files: `cli.py` (user-facing), `config.py` (settings), `models.py` (schemas)

**percent/llm/:**
- Purpose: LLM provider abstraction
- Contains: Multi-provider routing (Claude, GPT-4, DeepSeek, Ollama)
- Key files: `client.py` - unified interface + usage tracking

**percent/parsers/:**
- Purpose: Data source normalization
- Contains: 8+ source-specific adapters (WeChat, Telegram, YouTube, Bilibili, etc.)
- Key files: `base.py` (abstract interface), one file per source

**percent/persona/:**
- Purpose: Personality modeling pipeline
- Contains: Extract → Store → Synthesize → Validate → Export
- Key files:
  - `engine.py`: Orchestrator
  - `fragments.py`: Vector store (SQLite)
  - `synthesizer.py`: Profile generation
  - `spectrum.py`: Dimension scoring
  - `fingerprint.py`: Behavioral analysis

**percent/chat/:**
- Purpose: Conversation with persona
- Contains: Memory retrieval + LLM integration
- Key files: `engine.py` - maintain history, retrieve context

**percent/export/:**
- Purpose: Format conversion (core.md → SOUL.md, etc.)
- Contains: Export engines
- Key files: `soul_md.py` - OpenClaw format

**percent/prompts/:**
- Purpose: LLM instruction templates
- Contains: Markdown prompts for extraction, synthesis, validation
- Key files: All .md files are prompt templates with variable placeholders

**percent/static/:**
- Purpose: Web UI assets
- Contains: HTML, CSS, JavaScript
- Key files: `index.html` (entry point), `app.js` (client logic)

**tests/:**
- Purpose: Test suite
- Contains: Unit tests, integration tests, fixtures
- Key files: `conftest.py` (shared fixtures), mirrored module tests

## Key File Locations

**Entry Points:**
- `percent/cli.py`: CLI (run: `percent import run ...`, `percent chat`, etc.)
- `percent/web.py`: Web server (run: `percent web`)
- `pyproject.toml`: Package entry (script: `percent = "percent.cli:app"`)

**Configuration:**
- `percent/config.py`: Config model + loaders
- `~/.percent/config.yaml`: Runtime config (created by `percent init`)
- `pyproject.toml`: Build config, dependencies, lint rules

**Core Logic:**
- `percent/persona/engine.py`: Main pipeline orchestrator
- `percent/persona/fragments.py`: Vector store (SQLite)
- `percent/llm/client.py`: LLM provider abstraction
- `percent/parsers/base.py`: Parser interface

**Data Models:**
- `percent/models.py`: Pydantic schemas (DataChunk, Finding, Fragment)

**Tests:**
- `tests/conftest.py`: Fixtures (tmp_percent_dir, mock_llm_response)
- `tests/test_persona/test_engine.py`: Main pipeline tests

## Naming Conventions

**Files:**
- Module files: `snake_case.py` (e.g., `cross_validate.py`, `big_five.py`)
- Base classes: `base.py` (e.g., `parsers/base.py`)
- Entry points: `cli.py`, `web.py`, `engine.py`

**Directories:**
- Package folders: `lowercase` with `__init__.py` (e.g., `llm/`, `parsers/`, `persona/`)
- Test folders: `test_<module>/` or `test_<module>.py` (mirrors src structure)

**Classes:**
- Parsers: `<Source>Parser` (e.g., `WeChatParser`, `TelegramParser`)
- Engines: `<Component>Engine` (e.g., `PersonaEngine`, `ChatEngine`)
- Stores: `<Component>Store` (e.g., `FragmentStore`)
- Exporters: `<Format>Exporter` (e.g., `SoulMdExporter`)

**Functions:**
- Private/internal: `_snake_case()` (e.g., `_load_prompt()`, `_parse_findings()`)
- Public: `snake_case()` (e.g., `validate()`, `parse()`)

**Enums:**
- `CamelCase` values in StrEnum (e.g., `CONVERSATION`, `TRAIT`)

## Where to Add New Code

**New Data Source Parser:**
- Implementation: Create `percent/parsers/<source_name>.py` inheriting from `DataParser`
- Register: Add to `_PARSER_REGISTRY` dict in `percent/cli.py`
- Tests: Create `tests/test_parsers/test_<source_name>.py`
- Example: `percent/parsers/wechat.py` shows full pattern with validation, parsing, import guide

**New Persona Analysis (e.g., new spectrum dimension):**
- Implementation: Add method to `percent/persona/spectrum.py` (SpectrumEngine class)
- Or create new file: `percent/persona/<analysis_name>.py` with analyzer class
- Register in CLI: Add command in `percent/cli.py` under `persona_app`
- Tests: Add to `tests/test_persona/` directory
- Example: `big_five.py` shows standalone analyzer pattern

**New LLM-based Feature:**
- Prompt template: Create `percent/prompts/<feature_name>.md`
- Implementation: Use existing `LLMClient` from `percent/llm/client.py`
- Load prompt: Call `_load_prompt(prompts_dir)` with fallback
- Register in CLI: Add to appropriate typer.Typer subcommand
- Example: `synthesizer.py` → `synthesize.md` shows pattern

**New Web Endpoint:**
- Implementation: Add `@app.get()` or `@app.post()` to `percent/web.py`
- Response models: Use Pydantic in `percent/web.py` for request/response schemas
- Frontend: Update `percent/static/app.js` or add new `.html` file
- Tests: Create `tests/test_web_<feature>.py`
- Example: `@app.get("/api/insights")` shows typical pattern

**Utilities/Helpers:**
- Shared helpers: `percent/<module>/utils.py` (if component-specific)
- Cross-component: Functions in existing modules or new `percent/utils.py`
- Example: `_load_prompt()` pattern repeated across components

## Special Directories

**~/.percent/:**
- Purpose: User data directory
- Generated: Yes (created by `percent init`)
- Committed: No (excluded in .gitignore)
- Contents:
  - `config.yaml`: API keys, LLM settings
  - `core.md`: Current personality profile
  - `fragments.db`: SQLite vector store
  - `fingerprint.json`: Behavioral statistics
  - `imports.json`: Import history
  - `big_five.json`: Big Five scores (optional)
  - `raw/`: Raw data exports (optional)

**.planning/codebase/:**
- Purpose: GSD analysis documents
- Generated: Yes (by `/gsd:map-codebase`)
- Committed: Yes
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md

**tests/:**
- Purpose: Test suite
- Generated: No (committed)
- Contains: pytest test files with fixtures
- Pattern: One test file per module (test_<module>.py) + subdirs for nested packages

**percent/static/:**
- Purpose: Web UI assets
- Generated: No (committed)
- Contains: HTML, CSS, JavaScript for Web UI
- Served by: FastAPI static handler in `web.py`

---

*Structure analysis: 2026-04-11*
