# Coding Conventions

**Analysis Date:** 2026-04-11

## Naming Patterns

**Files:**
- Lowercase with underscores: `wechat.py`, `fragment_store.py`, `llm_client.py`
- Parser modules follow the pattern: `{platform}.py` (e.g., `telegram.py`, `youtube.py`)
- Special suffixes for variants: `wechat_db.py`, `telegram_api.py` for alternate implementations

**Functions:**
- Lowercase with underscores following PEP 8: `_detect_csv_format()`, `_validate_single_file()`, `_hash_content()`
- Private functions prefixed with single underscore: `_get_parser()`, `_load_template()`, `_track_usage()`
- Public methods in classes without prefix: `parse()`, `validate()`, `send()`, `complete()`
- Descriptive verb-first: `extract()`, `synthesize()`, `validate()`, `complete_chat()`

**Variables:**
- Lowercase with underscores: `percent_dir`, `llm_api_key`, `total_input_tokens`, `response_text`
- Constants in UPPERCASE with underscores: `_PARSER_REGISTRY`, `_PRICING`, `_TEXT_TYPES`, `_CSV_FORMATS`, `_WINDOW_GAP_SECONDS`
- Private module constants prefixed with underscore: `_DEFAULT_MODEL`, `_DEFAULT_PROMPTS_DIR`, `_FALLBACK_SYSTEM`
- Temporary/loop variables single letter only when self-evident (rarely used)

**Types:**
- PEP 484 union syntax preferred: `str | None`, `dict[str, str] | None`, `list[DataChunk]`
- Classes use PascalCase: `DataChunk`, `FindingCategory`, `Fragment`, `PersonaEngine`
- Enum classes extend `StrEnum`: `ChunkType(StrEnum)`, `FindingCategory(StrEnum)`
- Type hints on all function parameters and returns

## Code Style

**Formatting:**
- Line length: 100 characters (from `pyproject.toml`)
- Ruff formatter enforces style (configured in `pyproject.toml` under `[tool.ruff]`)
- No explicit trailing commas or complex formatting preferences observed

**Linting:**
- Ruff configured in `pyproject.toml` with rules: `["E", "F", "I", "UP"]`
  - E: pycodestyle errors
  - F: Pyflakes
  - I: isort (import sorting)
  - UP: pyupgrade (modern syntax)
- Target Python version: 3.12 (from `requires-python = ">=3.12"`)
- MyPy strict checking enabled:
  - `warn_return_any = true`
  - `warn_unused_configs = true`
  - `ignore_missing_imports = true` (for untyped dependencies)

## Import Organization

**Order:**
1. `from __future__ import annotations` — Always first (future compatibility)
2. Standard library imports (`pathlib`, `json`, `csv`, `datetime`)
3. Third-party imports (`pydantic`, `typer`, `rich`, `litellm`, `sentence_transformers`)
4. Relative project imports (`percent.models`, `percent.parsers.base`)

**Path Aliases:**
- All imports use absolute imports: `from percent.models import DataChunk`
- No relative imports (no `from .models import`) observed
- Lazy imports allowed in CLI context for performance: `import importlib`

**Examples:**
```python
from __future__ import annotations

from pathlib import Path
import json

import typer
from rich.console import Console
from pydantic import BaseModel

from percent.models import DataChunk
from percent.parsers.base import DataParser
```

## Error Handling

**Patterns:**
- Catch specific exceptions, not bare `except:`
- Files and parsing use granular exceptions:
  ```python
  except (OSError, csv.Error):
      return False
  ```
  ```python
  except json.JSONDecodeError:
      return False
  ```
- CLI commands use `typer.Exit(1)` for error exits with console message:
  ```python
  console.print(f"[red]Unknown source '{source}'[/red]")
  raise typer.Exit(1)
  ```
- LLM client lets exceptions propagate (no try/catch in `complete()` method)
- Fragment store handles migration errors with try/except for schema changes:
  ```python
  try:
      self._conn.execute("SELECT content_hash FROM fragments LIMIT 1")
  except sqlite3.OperationalError:
      self._conn.execute("ALTER TABLE fragments ADD COLUMN content_hash TEXT")
  ```

## Logging

**Framework:** Rich console library (`from rich.console import Console`)

**Patterns:**
- Status messages formatted with Rich markup: `[yellow]...[/yellow]`, `[green]...[/green]`, `[red]...[/red]`, `[cyan]...[/cyan]`
- Console created as module-level singleton: `console = Console()` in `cli.py`
- Info/debug using markup: `console.print("[cyan]Fetching Bilibili watch history...[/cyan]")`
- Warnings in yellow: `console.print(f"[yellow]Warning: {msg}[/yellow]")`
- Errors in red: `console.print(f"[red]Error: {msg}[/red]")`
- Success in green: `console.print(f"[green]Success: {msg}[/green]")`
- No traditional logging module (logging, logger) used — all via Rich

## Comments

**When to Comment:**
- Comment complex algorithms and non-obvious business logic
- Comment data format details (e.g., CSV column mappings in `_CSV_FORMATS`)
- Comment constant definitions to explain magic numbers:
  ```python
  _WINDOW_GAP_SECONDS = 30 * 60  # 30 minutes
  ```

**JSDoc/TSDoc:**
- Python uses docstrings (PEP 257) on public classes and methods
- Format: Triple-quoted strings immediately after `def`/`class`:
  ```python
  def validate(self, path: Path) -> bool:
      """Check if the file/directory is valid for this parser."""
  ```
  ```python
  class ChatEngine:
      """
      Persona-grounded conversational chat engine.

      Retrieves relevant memory fragments for each user message, builds a
      personalised system prompt from core.md + fragments, then calls the LLM
      via complete_chat() while maintaining full conversation history.
      """
  ```
- Private methods typically lack docstrings unless behavior is complex
- Multi-line docstrings follow: summary line, blank line, detailed description

## Function Design

**Size:** Functions average 5-30 lines; complex pipelines up to 50 lines

**Parameters:**
- Maximum 5-6 parameters before considering builder/config pattern
- Optional parameters after required ones
- Type hints on all parameters with union syntax: `path: Path | None = None`
- Defaults for optional params: `batch_size: int = 20`

**Return Values:**
- Explicit return type hints on all functions
- Return early pattern common: Multiple `return` statements acceptable if clear
- Void functions annotated `-> None` explicitly
- Single responsibility preferred: Parse functions return `list[DataChunk]`, never side effects

## Module Design

**Exports:**
- Modules export concrete classes/functions, not everything
- Base classes provide abstract interfaces: `DataParser` in `percent/parsers/base.py`
- No `__all__` lists observed (implicit public API)

**Barrel Files:**
- Limited barrel file usage observed
- `percent/__init__.py` exports only `__version__`
- `percent/parsers/__init__.py` empty (parsers loaded dynamically via registry)
- `percent/llm/__init__.py` empty (client imported directly)

## Architectural Conventions

**Section Comments:**
- Long functions use decorative separator comments for internal sections:
  ```python
  # ── public API ──────────────────────────────────────────────────────────
  ```
  ```python
  # ─── helpers ────────────────────────────────────────────────────────────────
  ```

**Module Layout:**
1. Module docstring
2. `from __future__ import annotations`
3. Standard library imports
4. Third-party imports
5. Relative imports
6. Constants
7. Helper functions (prefixed with `_`)
8. Public classes/functions
9. Module-level callable setup (e.g., CLI app registration)

**Classes:**
- Single responsibility principle observed
- Abstract base classes for interfaces: `DataParser(ABC)` with `@abstractmethod` decorators
- Dataclasses for simple data carriers: `UsageStats` uses `@dataclass`
- Pydantic models for configuration: `PercentConfig(BaseModel)`, `DataChunk(BaseModel)`

---

*Convention analysis: 2026-04-11*
