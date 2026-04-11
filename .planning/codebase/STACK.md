# Technology Stack

**Analysis Date:** 2026-04-11

## Languages

**Primary:**
- Python 3.12+ - All core logic, CLI, parsers, persona engine, chat engine, web server
- JavaScript - Web UI bootstrap, XHS export utility (`percent/static/xhs_export.js`)
- HTML/CSS - Web UI interface (`percent/static/index.html`)
- YAML - Configuration format for settings

**Secondary:**
- SQL - SQLite schema and queries in `percent/persona/fragments.py`

## Runtime

**Environment:**
- Python 3.12+ (specified in `pyproject.toml` with `requires-python = ">=3.12"`)
- macOS/Linux/Windows compatible (cross-platform via Python)

**Package Manager:**
- `uv` (used for dependency management - see `uv.lock` for lockfile)
- Fallback: pip (via hatchling build system)

## Frameworks

**Core:**
- **Typer** 0.15+ - CLI framework for command-line interface (`percent.cli`)
  - Subcommands: `import`, `persona`, `export`, `config`
- **FastAPI** 0.135.3+ - REST API server for web UI (`percent.web`)
- **Pydantic** 2.0+ - Data validation and settings management
  - Used in `percent/config.py` (PercentConfig), `percent/models.py` (DataChunk, Finding, Fragment)

**AI/LLM:**
- **LiteLLM** 1.40+ - Unified LLM provider abstraction (`percent/llm/client.py`)
  - Supports: Claude (Anthropic), OpenAI (GPT), DeepSeek, Ollama, OpenRouter
  - Client: `LLMClient` class handles provider routing and token tracking
- **sentence-transformers** 3.0+ - Embedding models for semantic search (`percent/chat/engine.py`, `percent/persona/engine.py`)
  - Default model: `all-MiniLM-L6-v2` (local, no API needed)
  - Used for fragment storage and semantic similarity search

**Data Processing:**
- **NumPy** 1.26+ - Numerical operations for embeddings
- **PyYAML** 6.0+ - YAML parsing for config files

**Web/HTTP:**
- **Requests** 2.31+ - HTTP client for external API calls (Bilibili, YouTube APIs) in parsers
- **Uvicorn** 0.43.0+ - ASGI server for FastAPI web application
- **python-multipart** 0.0.22+ - File upload handling in FastAPI

**Data Serialization:**
- **Zstandard** 0.25.0+ - Compression utility (imported but usage unclear from initial scan)

**Output/Formatting:**
- **Rich** 13.0+ - Terminal formatting and tables for CLI output

## Key Dependencies

**Critical:**
- **LiteLLM** - Core dependency for all LLM interactions, enables multi-provider support (Claude default)
- **sentence-transformers** - Enables local semantic embeddings without external API dependency
- **SQLite3** (built-in) - Fragment storage and persistence

**Infrastructure:**
- **FastAPI + Uvicorn** - Web server stack for `percent web` command
- **Typer** - Command-line interface backbone
- **Pydantic** - Configuration and data validation

**Optional:**
- **Telethon** 1.36+ - Optional dependency for Telegram API integration
  - Installed via: `pip install percent[telegram]`
  - Defined in `pyproject.toml` optional-dependencies

## Configuration

**Environment:**
- Configuration file: `~/.percent/config.yaml` (YAML format, user-created at init)
- Config fields (persisted):
  - `llm_provider` - LLM provider name (default: "claude")
  - `llm_model` - Model identifier (default: "claude-sonnet-4-20250514")
  - `llm_api_key` - API key for LLM provider (stored in config, user-supplied)
  - `embedding_model` - Embedding model name (default: "all-MiniLM-L6-v2")
  - `core_rebuild_threshold` - Fragment threshold for core.md regeneration (default: 10)
  - `percent_dir` - Home directory for all data (default: `~/.percent`)

**Data Directories:**
- `~/.percent/` - User data home
  - `core.md` - Generated personality profile
  - `fragments.db` - SQLite database of personality fragments
  - `raw/` - Imported raw data by source subdirectory
  - `config.yaml` - User configuration
  - `imports.json` - Import history manifest
  - `fingerprint.json` - Behavioral fingerprint data
  - `big_five.json` - Big Five personality scores

**Build:**
- `pyproject.toml` - Modern Python package metadata, dependencies, tool configs
- `uv.lock` - UV package manager lockfile (reproducible builds)
- Build backend: **hatchling** (configured in build-system)

## Platform Requirements

**Development:**
- Python 3.12+
- System dependencies: None (pure Python except optional Telethon for Telegram)
- Optional: `uv` package manager for faster installs

**Production:**
- **Deployment target:** Local CLI or self-hosted web server
  - CLI: Direct Python execution on user machine
  - Web: Uvicorn server listens on `127.0.0.1:18900` (localhost only, no remote)
  - Data storage: User's local filesystem (`~/.percent/`)
- **Architecture:** CPU-only (no GPU required)
  - Embeddings use CPU-friendly `all-MiniLM-L6-v2` model
  - LLM calls via external API (no local model inference by default)

## Package Entry Points

**CLI:**
- `percent` command - Main CLI entry point via Typer (`percent.cli:app`)
- Sub-commands: `percent init`, `percent import`, `percent persona`, `percent export`, `percent config`, `percent chat`, `percent web`

**Web:**
- FastAPI app: `percent.web:app`
- Server start: `percent web` command or direct `uvicorn percent.web:app --port 18900`

## Tool Configuration

**Code Quality:**
- **Ruff** 0.8+ - Linter (dev dependency)
  - Config: `pyproject.toml` [tool.ruff]
  - Target: Python 3.12, line length 100
  - Rules selected: E, F, I, UP (errors, undefined names, imports, upgrades)

**Type Checking:**
- **MyPy** 1.13+ - Static type checker (dev dependency)
  - Config: `pyproject.toml` [tool.mypy]
  - Python version: 3.12
  - Warnings enabled for `return_any`, `unused_configs`

**Testing:**
- **Pytest** 8.0+ - Test runner (dev dependency)
  - Config: `pyproject.toml` [tool.pytest.ini_options]
  - Test path: `tests/`
  - Python path: `.` (root)
- **pytest-asyncio** 0.23+ - Async test support (dev dependency)

---

*Stack analysis: 2026-04-11*
