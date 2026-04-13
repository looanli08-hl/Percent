# Codebase Concerns

**Analysis Date:** 2026-04-11

## Tech Debt

**Single-threaded SQLite with `check_same_thread=False`:**
- Issue: `FragmentStore` in `percent/persona/fragments.py:16` opens SQLite with `check_same_thread=False`, disabling thread-safety checks. This is a flag for unsafe concurrent access in multi-threaded contexts.
- Files: `percent/persona/fragments.py`
- Impact: Web API requests in `percent/web.py` may race on fragment reads/writes. Data corruption risk if parallel imports occur. FastAPI is async/multi-threaded by default.
- Fix approach: Implement thread-safe access patterns — either queue all fragment operations through a single worker thread, use SQLite WAL mode + explicit locking, or migrate to a thread-safe database (PostgreSQL for multi-user).

**Bare exception handlers with silent failure:**
- Issue: `percent/persona/engine.py:186` catches all exceptions during fingerprint generation and silently passes. Errors are hidden from the user.
- Files: `percent/persona/engine.py:186` (fingerprint), `percent/web.py:257` (zip extraction)
- Impact: Bugs in fingerprint generation are not reported. ZIP extraction failures silently keep the zip file or ignore extraction errors. Users don't know if their data was processed correctly.
- Fix approach: Log exceptions with context; return status to user. `logging.warning()` + re-raise or return failure status in API responses.

**Hardcoded provider/model defaults:**
- Issue: `percent/config.py:12` defaults to `claude-sonnet-4-20250514`, but price data in `percent/llm/client.py:10-19` is manually updated. Model strings become stale; cost estimates are outdated.
- Files: `percent/config.py`, `percent/llm/client.py`
- Impact: Cost estimates are inaccurate once Anthropic updates model versions. Wrong default model silently fails if user's API key doesn't have access to that model.
- Fix approach: Fetch available models from provider at init time, or allow user to override in config. Keep pricing map in a YAML file, not hardcoded Python dict.

**Manual embedding recomputation on every search:**
- Issue: `percent/persona/fragments.py:101-120` loads all fragments from SQLite, then computes cosine similarity in Python for every search. No vector database, no indexing.
- Files: `percent/persona/fragments.py:101-120`
- Impact: Scales as O(n) per search. With 10k fragments, every chat query becomes slow. No denormalization or caching.
- Fix approach: Migrate to a vector database (Qdrant, Milvus, pgvector) for ANN search, or implement in-memory FAISS index that's persisted.

---

## Known Bugs

**Emoji/Unicode handling in WhatsApp parser:**
- Symptoms: WhatsApp CSV exports with emoji or special Unicode may be parsed incorrectly. Text encoding mismatches.
- Files: `percent/parsers/whatsapp.py` (370 LOC)
- Trigger: Import WhatsApp CSV with emojis or non-ASCII text from non-English locales.
- Workaround: Manually clean the CSV to ASCII before import, or re-export from WhatsApp with UTF-8 encoding enforced.

**Telegram parser fragility with nested message types:**
- Symptoms: Telegram exported JSON with forwarded messages, replies, or media captions may be dropped or incorrectly categorized.
- Files: `percent/parsers/telegram.py` (315 LOC), `tests/test_parsers/test_telegram.py` (450 LOC)
- Trigger: Import Telegram JSON with message replies (reply_to_message) or forwarded content.
- Workaround: Extract plain text manually before import.

**WeChat-DB parser only supports message tables, not Moments:**
- Symptoms: User imports a decrypted WeChat database expecting posts and moments to be extracted, but only messages are parsed.
- Files: `percent/parsers/wechat_db.py:60-62` (Moments parsing exists but may be incomplete), `percent/parsers/wechat_db.py:64-71` (voice message stubs)
- Trigger: Moments/posts in decrypted WeChat DB are not extracted with full context.
- Workaround: Only use CSV export (PyWxDump) for complete coverage; DB mode is beta for messages only.

---

## Security Considerations

**API keys stored in plaintext config file:**
- Risk: `~/.percent/config.yaml` contains `llm_api_key` in plaintext. If user's home directory is compromised or synced to cloud (iCloud, Google Drive), API key is exposed.
- Files: `percent/config.py:39-43` (save_config), `percent/cli.py:78-82` (init prompts for key)
- Current mitigation: Local file only; user must protect home directory.
- Recommendations: Store API key in system keyring (macOS Keychain, Linux Secret Service, Windows Credential Manager) instead of YAML. Use `keyring` library.

**Bilibili/YouTube API cookies stored in raw/ directory:**
- Risk: `~/.percent/raw/bilibili/bilibili_cookie.txt` or `~/.percent/raw/youtube/` may contain session cookies. If directory is readable by other users or backed up unencrypted, cookies are stolen.
- Files: `percent/parsers/bilibili_api.py:14`, `percent/parsers/youtube_api.py`
- Current mitigation: Relies on file permissions.
- Recommendations: (1) Encrypt cookies on disk, (2) Warn users during import about cookie security, (3) Delete cookies after import succeeds.

**No CSRF/CORS protection on Web API:**
- Risk: FastAPI server in `percent/web.py` has no CSRF tokens or origin validation. A malicious webpage could call `/api/chat` or `/api/import/analyze` from the user's browser.
- Files: `percent/web.py` (entire file, no @app.middleware for CORS or CSRF)
- Current mitigation: Server runs on localhost only (localhost:8000 by default).
- Recommendations: Add CORS middleware restricting `Access-Control-Allow-Origin` to localhost only, or require CSRF tokens for POST/DELETE operations.

---

## Performance Bottlenecks

**CLI batch extraction runs extraction on chunks sequentially:**
- Problem: `percent/persona/extractor.py` processes chunks in batches, but each batch sends one API call to the LLM. With large imports (1000+ chunks), this creates many sequential API calls.
- Files: `percent/persona/extractor.py` (batching logic), `percent/cli.py:100-150` (import run command)
- Cause: LLM extraction is not parallelized. Each batch waits for the previous LLM response.
- Improvement path: Implement concurrent extraction — send up to `N` extraction calls in parallel (respecting LLM rate limits), collect responses, and merge findings.

**Web UI profile reload rebuilds entire spectrum on every API call:**
- Problem: `/api/spectrum` recomputes all 8 dimensions and eligibility on every request. No caching.
- Files: `percent/web.py:94-100` (spectrum endpoint), `percent/persona/spectrum.py` (full recomputation)
- Cause: Spectrum is stateless and recomputed from fragments each time.
- Improvement path: Cache spectrum in SQLite or JSON file, invalidate on new import. Or compute spectrum once during import, persist to `spectrum.json`.

**Vector search loads all fragments into memory for cosine similarity:**
- Problem: Every chat query triggers O(n) embedding computations. With 10k fragments × 384 dimensions = 3.8M floats loaded and computed per query.
- Files: `percent/persona/fragments.py:101-120`, `percent/chat/engine.py:75-82`
- Cause: No vector index. Full scan required.
- Improvement path: Pre-compute and persist FAISS or Annoy index. Update on import. Load once at startup, not per query.

---

## Fragile Areas

**LLM response JSON parsing with naive regex:**
- Files: `percent/persona/extractor.py:36-71`, `percent/persona/cross_validate.py:140-181`
- Why fragile: Uses `re.search(r"\[.*\]", text, re.DOTALL)` to extract JSON from LLM responses. If the LLM outputs multiple arrays or includes unescaped `[]` in text, regex fails or captures wrong block.
- Safe modification: (1) Wrap regex in try-except, (2) Use a proper JSON parser with error recovery, (3) Require LLM to output clearly delimited JSON (e.g., ` ```json ... ``` `), or (4) Add pre-processing to clean LLM response before parsing.
- Test coverage: `tests/test_persona/test_extractor.py:145` has basic tests; missing tests for malformed JSON, multiple arrays, Unicode in content.

**Fingerprint generation is best-effort and invisible:**
- Files: `percent/persona/engine.py:172-186`
- Why fragile: Exceptions in `analyze_fingerprint()` are caught and silently ignored. If fingerprint fails, the rest of the pipeline continues. User never knows.
- Safe modification: Log failures with `logging.warning()`. Optionally return fingerprint status in analysis result. Make fingerprint generation optional (off by default for imports, on-demand from CLI).
- Test coverage: No tests for fingerprint generation in `tests/test_persona/test_engine.py`.

**Config loading defaults to empty API key silently:**
- Files: `percent/config.py:46-53`
- Why fragile: `load_config()` returns a PercentConfig with empty `llm_api_key=""` if config file is missing. Later, `LLMClient.complete()` passes `api_key=None` to litellm, which may fail or use environment variables unexpectedly.
- Safe modification: Validate config at startup. If API key is missing and provider is "openai"/"claude", fail fast with clear error message. Don't silently fall back to env vars.
- Test coverage: `tests/test_config.py:97` tests save/load but not missing key case.

**Circular dependency risk: Web imports CLI helpers:**
- Files: `percent/web.py:220-227` (parser registry mirrors `percent/cli.py:35-43`), `percent/web.py:281-289` (mirrors CLI logic)
- Why fragile: Same parser registry and import logic duplicated across `cli.py` and `web.py`. If a parser is added to CLI but not Web, or vice versa, import works in one but not the other.
- Safe modification: Extract parser registry and import logic to a shared module `percent/import_registry.py`, import it in both `cli.py` and `web.py`.
- Test coverage: `tests/test_web_evidence.py` tests Web API but doesn't verify parser parity with CLI.

---

## Scaling Limits

**SQLite fragments DB with no pagination or indexing:**
- Current capacity: ~10k fragments before vector search becomes slow (O(n) per query).
- Limit: Crashes or timeouts at ~100k fragments (can't load all into memory for cosine similarity).
- Scaling path: Migrate to vector database (Qdrant, Milvus, pgvector). Implement pagination in Web UI.

**LLM extraction batch size hardcoded to 20:**
- Current capacity: 20 chunks per batch → 1 API call per batch.
- Limit: With 5000-chunk imports, 250 sequential API calls. Takes hours.
- Scaling path: Implement concurrent extraction with configurable max_concurrent (e.g., 5-10), respecting provider rate limits.

**No rate limiting or quota management on Web API:**
- Current capacity: Unlimited requests per user to `/api/chat`, `/api/import/analyze`, `/api/spectrum`.
- Limit: DOS attack or accidental loop can exhaust LLM quota in seconds.
- Scaling path: Add per-endpoint rate limiting (FastAPI Limiter), quota tracking, and user warnings.

---

## Dependencies at Risk

**litellm pinned to >=1.40 but no upper bound:**
- Risk: litellm's major version updates may change API signature or behavior. Backward-incompatible changes not caught until runtime.
- Impact: `percent/llm/client.py` calls `litellm.completion()` directly. If litellm 2.x breaks this API, all LLM calls fail.
- Migration plan: Pin litellm to `>=1.40,<2.0` to prevent major version surprises. Add integration tests against a live mock LLM provider.

**sentence-transformers >=3.0 has heavy dependencies:**
- Risk: sentence-transformers brings in PyTorch, which is large. No fallback if it fails to install.
- Impact: Installation fails on systems without PyTorch support (ARM, lightweight containers). Embedding search is a core feature, so no graceful degradation.
- Migration plan: Make embedding model configurable at runtime. Allow users to opt into local embedding via environment variable. Or provide a lightweight fallback (e.g., TF-Lite version).

**FastAPI/Uvicorn pinned broadly (>=0.135.3 / >=0.43.0):**
- Risk: Web UI uses broad version ranges. Future breaking changes may not be caught.
- Impact: Minor version updates could introduce incompatibilities.
- Migration plan: Tighten constraints: `fastapi>=0.135.3,<1.0`, `uvicorn>=0.43.0,<1.0`.

---

## Missing Critical Features

**No user-facing evidence drill-down:**
- Problem: Users can see `core.md` and "confidence" scores, but can't trace back: "Why did Percent think I like gaming?" No evidence view.
- Blocks: Can't build trust without transparency. Users can't debug bad conclusions.
- Roadmap reference: Wave 3 (Provenance and Trust Layer) plans to add this.

**No import history or provenance tracking:**
- Problem: If a user imports the same source twice, it's not clear what changed. No audit trail.
- Blocks: Support can't help users debug "why did my profile change?" No reproducibility.
- Roadmap reference: Wave 3 (Import Manifest) plans `imports.json`.

**No way to reset or partially delete data:**
- Problem: Users can't easily remove a bad import or reset the profile without deleting `~/.percent/`.
- Blocks: Users stuck with bad data; can't iterate safely.
- Roadmap reference: Wave 4 (Operational UX) plans `percent reset profile` / `percent purge`.

**Evaluation (PersonaBench) does not control for data leakage:**
- Problem: PersonaBench v0.2 may use the same data for training and evaluation. Scores are inflated.
- Blocks: Can't make quality claims based on PersonaBench scores; claims will be scrutinized.
- Roadmap reference: Wave 5 (Evaluation Upgrade) plans train/eval split.

---

## Test Coverage Gaps

**LLM-dependent tests without mocking:**
- What's not tested: Extraction, synthesis, and validation all call real LLM APIs. Tests cost money and are flaky.
- Files: `tests/test_persona/test_extractor.py`, `tests/test_persona/test_synthesizer.py`, `tests/test_persona/test_engine.py`, `tests/test_chat.py`
- Risk: Tests may pass locally but fail in CI due to API quota, rate limiting, or model changes.
- Fix approach: Mock all LLM calls in tests. Use `responses` library for HTTP-based APIs, or pytest fixtures that intercept `litellm.completion()`.

**Web API endpoints not fully tested:**
- What's not tested: `/api/import/upload`, `/api/import/analyze`, `/api/spectrum` are not covered by test suite.
- Files: `percent/web.py` endpoints missing from `tests/test_web_*.py`
- Risk: Breaking changes to Web API are not caught by CI. Users importing via Web may hit errors not seen in CLI tests.
- Fix approach: Add integration tests for Web import flow; test file upload, parsing, and analysis end-to-end.

**Parser robustness for malformed inputs:**
- What's not tested: Most parsers don't test edge cases — empty files, corrupted ZIP, mixed encoding, null values in required fields.
- Files: `percent/parsers/*.py` (bilibili.py, youtube.py, wechat.py, whatsapp.py, etc.)
- Risk: User provides a malformed export, parser crashes or drops data silently. No clear error message.
- Fix approach: Add tests for `validate()` and `parse()` with bad inputs. Ensure exceptions are raised with user-friendly messages.

**Spectrum eligibility logic is rule-based, not validated:**
- What's not tested: `percent/persona/spectrum.py:85-112` (eligibility check) is never tested against real thresholds. No unit tests for boundary conditions (29 vs 30 fragments, 1 vs 2 sources).
- Files: `percent/persona/spectrum.py:85-112`
- Risk: Eligibility rules silently change if code is refactored. No regression test.
- Fix approach: Add parameterized unit tests for eligibility edge cases.

---

## Design Inconsistencies

**Parser registry duplicated between CLI and Web:**
- Issue: `percent/cli.py:35-43` and `percent/web.py:220-227` maintain separate copies of parser registry. If one is updated and the other isn't, CLI and Web support different sources.
- Files: `percent/cli.py`, `percent/web.py`
- Impact: Hard to maintain; easy to introduce bugs. Web may not support a parser that CLI supports.
- Fix approach: Extract registry to `percent/import_registry.py`, import in both places.

**Fingerprint and Big Five generated but not surfaced in Web UI:**
- Issue: `percent/persona/engine.py:172-186` generates fingerprint; `percent/persona/big_five.py` exists; endpoints exist in `percent/web.py`. But Web UI doesn't display them.
- Files: `percent/web.py` (endpoints exist but UI doesn't call them)
- Impact: Features exist but are hidden. Users can't see personality dimensions or behavioral patterns.
- Fix approach: Update Web static UI to fetch and display `/api/spectrum`, `/api/insights`, `/api/fingerprint`.

**Confidence scores adjusted during cross-validation, but no explanations:**
- Issue: `percent/persona/cross_validate.py:28-106` adjusts fragment confidence based on corroboration. But the user never knows why a score changed.
- Files: `percent/persona/cross_validate.py`, `percent/persona/engine.py:144-150`
- Impact: Score transparency is lost. Users see "confidence: 0.75" but don't know if it was boosted from 0.60 due to cross-source corroboration.
- Fix approach: Store confidence history or add a `confidence_reasoning` field to fragments.

---

## Environment and Configuration Risks

**No validation that config is initialized before use:**
- Issue: If user runs `percent chat` without running `percent init` first, config will be created with empty API key. ChatEngine will fail later with a cryptic litellm error.
- Files: `percent/cli.py`, `percent/config.py`
- Impact: Poor user experience; error messages are from litellm, not from Percent.
- Fix approach: Add a startup check in CLI and Web that validates required config before proceeding. Prompt for missing config.

**Embedding model is hardcoded in multiple places:**
- Issue: `_DEFAULT_MODEL = "all-MiniLM-L6-v2"` is defined in `percent/persona/engine.py:19`, `percent/chat/engine.py:11`. If model changes, must update both.
- Files: `percent/persona/engine.py`, `percent/chat/engine.py`, `percent/web.py`
- Impact: Hard to experiment with different embeddings. Configuration scattered.
- Fix approach: Store embedding model in PercentConfig, pass as argument consistently.

---

*Concerns audit: 2026-04-11*
