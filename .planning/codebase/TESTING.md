# Testing Patterns

**Analysis Date:** 2026-04-11

## Test Framework

**Runner:**
- Pytest 8.0+ (from `pyproject.toml`)
- Config: `.planning/codebase/../../../pyproject.toml` under `[tool.pytest.ini_options]`
  - `testpaths = ["tests"]`
  - `pythonpath = ["."]` — allows importing `percent` directly in tests

**Assertion Library:**
- Pytest's standard `assert` statements (no additional assertion library)

**Run Commands:**
```bash
pytest                    # Run all tests in tests/
pytest tests/test_config.py      # Run specific file
pytest -v                        # Verbose output
pytest --tb=short               # Shorter traceback
```

Coverage not currently enforced in config (no `pytest-cov` in dependencies), but `mypy` type checking is run via dev dependencies.

## Test File Organization

**Location:**
- Co-located with source: Tests in `tests/` directory parallel to `percent/` source
- Test structure mirrors source structure:
  - `percent/parsers/` → `tests/test_parsers/`
  - `percent/persona/` → `tests/test_persona/`
  - `percent/chat/` → `tests/test_chat.py`

**Naming:**
- Test files: `test_{module}.py` (e.g., `test_config.py`, `test_models.py`)
- Test functions: `test_{feature}()` or `test_{class}_{method}()` in simple cases
- Test classes: `Test{ClassName}` for grouping related tests (e.g., `TestChatEngine`, `TestPersonaValidator`)

**Structure:**
```
tests/
├── conftest.py                 # Shared fixtures
├── test_config.py              # Simple tests (no class)
├── test_models.py              # Pydantic model tests
├── test_llm.py                 # LLM client tests
├── test_chat.py                # ChatEngine tests (grouped in class)
├── test_parsers/               # Parser tests organized by source
│   ├── __init__.py
│   ├── test_wechat.py
│   ├── test_telegram.py
│   └── test_youtube.py
└── test_persona/               # Persona pipeline tests
    ├── __init__.py
    ├── test_engine.py
    ├── test_extractor.py
    └── test_synthesizer.py
```

## Test Structure

**Suite Organization:**
```python
# Simple test function (for straightforward units)
def test_default_config():
    config = PercentConfig()
    assert config.llm_provider == "claude"

# Test class grouping related tests
class TestChatEngine:
    """Tests for ChatEngine — mocks SentenceTransformer and FragmentStore."""

    @pytest.fixture(autouse=True)
    def patch_embedder(self):
        """Auto-patched fixture for every test in class."""
        dummy = make_dummy_embedder()
        with patch("percent.chat.engine.SentenceTransformer", return_value=dummy):
            yield dummy

    def test_send_builds_prompt_with_core_and_fragments_returns_response(
        self, tmp_percent_dir, mock_llm_response
    ):
        """send() uses core.md + retrieved fragments in system prompt, returns LLM reply."""
        mock_llm_response(CHAT_RESPONSE)
        # ... test body
```

**Patterns:**
- Setup: Fixtures injected as function parameters (`tmp_percent_dir`, `mock_llm_response`)
- No explicit setUp/tearDown; pytest fixtures handle initialization
- Multi-line docstrings on test methods describe expected behavior clearly
- Teardown implicit via fixture cleanup (e.g., `tmp_path` auto-removes temp directory)

## Mocking

**Framework:** Python's built-in `unittest.mock` (MagicMock, patch)

**Patterns:**
```python
# Fixture factory for mocking LLM responses
@pytest.fixture
def mock_llm_response(monkeypatch):
    """Factory fixture to mock LLM responses."""
    def _mock(response_text: str):
        def fake_completion(**kwargs):
            class FakeChoice:
                class FakeMessage:
                    content = response_text
                message = FakeMessage()
            class FakeResponse:
                choices = [FakeChoice()]
            return FakeResponse()
        monkeypatch.setattr("litellm.completion", fake_completion)
    return _mock

# Usage in test
def test_llm_client_completion(mock_llm_response):
    mock_llm_response("This person values creativity.")
    client = LLMClient(provider="claude", model="claude-sonnet-4-20250514", api_key="fake")
    result = client.complete("Analyze this data", system="You are an analyzer")
    assert "creativity" in result
```

```python
# Direct MagicMock for complex objects
def make_dummy_embedder():
    """Return a mock SentenceTransformer that yields fixed-size embeddings."""
    embedder = MagicMock()
    embedder.encode.return_value = np.ones(384, dtype=np.float32)
    return embedder

# Patching at module level
@pytest.fixture(autouse=True)
def patch_embedder(self):
    dummy = make_dummy_embedder()
    with patch("percent.chat.engine.SentenceTransformer", return_value=dummy):
        yield dummy
```

**What to Mock:**
- External API calls: LLM (litellm.completion)
- ML models: SentenceTransformer (expensive to load)
- Database operations: FragmentStore in ChatEngine tests
- File I/O: When testing logic independent of actual files

**What NOT to Mock:**
- Pydantic models (use real instances with test data)
- Config loading/saving (use `tmp_percent_dir` for isolation)
- Data structures and enums
- Simple utility functions

## Fixtures and Factories

**Test Data:**

Helper functions for common test objects:
```python
def make_chunk(content: str, source: str = "wechat") -> DataChunk:
    """Create a test DataChunk with sensible defaults."""
    return DataChunk(
        source=source,
        type=ChunkType.CONVERSATION,
        timestamp=datetime(2024, 1, 1),
        content=content,
    )

def make_dummy_embedder():
    """Return a mock SentenceTransformer that yields fixed-size embeddings."""
    embedder = MagicMock()
    embedder.encode.return_value = np.ones(384, dtype=np.float32)
    return embedder
```

Shared test constants:
```python
EXTRACT_RESPONSE = json.dumps([
    {
        "category": "trait",
        "content": "Values intellectual honesty",
        "confidence": 0.85,
        "evidence": "challenges incorrect claims",
    },
])

CORE_MD = """\
## Personality Traits
- Values intellectual honesty

## Values
- Prioritizes deep understanding
"""
```

**Location:**
- Shared fixtures in `tests/conftest.py` (`tmp_percent_dir`, `mock_llm_response`)
- Per-test-module helper functions at top (e.g., `make_chunk()`, `make_dummy_embedder()` in test files)
- Test constants defined module-level in uppercase (e.g., `CORE_MD`, `CHAT_RESPONSE`)

**Key Fixtures (conftest.py):**
```python
@pytest.fixture
def tmp_percent_dir(tmp_path):
    """Create a temporary ~/.percent/ directory for testing."""
    percent_dir = tmp_path / ".percent"
    percent_dir.mkdir()
    (percent_dir / "raw").mkdir()
    return percent_dir
```

## Coverage

**Requirements:** Not enforced in config

**View Coverage:**
```bash
pytest --cov=percent --cov-report=html    # Generate HTML report (if pytest-cov installed)
pytest --cov=percent --cov-report=term    # Terminal summary
```

Currently no coverage thresholds configured in `pyproject.toml`. Type checking via mypy serves as secondary validation layer.

## Test Types

**Unit Tests:**
- Scope: Individual functions, classes, methods
- Approach: Heavy mocking of external dependencies
- Examples: `test_config.py` (config loading), `test_models.py` (Pydantic validation)
- Speed: <100ms per test, run as pre-commit validation

**Integration Tests:**
- Scope: Multi-component interactions (e.g., PersonaEngine.run() orchestrating extract→embed→store→synthesize)
- Approach: Real FragmentStore (sqlite), real embedder mocks (to avoid network), mocked LLM
- Examples: `tests/test_persona/test_engine.py` (full pipeline)
- Speed: 100-500ms per test

**E2E Tests:**
- Framework: None currently used
- If added, would use: pytest + fixtures, no headless browser needed (CLI tool)

## Common Patterns

**Async Testing:**
Not used; codebase is synchronous. Dependency `pytest-asyncio` in dev dependencies but no async/await patterns observed.

**Error Testing:**
```python
def test_finding_confidence_bounds():
    """Pydantic validation ensures confidence is 0.0-1.0."""
    finding = Finding(
        category=FindingCategory.PREFERENCE,
        content="Prefers hard sci-fi",
        confidence=0.85,
        source="wechat",
        evidence="Multiple conversations...",
    )
    assert 0 <= finding.confidence <= 1
```

```python
def test_config_file_excludes_sensitive_defaults(tmp_percent_dir):
    """Verify sensitive fields aren't written to disk."""
    config = PercentConfig(percent_dir=tmp_percent_dir)
    save_config(config)
    content = (tmp_percent_dir / "config.yaml").read_text()
    assert "percent_dir" not in content
```

**Assertion Patterns:**
- Positive assertions preferred: `assert value == expected`
- Negations acceptable: `assert "percent_dir" not in content`
- Collection checks: `assert len(engine.history) == 4`
- Membership: `assert "creativity" in result`

**Test Data Isolation:**
- Each test gets fresh `tmp_percent_dir` fixture
- Mocks reset between tests automatically by unittest.mock
- No shared state between test methods

## Test Organization Summary

**Total test coverage by module:**
- Parsers: ~1,500 lines (largest area) — `tests/test_parsers/` with telegram, wechat, youtube, whatsapp, etc.
- Persona pipeline: ~700 lines — extraction, synthesis, validation, deep analysis
- Chat engine: ~130 lines — history, prompt building, reset
- Models: ~30 lines — Pydantic validation basics
- Config: ~25 lines — persistence and loading

**Test Execution Breakdown:**
- Simple file-based tests run first (config, models)
- Parser tests validate format detection and chunk extraction
- Integration tests validate PersonaEngine orchestration
- All tests isolated via fixtures, no fixture order dependencies

---

*Testing analysis: 2026-04-11*
