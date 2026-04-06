<div align="center">

<img src="assets/logo.svg" alt="Percent logo" width="120" height="120" />

# Percent

**How much of you can AI understand?**

[![CI](https://github.com/looanli08-hl/percent/actions/workflows/ci.yml/badge.svg)](https://github.com/looanli08-hl/percent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

[Documentation](#how-it-works) · [Quick Start](#quick-start) · [PersonaBench](#personabench) · [Contributing](#contributing) · [中文](README_CN.md)

</div>

---

## Why Percent?

Every AI assistant starts blank. It doesn't know how you think, what you care about, or how you communicate. You re-introduce yourself every session.

**Percent fixes that.**

Feed it your WeChat history, YouTube watch list, Bilibili comments — anything that reflects how you actually think. Percent extracts your personality into a structured model (`core.md`) that any LLM can use to become *your* AI, not a generic one.

- **Privacy-first.** Raw data stays on your machine. When using cloud LLMs (OpenAI, Claude, DeepSeek), text fragments are sent for analysis — use Ollama for fully local processing.
- **Source-agnostic.** WeChat, YouTube, Bilibili — more sources coming.
- **Model-agnostic.** Works with Claude, GPT-4, DeepSeek, Ollama, any LiteLLM-compatible model.
- **Measurable.** PersonaBench gives you a concrete score — not vibes.

---

## PersonaBench

PersonaBench is Percent's built-in benchmark for measuring how accurately your personality model reflects you.

```
PersonaBench v0.1
Score: 72.5%  (10 tests)

  [1] 0.95  Gaming preferences and invite behavior matched exactly
  [2] 0.90  Tech research habits and pragmatic style highly consistent
  [3] 0.90  Tutoring details and frugal mindset aligned precisely
  [4] 0.90  Practical values and money-saving behavior matched profile
  [5] 0.80  Football enthusiasm and team loyalty predicted correctly
  [6] 0.80  Direct expression style and tech curiosity confirmed
  [7] 0.70  Emotional expression pattern partially matched
  [8] 0.70  Venting style consistent but actual response more narrative
  [9] 0.30  Response format deviated from predicted interaction style
  [10] 0.30  Predicted casual tone vs actual formal description
```

Run it yourself:

```bash
percent persona validate --num-tests 10
```

---

## Quick Start

```bash
git clone https://github.com/looanli08-hl/engram && cd engram
uv sync
uv run percent init
uv run percent import run wechat ~/exports/wechat_chat.csv
uv run percent chat
```

That's it. After `import run`, Percent has built your `core.md` and chat speaks as you.

---

## How It Works

```
Your data                Percent pipeline             Output
─────────────────────    ────────────────────────     ──────────────────
WeChat CSV          ──►  Parser                  ──►  DataChunks
YouTube Takeout     ──►  Extractor (LLM)         ──►  Findings
Bilibili History    ──►  Fragment Store (SQLite)  ──►  Embeddings
                         Synthesizer (LLM)        ──►  core.md
                         PersonaEngine            ──►  core.md (updated)
                                                  ──►  Chat / SOUL.md
```

1. **Parse** — source-specific parsers normalize raw exports into `DataChunk` objects
2. **Extract** — an LLM reads each chunk and extracts personality findings (traits, opinions, preferences)
3. **Store** — findings are embedded and stored in a local SQLite + vector index
4. **Synthesize** — all findings are condensed into a structured `core.md` personality profile
5. **Use** — chat with your persona, export `SOUL.md` for use in any system prompt

---

## Supported Sources

| Source | Format | Command |
|--------|--------|---------|
| WeChat | PyWxDump CSV export | `percent import run wechat <path>` |
| YouTube | Google Takeout JSON | `percent import run youtube <path>` |
| Bilibili | Watch history JSON | `percent import run bilibili <path>` |

More sources are welcome — see [Contributing](#contributing).

---

## Commands Reference

```
percent init                         Configure API key and provider
percent import run <source> <path>   Import and analyze data
percent import guide <source>        Show export instructions for a source
percent import status                Show fragment store statistics

percent persona view                 Print current core.md
percent persona stats                Fragment statistics
percent persona rebuild              Rebuild core.md from all stored fragments
percent persona validate             Run PersonaBench

percent export soul                  Generate SOUL.md system prompt
percent export core                  Copy core.md to a custom path

percent chat                         Start interactive chat with your persona
percent config llm                   Change LLM provider / model / key
percent config parsers               List available parsers
```

---

## Architecture

```
percent/
├── cli.py                  Typer CLI entry point
├── config.py               PercentConfig (Pydantic), load/save YAML
├── models.py               DataChunk, Finding, Fragment (Pydantic)
├── llm/
│   └── client.py           LiteLLM wrapper (provider-agnostic)
├── parsers/
│   ├── base.py             DataParser ABC
│   ├── bilibili.py         Bilibili watch history
│   ├── youtube.py          YouTube Takeout
│   └── wechat.py           WeChat PyWxDump CSV
├── persona/
│   ├── engine.py           PersonaEngine (orchestrates extract→synthesize)
│   ├── extractor.py        LLM-based finding extractor
│   ├── synthesizer.py      LLM-based core.md synthesizer
│   ├── fragments.py        FragmentStore (SQLite + cosine search)
│   ├── validator.py        PersonaValidator (alignment scoring)
│   └── bench.py            PersonaBench v0.1
├── export/
│   └── soul_md.py          SOUL.md exporter
└── chat/
    └── engine.py           ChatEngine (RAG over fragments)
```

---

## Contributing

Percent is open-source and welcomes contributions.

The most impactful contributions right now:

- **New parsers** — Spotify, Twitter/X, Notion, iMessage
- **Prompt improvements** — better extraction and synthesis prompts in `prompts/`
- **PersonaBench datasets** — reference personas for calibration

To add a parser, subclass `DataParser` in `percent/parsers/`, register it in `cli.py`, and add tests under `tests/test_parsers/`.

```bash
git clone https://github.com/looanli08-hl/engram
cd engram
uv sync
uv run pytest tests/ -v
```

---

## License

MIT — do whatever you want with it. Your personality model is yours.
