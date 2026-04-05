<div align="center">

<!-- Logo placeholder: replace with assets/logo.svg when available -->
<img src="assets/logo.svg" alt="Engram logo" width="80" height="80" />

# Engram

**The Personality Engine for AI**

[![CI](https://github.com/your-org/engram/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/engram/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

[Documentation](#how-it-works) · [Quick Start](#quick-start) · [PersonaBench](#personabench) · [Contributing](#contributing) · [中文](README_CN.md)

</div>

---

## Why Engram?

Every AI assistant starts blank. It doesn't know how you think, what you care about, or how you communicate. You re-introduce yourself every session.

**Engram fixes that.**

Feed it your WeChat history, YouTube watch list, Bilibili comments — anything that reflects how you actually think. Engram extracts your personality into a structured model (`core.md`) that any LLM can use to become *your* AI, not a generic one.

- **Privacy-first.** Everything runs locally. Your data never leaves your machine.
- **Source-agnostic.** WeChat, YouTube, Bilibili — more sources coming.
- **Model-agnostic.** Works with Claude, GPT-4, DeepSeek, Ollama, any LiteLLM-compatible model.
- **Measurable.** PersonaBench gives you a concrete score — not vibes.

---

## PersonaBench

PersonaBench is Engram's built-in benchmark for measuring how accurately your personality model reflects you.

```
PersonaBench v0.1
Score: 84.3%  (10 tests)

  [1] 0.91  Profile predicted directness; actual response matches
  [2] 0.88  Intellectual honesty pattern observed in challenge
  [3] 0.79  Communication style: concise, no filler
  [4] 0.85  Systems thinking visible in response structure
  [5] 0.72  Preference for hard evidence confirmed
  [6] 0.90  Low tolerance for hedging; matches profile
  [7] 0.83  Deep-dive tendency over surface overview
  [8] 0.81  Precise vocabulary consistent with profile
  [9] 0.86  Confrontational on factual errors, as modeled
  [10] 0.88  Hard sci-fi reference consistent with preferences
```

Run it yourself:

```bash
engram persona validate --num-tests 10
```

---

## Quick Start

```bash
pip install engram
engram init
engram import run wechat ~/exports/wechat_chat.csv
engram chat
```

That's it. After `import run`, Engram has built your `core.md` and chat speaks as you.

---

## How It Works

```
Your data                Engram pipeline              Output
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
| WeChat | PyWxDump CSV export | `engram import run wechat <path>` |
| YouTube | Google Takeout JSON | `engram import run youtube <path>` |
| Bilibili | Watch history JSON | `engram import run bilibili <path>` |

More sources are welcome — see [Contributing](#contributing).

---

## Commands Reference

```
engram init                         Configure API key and provider
engram import run <source> <path>   Import and analyze data
engram import guide <source>        Show export instructions for a source
engram import status                Show fragment store statistics

engram persona view                 Print current core.md
engram persona stats                Fragment statistics
engram persona rebuild              Rebuild core.md from all stored fragments
engram persona validate             Run PersonaBench

engram export soul                  Generate SOUL.md system prompt
engram export core                  Copy core.md to a custom path

engram chat                         Start interactive chat with your persona
engram config llm                   Change LLM provider / model / key
engram config parsers               List available parsers
```

---

## Architecture

```
engram/
├── cli.py                  Typer CLI entry point
├── config.py               EngramConfig (Pydantic), load/save YAML
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

Engram is open-source and welcomes contributions.

The most impactful contributions right now:

- **New parsers** — Spotify, Twitter/X, Notion, iMessage
- **Prompt improvements** — better extraction and synthesis prompts in `prompts/`
- **PersonaBench datasets** — reference personas for calibration

To add a parser, subclass `DataParser` in `engram/parsers/`, register it in `cli.py`, and add tests under `tests/test_parsers/`.

```bash
git clone https://github.com/your-org/engram
cd engram
uv sync
uv run pytest tests/ -v
```

---

## License

MIT — do whatever you want with it. Your personality model is yours.
