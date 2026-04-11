# Percent V2: Persona Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a shareable persona card — a 1080x1440 image generated from real user data, with an 8-dimension stellar chart, AI-generated label, and data-driven insights.

**Architecture:** Three phases executed sequentially. Phase 1 fixes regressions that would break the user journey. Phase 2 builds the spectrum engine (dimension scoring + metrics + eligibility gate + LLM labeling). Phase 3 builds the card UI (stellar chart SVG + layout + image export). XHS parser completion runs in parallel and does not block the card.

**Tech Stack:** Python 3.12+, FastAPI, SQLite (FragmentStore), LiteLLM, SVG (stellar chart), modern-screenshot (image export), Instrument Serif + DM Sans (fonts)

**Project root:** `/Users/looanli/Projects/percent`

---

## File Structure

### New files
- `percent/persona/spectrum.py` — 8-dimension scoring engine + numerical metrics + eligibility gate + LLM label generation
- `percent/prompts/spectrum_label.md` — LLM prompt for label + description + insight rewriting
- `tests/test_persona/test_spectrum.py` — Tests for spectrum scoring, metrics, eligibility
- `tests/test_web_spectrum.py` — Tests for `/api/spectrum` endpoint

### Modified files
- `percent/parsers/wechat.py` — Fix regression: restore `type` validation for original format
- `percent/web.py` — Add evidence to fragment API response; add `/api/spectrum` endpoint
- `percent/static/index.html` — Card view UI (stellar chart SVG, layout, export button, detail card)
- `percent/persona/engine.py` — Trigger spectrum computation after analysis
- `percent/cli.py` — Add `xiaohongshu` to CLI parser registry
- `README.md` — Fix `cd engram` → `cd Percent`, PersonaBench v0.1 → v0.2
- `README_CN.md` — Same fixes

---

## Phase 1: P0 Fixes

### Task 1: Fix WeChat parser regression

**Files:**
- Modify: `percent/parsers/wechat.py:28-35`
- Modify: `tests/test_parsers/test_wechat.py:51-57`

The `_detect_csv_format` function currently only checks for `talker`, `content`, `time` columns — it no longer requires `type`. This causes the test at line 51 to fail because a CSV with only `StrTalker/StrContent/CreateTime` (no `Type`) is now accepted. The fix: for the original raw DB format, require all 4 columns; for WeFlow/MemoTrace formats, `type` column is optional (these tools may export without it).

- [ ] **Step 1: Run the failing tests to confirm the regression**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_parsers/test_wechat.py -v`

Expected: `test_validate_csv_missing_required_column` FAILS, `test_import_guide_mentions_pywxdump` FAILS

- [ ] **Step 2: Fix `_detect_csv_format` to require `type` for original format**

In `percent/parsers/wechat.py`, replace the `_detect_csv_format` function:

```python
def _detect_csv_format(fieldnames: list[str]) -> dict[str, str] | None:
    """Detect which CSV format matches the given column headers."""
    field_set = set(fieldnames)
    for fmt in _CSV_FORMATS:
        # All four columns (including type) must be present
        required = {fmt["talker"], fmt["content"], fmt["time"], fmt["type"]}
        if required.issubset(field_set):
            return fmt
    return None
```

- [ ] **Step 3: Fix import guide to mention WeFlow (and restore PyWxDump mention for test)**

In `percent/parsers/wechat.py`, update the `get_import_guide` return value — ensure it contains "PyWxDump" (the test checks for it) while also mentioning WeFlow:

```python
def get_import_guide(self) -> str:
    return (
        "WeChat Chat Log Export Guide\n"
        "=============================\n"
        "\n"
        "Option A — WeFlow (macOS, recommended):\n"
        "  1. Download WeFlow from https://github.com/hicccc77/WeFlow/releases\n"
        "  2. Install the .dmg and open while WeChat is running.\n"
        "  3. Export chats as CSV.\n"
        "  4. Upload the exported file(s) here.\n"
        "\n"
        "Option B — MemoTrace (Windows, recommended):\n"
        "  1. Download MemoTrace from https://github.com/shixiaogaoya/MemoTrace/releases\n"
        "  2. Run the tool while WeChat is logged in on your PC.\n"
        "  3. Export chats as CSV.\n"
        "  4. Upload the exported file(s) here.\n"
        "\n"
        "Option C — PyWxDump (advanced):\n"
        "  1. See https://github.com/xaoyaoo/PyWxDump for instructions.\n"
        "  2. Export chats as CSV.\n"
        "\n"
        "Note: Only text messages are imported.\n"
        "      Messages within a 30-minute gap are grouped into one conversation chunk.\n"
    )
```

- [ ] **Step 4: Run tests to verify both pass**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_parsers/test_wechat.py -v`

Expected: ALL PASS (including `test_validate_csv_missing_required_column` and `test_import_guide_mentions_pywxdump`)

- [ ] **Step 5: Run full test suite to verify no other regressions**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest -q`

Expected: All tests pass (163 passed, 0 failed)

- [ ] **Step 6: Commit**

```bash
cd /Users/looanli/Projects/percent
git add percent/parsers/wechat.py tests/test_parsers/test_wechat.py
git commit -m "fix: restore type validation in WeChat parser, fix import guide"
```

---

### Task 2: Fix evidence not returned by API

**Files:**
- Modify: `percent/web.py:102-115`

- [ ] **Step 1: Write a test for evidence in fragment API response**

Create `tests/test_web_evidence.py`:

```python
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from percent.models import FindingCategory, Fragment
from percent.web import app


@pytest.fixture()
def client():
    return TestClient(app)


def _make_fragment(source: str = "wechat", evidence: str = "said X in chat") -> Fragment:
    return Fragment(
        id=1,
        category=FindingCategory.TRAIT,
        content="test trait",
        confidence=0.85,
        source=source,
        evidence=evidence,
    )


def test_fragments_endpoint_includes_evidence(client):
    frag = _make_fragment(evidence="user said 'I love coding' at 2am")

    with patch("percent.web._require_config") as mock_cfg:
        mock_cfg.return_value.fragments_db_path.exists.return_value = True
        with patch("percent.web.FragmentStore") as MockStore:
            instance = MockStore.return_value
            instance.get_all.return_value = [frag]
            resp = client.get("/api/fragments/wechat")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["fragments"]) == 1
    assert data["fragments"][0]["evidence"] == "user said 'I love coding' at 2am"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_web_evidence.py -v`

Expected: FAIL — `evidence` key not in response dict

- [ ] **Step 3: Add evidence field to fragment API response**

In `percent/web.py`, modify the `get_fragments_by_source` function. Replace the list comprehension (lines 102-115):

```python
    filtered = [
        {
            "id": f.id,
            "category": f.category.value,
            "content": f.content,
            "confidence": f.confidence,
            "evidence": f.evidence,
            "created_at": f.created_at.isoformat() if f.created_at else "",
        }
        for f in all_frags
        if f.source == source
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_web_evidence.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/looanli/Projects/percent
git add percent/web.py tests/test_web_evidence.py
git commit -m "fix: return evidence field in /api/fragments/{source} response"
```

---

### Task 3: Fix documentation sync

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`

- [ ] **Step 1: Fix README.md**

Replace `cd engram` with `cd Percent` on line 65:
```
git clone https://github.com/looanli08-hl/Percent && cd Percent
```

Replace `PersonaBench v0.1` with `PersonaBench v0.2` on line 39:
```
PersonaBench v0.2
```

- [ ] **Step 2: Fix README_CN.md with the same changes**

Same two substitutions in the Chinese README.

- [ ] **Step 3: Commit**

```bash
cd /Users/looanli/Projects/percent
git add README.md README_CN.md
git commit -m "fix: sync README with current repo name and PersonaBench version"
```

---

## Phase 2: Spectrum Engine

### Task 4: Spectrum dimension scoring

**Files:**
- Create: `percent/persona/spectrum.py`
- Create: `tests/test_persona/test_spectrum.py`

This is the core computation engine. It takes all fragments from the DB and computes 8 dimension scores (0-100) plus numerical metrics for card insights.

- [ ] **Step 1: Write tests for dimension scoring**

Create `tests/test_persona/test_spectrum.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from percent.models import FindingCategory, Fragment
from percent.persona.spectrum import SpectrumEngine, SpectrumResult


def _frag(
    content: str,
    source: str = "wechat",
    category: FindingCategory = FindingCategory.HABIT,
    confidence: float = 0.8,
    hours_offset: int = 0,
    evidence: str = "",
) -> Fragment:
    """Helper to create a Fragment with a specific timestamp offset from midnight."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ts = base + timedelta(hours=hours_offset)
    return Fragment(
        id=None,
        category=category,
        content=content,
        confidence=confidence,
        source=source,
        evidence=evidence,
        created_at=ts,
    )


class TestSpectrumScoring:
    def test_returns_spectrum_result(self):
        frags = [_frag(f"test content {i}", hours_offset=i) for i in range(10)]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert isinstance(result, SpectrumResult)

    def test_scores_are_0_to_100(self):
        frags = [_frag(f"content {i}", hours_offset=i) for i in range(20)]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        for dim, score in result.dimensions.items():
            assert 0 <= score <= 100, f"{dim} score {score} out of range"

    def test_night_owl_high_for_late_night_fragments(self):
        # All fragments created between 1am-4am
        frags = [_frag(f"late night {i}", hours_offset=1 + i) for i in range(4)]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert result.dimensions["夜行性"] >= 60

    def test_night_owl_low_for_daytime_fragments(self):
        # All fragments created between 9am-5pm
        frags = [_frag(f"daytime {i}", hours_offset=9 + i) for i in range(8)]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert result.dimensions["夜行性"] <= 40

    def test_cross_platform_contrast_needs_multiple_sources(self):
        frags = [_frag(f"single source {i}", source="wechat") for i in range(10)]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        # Single source = dimension not available
        assert "跨平台反差" not in result.dimensions

    def test_cross_platform_contrast_present_with_two_sources(self):
        frags = [
            _frag("wechat content", source="wechat"),
            _frag("bilibili content", source="bilibili"),
        ]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert "跨平台反差" in result.dimensions

    def test_available_dimensions_vary_by_source(self):
        # Only bilibili data → no reply inertia or expression sharpness
        frags = [_frag(f"video {i}", source="bilibili", hours_offset=i) for i in range(10)]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert "回复惯性" not in result.dimensions
        assert "夜行性" in result.dimensions  # timestamp-based, always available


class TestSpectrumMetrics:
    def test_metrics_include_data_span(self):
        frags = [
            _frag("early", hours_offset=0),
            _frag("late", hours_offset=24 * 30),  # 30 days later
        ]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert result.metrics["data_span_days"] >= 29

    def test_metrics_include_fragment_count(self):
        frags = [_frag(f"f{i}") for i in range(15)]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert result.metrics["fragment_count"] == 15

    def test_metrics_include_source_count(self):
        frags = [
            _frag("a", source="wechat"),
            _frag("b", source="bilibili"),
            _frag("c", source="xiaohongshu"),
        ]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert result.metrics["source_count"] == 3
        assert set(result.metrics["sources"]) == {"wechat", "bilibili", "xiaohongshu"}


class TestEligibilityGate:
    def test_ineligible_with_too_few_fragments(self):
        frags = [_frag(f"f{i}") for i in range(5)]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert result.eligible is False

    def test_ineligible_with_single_source_under_50(self):
        frags = [_frag(f"f{i}", source="wechat") for i in range(35)]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert result.eligible is False  # single source, < 50

    def test_eligible_with_single_source_over_50(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        frags = [
            Fragment(
                id=None,
                category=FindingCategory.HABIT,
                content=f"fragment {i}",
                confidence=0.8,
                source="wechat",
                created_at=base + timedelta(days=i % 30),
            )
            for i in range(55)
        ]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert result.eligible is True

    def test_eligible_with_two_sources_over_30(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        frags = [
            Fragment(
                id=None,
                category=FindingCategory.HABIT,
                content=f"wechat {i}",
                confidence=0.8,
                source="wechat",
                created_at=base + timedelta(days=i),
            )
            for i in range(20)
        ] + [
            Fragment(
                id=None,
                category=FindingCategory.PREFERENCE,
                content=f"bilibili {i}",
                confidence=0.7,
                source="bilibili",
                created_at=base + timedelta(days=i),
            )
            for i in range(15)
        ]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        assert result.eligible is True

    def test_ineligible_with_short_data_span(self):
        # All fragments on same day
        frags = [
            _frag(f"f{i}", source="wechat", hours_offset=i) for i in range(60)
        ]
        engine = SpectrumEngine()
        result = engine.compute_scores(frags)
        # data_span < 7 days
        assert result.eligible is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_persona/test_spectrum.py -v`

Expected: FAIL — `percent.persona.spectrum` does not exist

- [ ] **Step 3: Implement SpectrumEngine**

Create `percent/persona/spectrum.py`:

```python
"""Percent Spectrum — 8-dimension personality scoring from fragments."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from percent.models import Fragment

# Dimensions and which data sources feed them
_CHAT_SOURCES = {"wechat", "telegram", "whatsapp"}
_CONTENT_SOURCES = {"bilibili", "youtube", "xiaohongshu"}

# Night hours: 0-6 (midnight to 6am)
_NIGHT_HOURS = set(range(0, 7))


@dataclass
class SpectrumResult:
    """Result of spectrum computation."""
    dimensions: dict[str, int] = field(default_factory=dict)  # name -> 0-100
    metrics: dict = field(default_factory=dict)  # computed numerical metrics
    eligible: bool = False
    ineligible_reason: str = ""


class SpectrumEngine:
    """Computes 8 personality dimensions from fragments."""

    # Eligibility thresholds
    MIN_FRAGMENTS = 30
    MIN_SINGLE_SOURCE_FRAGMENTS = 50
    MIN_DATA_SPAN_DAYS = 7

    def compute_scores(self, fragments: list[Fragment]) -> SpectrumResult:
        """Compute dimension scores, metrics, and eligibility from fragments."""
        result = SpectrumResult()
        if not fragments:
            result.ineligible_reason = "没有数据"
            return result

        # Basic metrics
        sources = list({f.source for f in fragments})
        timestamps = [f.created_at for f in fragments if f.created_at]
        data_span_days = 0
        if len(timestamps) >= 2:
            sorted_ts = sorted(timestamps)
            delta = sorted_ts[-1] - sorted_ts[0]
            data_span_days = max(delta.days, 0)

        result.metrics = {
            "fragment_count": len(fragments),
            "source_count": len(sources),
            "sources": sources,
            "data_span_days": data_span_days,
        }

        # Eligibility check
        result.eligible = self._check_eligibility(
            fragment_count=len(fragments),
            source_count=len(sources),
            data_span_days=data_span_days,
        )
        if not result.eligible:
            return result

        # Split fragments by source type
        chat_frags = [f for f in fragments if f.source in _CHAT_SOURCES]
        content_frags = [f for f in fragments if f.source in _CONTENT_SOURCES]
        source_set = set(sources)
        has_chat = bool(source_set & _CHAT_SOURCES)
        has_content = bool(source_set & _CONTENT_SOURCES)

        # Compute dimensions (only for available data)
        # 1. 夜行性 — always available (needs timestamps)
        result.dimensions["夜行性"] = self._score_night_owl(fragments)

        # 2-5: Chat-dependent dimensions
        if has_chat:
            result.dimensions["回复惯性"] = self._score_reply_inertia(chat_frags)
            result.dimensions["表达锋利度"] = self._score_expression_sharpness(chat_frags)
            result.dimensions["社交温差"] = self._score_social_temperature(chat_frags)
            result.dimensions["情绪外显度"] = self._score_emotional_visibility(chat_frags)

        # 6-7: Content-dependent dimensions
        if has_content:
            result.dimensions["内容杂食度"] = self._score_content_omnivore(content_frags)
            result.dimensions["品味独占欲"] = self._score_taste_exclusivity(content_frags)

        # 8: Cross-platform contrast — needs 2+ sources
        if len(sources) >= 2:
            result.dimensions["跨平台反差"] = self._score_cross_platform(fragments, sources)

        return result

    def _check_eligibility(
        self, fragment_count: int, source_count: int, data_span_days: int,
    ) -> bool:
        if fragment_count < self.MIN_FRAGMENTS:
            return False
        if data_span_days < self.MIN_DATA_SPAN_DAYS:
            return False
        if source_count < 2 and fragment_count < self.MIN_SINGLE_SOURCE_FRAGMENTS:
            return False
        return True

    def _score_night_owl(self, fragments: list[Fragment]) -> int:
        """Score based on ratio of activity during night hours (0-6am)."""
        if not fragments:
            return 50
        hours = [f.created_at.hour for f in fragments if f.created_at]
        if not hours:
            return 50
        night_count = sum(1 for h in hours if h in _NIGHT_HOURS)
        ratio = night_count / len(hours)
        # Scale: 0% night = 0, 50%+ night = 100
        return min(int(ratio * 200), 100)

    def _score_reply_inertia(self, chat_frags: list[Fragment]) -> int:
        """Score based on content patterns suggesting delayed/absent replies."""
        if not chat_frags:
            return 50
        # Heuristic: look for short responses, question marks without follow-up,
        # time gaps in metadata
        total = len(chat_frags)
        short_replies = sum(1 for f in chat_frags if len(f.content) < 10)
        ratio = short_replies / total if total > 0 else 0
        return min(int(ratio * 150), 100)

    def _score_expression_sharpness(self, chat_frags: list[Fragment]) -> int:
        """Score based on hedging language vs direct expression."""
        if not chat_frags:
            return 50
        hedge_words = {"没事", "还好", "随便", "都行", "无所谓", "算了", "也行", "差不多"}
        total_chars = 0
        hedge_count = 0
        for f in chat_frags:
            total_chars += len(f.content)
            for word in hedge_words:
                hedge_count += f.content.count(word)
        if total_chars == 0:
            return 50
        # More hedging = lower sharpness
        ratio = hedge_count / (total_chars / 100)  # per 100 chars
        # Invert: high hedging = low sharpness
        score = max(0, 100 - int(ratio * 50))
        return min(score, 100)

    def _score_social_temperature(self, chat_frags: list[Fragment]) -> int:
        """Score based on concentration of chat partners (metadata.talker)."""
        if not chat_frags:
            return 50
        talkers = Counter()
        for f in chat_frags:
            # Evidence or content may reference talker; fragments don't have metadata
            # Use source-level grouping as proxy
            talkers[f.source] += 1
        # With only fragment data, we approximate using content diversity
        unique_topics = len(set(f.content[:50] for f in chat_frags))
        ratio = unique_topics / len(chat_frags)
        # High ratio = diverse topics = broad social, low temp gap
        # Low ratio = concentrated = deep social, high temp gap
        return min(int((1 - ratio) * 120), 100)

    def _score_emotional_visibility(self, chat_frags: list[Fragment]) -> int:
        """Score based on emotional word frequency."""
        if not chat_frags:
            return 50
        emotion_markers = {
            "哈哈", "嘿嘿", "呜呜", "唉", "啊啊", "好开心", "好难过",
            "生气", "烦死", "累死", "爱", "恨", "！", "？？", "😂", "😭",
            "🥺", "😡", "❤", "💔", "哭", "笑死", "崩溃", "感动",
        }
        total_chars = 0
        emotion_count = 0
        for f in chat_frags:
            total_chars += len(f.content)
            for marker in emotion_markers:
                emotion_count += f.content.count(marker)
        if total_chars == 0:
            return 50
        ratio = emotion_count / (total_chars / 100)
        return min(int(ratio * 40), 100)

    def _score_content_omnivore(self, content_frags: list[Fragment]) -> int:
        """Score based on diversity of content categories."""
        if not content_frags:
            return 50
        categories = Counter(f.category.value for f in content_frags)
        unique_topics = len(set(f.content[:30] for f in content_frags))
        diversity = unique_topics / max(len(content_frags), 1)
        return min(int(diversity * 120), 100)

    def _score_taste_exclusivity(self, content_frags: list[Fragment]) -> int:
        """Score based on how niche the content preferences are."""
        if not content_frags:
            return 50
        # Heuristic: fewer repeated themes = more niche
        topics = [f.content[:30] for f in content_frags]
        counter = Counter(topics)
        if not counter:
            return 50
        # High concentration in few topics = niche = high exclusivity
        top_ratio = counter.most_common(1)[0][1] / len(topics)
        return min(int(top_ratio * 130), 100)

    def _score_cross_platform(self, fragments: list[Fragment], sources: list[str]) -> int:
        """Score behavioral contrast between platforms."""
        if len(sources) < 2:
            return 0
        by_source: dict[str, list[str]] = {}
        for f in fragments:
            by_source.setdefault(f.source, []).append(f.content[:50])

        # Compare category distributions across sources
        cat_by_source: dict[str, Counter] = {}
        for f in fragments:
            cat_by_source.setdefault(f.source, Counter())[f.category.value] += 1

        # Calculate distribution difference
        if len(cat_by_source) < 2:
            return 50
        distributions = list(cat_by_source.values())
        # Simple distance: count category mismatches
        all_cats = set()
        for d in distributions:
            all_cats.update(d.keys())
        total_diff = 0
        for cat in all_cats:
            values = [d.get(cat, 0) for d in distributions]
            total = sum(values)
            if total > 0:
                proportions = [v / total for v in values]
                diff = max(proportions) - min(proportions)
                total_diff += diff
        avg_diff = total_diff / max(len(all_cats), 1)
        return min(int(avg_diff * 120), 100)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_persona/test_spectrum.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/looanli/Projects/percent
git add percent/persona/spectrum.py tests/test_persona/test_spectrum.py
git commit -m "feat: add SpectrumEngine — 8-dimension personality scoring with eligibility gate"
```

---

### Task 5: Spectrum LLM labeling

**Files:**
- Create: `percent/prompts/spectrum_label.md`
- Modify: `percent/persona/spectrum.py` (add `generate_card_data` method)

- [ ] **Step 1: Create the LLM prompt template**

Create `percent/prompts/spectrum_label.md`:

```markdown
You are analyzing a person's digital personality based on real behavioral data.

## Dimension Scores (0-100)
{dimensions}

## Computed Metrics
{metrics}

## Top Fragments (highest confidence, real evidence)
{fragments}

## Your Task

Based on the above REAL data, generate:

1. **label**: A Chinese persona label in 2-6 characters. Must be specific and slightly self-deprecating. Examples: 「深夜哲学家」「温柔已读不回」「清醒型电子仓鼠」. Do NOT use generic terms like 「内向的人」.

2. **description**: One Chinese sentence (max 20 chars) that makes the person feel "seen" — slightly uncomfortable but accurate. Must reference a specific behavioral pattern from the data. Do NOT be generic.

3. **insights**: Exactly 3 data-driven observations. Each MUST contain:
   - A specific number from the metrics
   - A specific behavior
   - Be written in casual Chinese (like talking to a friend)
   Format each as a single sentence.

Respond in valid JSON only:
```json
{
  "label": "...",
  "description": "...",
  "insights": ["...", "...", "..."]
}
```
```

- [ ] **Step 2: Add `generate_card_data` to SpectrumEngine**

Append to `percent/persona/spectrum.py`:

```python
@dataclass
class CardData:
    """Complete data needed to render a persona card."""
    spectrum: SpectrumResult
    label: str = ""
    description: str = ""
    insights: list[str] = field(default_factory=list)


def generate_card_data(
    fragments: list[Fragment],
    llm_client: object,
    prompts_dir: Path | None = None,
) -> CardData:
    """Compute spectrum + generate label/description/insights via LLM.

    Args:
        fragments: All fragments from the store
        llm_client: LLMClient instance with .complete() method
        prompts_dir: Directory containing spectrum_label.md prompt

    Returns:
        CardData with spectrum scores and LLM-generated text
    """
    import json as json_mod
    from pathlib import Path as PathType

    engine = SpectrumEngine()
    spectrum = engine.compute_scores(fragments)

    card = CardData(spectrum=spectrum)
    if not spectrum.eligible:
        return card

    # Prepare prompt inputs
    dim_text = "\n".join(f"- {k}: {v}/100" for k, v in spectrum.dimensions.items())
    metrics_text = "\n".join(f"- {k}: {v}" for k, v in spectrum.metrics.items())

    # Select top fragments by confidence
    sorted_frags = sorted(fragments, key=lambda f: f.confidence, reverse=True)[:10]
    frag_text = "\n".join(
        f"- [{f.source}] {f.content[:100]} (confidence: {f.confidence})"
        for f in sorted_frags
    )

    # Load prompt template
    if prompts_dir is None:
        prompts_dir = PathType(__file__).parent.parent / "prompts"
    template_path = prompts_dir / "spectrum_label.md"
    template = template_path.read_text(encoding="utf-8")

    prompt = template.format(
        dimensions=dim_text,
        metrics=metrics_text,
        fragments=frag_text,
    )

    # Call LLM
    raw = llm_client.complete(prompt)

    # Parse JSON response
    try:
        # Extract JSON from response (handle markdown code blocks)
        json_str = raw
        if "```json" in raw:
            json_str = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            json_str = raw.split("```")[1].split("```")[0]
        data = json_mod.loads(json_str.strip())
        card.label = data.get("label", "")
        card.description = data.get("description", "")
        card.insights = data.get("insights", [])[:3]
    except (json_mod.JSONDecodeError, IndexError, KeyError):
        card.label = "数字旅人"
        card.description = "你的数据正在讲述你的故事"
        card.insights = []

    return card
```

Add the import at the top of `spectrum.py`:

```python
from pathlib import Path
```

- [ ] **Step 3: Run all spectrum tests**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_persona/test_spectrum.py -v`

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
cd /Users/looanli/Projects/percent
git add percent/persona/spectrum.py percent/prompts/spectrum_label.md
git commit -m "feat: add LLM-based persona label generation for card data"
```

---

### Task 6: `/api/spectrum` endpoint

**Files:**
- Modify: `percent/web.py`
- Create: `tests/test_web_spectrum.py`

- [ ] **Step 1: Write test for spectrum endpoint**

Create `tests/test_web_spectrum.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from percent.persona.spectrum import CardData, SpectrumResult
from percent.web import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_spectrum_returns_eligible_card(client):
    card = CardData(
        spectrum=SpectrumResult(
            dimensions={"夜行性": 85, "回复惯性": 72},
            metrics={"fragment_count": 60, "source_count": 2, "sources": ["wechat", "bilibili"], "data_span_days": 30},
            eligible=True,
        ),
        label="深夜哲学家",
        description="凌晨三点的你比白天更诚实",
        insights=["你的已读不回率 87%", "凌晨活跃度是白天的 3.2 倍", "你在 B站和微信上判若两人"],
    )

    with patch("percent.web._require_config") as mock_cfg:
        mock_cfg.return_value.fragments_db_path.exists.return_value = True
        mock_cfg.return_value.percent_dir = MagicMock()
        with patch("percent.web.FragmentStore") as MockStore:
            MockStore.return_value.get_all.return_value = []
            with patch("percent.web.generate_card_data", return_value=card):
                resp = client.get("/api/spectrum")

    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is True
    assert data["label"] == "深夜哲学家"
    assert len(data["insights"]) == 3
    assert "夜行性" in data["dimensions"]


def test_spectrum_returns_ineligible(client):
    card = CardData(
        spectrum=SpectrumResult(eligible=False, ineligible_reason="数据不足"),
    )

    with patch("percent.web._require_config") as mock_cfg:
        mock_cfg.return_value.fragments_db_path.exists.return_value = True
        with patch("percent.web.FragmentStore") as MockStore:
            MockStore.return_value.get_all.return_value = []
            with patch("percent.web.generate_card_data", return_value=card):
                resp = client.get("/api/spectrum")

    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_web_spectrum.py -v`

Expected: FAIL — no `/api/spectrum` endpoint

- [ ] **Step 3: Add the endpoint to web.py**

Add to `percent/web.py` after the existing imports:

```python
from percent.persona.spectrum import generate_card_data
```

Add the endpoint after the existing `/api/insights` route:

```python
@app.get("/api/spectrum")
def get_spectrum() -> dict:
    """Return persona spectrum: dimension scores, label, insights, eligibility."""
    cfg = _require_config()
    db_path = cfg.fragments_db_path
    if not db_path.exists():
        return {"eligible": False, "reason": "没有数据"}

    store = FragmentStore(db_path)
    fragments = store.get_all()
    store.close()

    # Build LLM client for label generation (only if eligible)
    from percent.llm.client import LLMClient
    client = LLMClient(
        provider=cfg.llm_provider,
        model=cfg.llm_model,
        api_key=cfg.llm_api_key,
    )
    prompts_dir = Path(__file__).parent / "prompts"

    card = generate_card_data(fragments, client, prompts_dir)

    return {
        "eligible": card.spectrum.eligible,
        "reason": card.spectrum.ineligible_reason,
        "dimensions": card.spectrum.dimensions,
        "metrics": card.spectrum.metrics,
        "label": card.label,
        "description": card.description,
        "insights": card.insights,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_web_spectrum.py -v`

Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest -q`

Expected: All pass

- [ ] **Step 6: Commit**

```bash
cd /Users/looanli/Projects/percent
git add percent/web.py tests/test_web_spectrum.py
git commit -m "feat: add /api/spectrum endpoint for persona card data"
```

---

## Phase 3: Card UI

### Task 7: Stellar chart SVG + card layout + image export

**Files:**
- Modify: `percent/static/index.html`

This is the frontend implementation. Due to the size of the HTML file (2000+ lines), this task describes the specific sections to add. The card UI consists of three parts: (a) stellar chart SVG renderer, (b) card layout HTML/CSS, (c) image export with modern-screenshot.

**Note for implementor:** Before writing any UI code, invoke the `frontend-design` skill from Impeccable to load the design system. After completing the UI, run `/critique` for UX review and `/polish` for final quality pass. The visual design must follow the spec's color system (#131211 bg, #e8e2d9 text, #c4654a accent only on chart bars) with SVG grain texture.

- [ ] **Step 1: Add the modern-screenshot library import**

Add to the `<head>` section of `percent/static/index.html`, after the existing `<script>` tags:

```html
<script type="module">
  import { domToPng } from 'https://esm.sh/modern-screenshot@4';
  window.domToPng = domToPng;
</script>
```

- [ ] **Step 2: Add card view CSS**

Add card-specific CSS after the existing chat view styles. Key classes needed:
- `.card-view` — the full card view container
- `.card-canvas` — the 1080x1440 card element (scaled down for screen display)
- `.stellar-chart` — SVG container
- `.card-label` — Instrument Serif, 72-96pt persona label
- `.card-description` — one-line description
- `.card-insights` — three data insights list
- `.card-footer` — credibility footer with source info
- `.card-export-btn` — "保存为图片" button
- `.card-fallback` — shown when ineligible (progress indicator)

- [ ] **Step 3: Add card view HTML structure**

Add a new view section in the HTML body (alongside existing import-view and chat-view):

```html
<div class="card-view" id="cardView">
  <!-- Card canvas — this is what gets exported as image -->
  <div class="card-canvas" id="cardCanvas">
    <div class="card-brand">% Percent</div>
    <div class="card-label" id="cardLabel">「」</div>
    <div class="card-description" id="cardDescription"></div>
    <div class="card-chart-container">
      <svg id="stellarChart" viewBox="0 0 400 400"></svg>
    </div>
    <div class="card-insights" id="cardInsights"></div>
    <div class="card-footer" id="cardFooter"></div>
    <svg class="card-grain" width="100%" height="100%">
      <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/></filter>
      <rect width="100%" height="100%" filter="url(#grain)" opacity="0.03"/>
    </svg>
  </div>

  <!-- Export button (outside canvas) -->
  <button class="card-export-btn" id="cardExportBtn">保存为图片</button>

  <!-- Fallback when ineligible -->
  <div class="card-fallback view-hidden" id="cardFallback">
    <p>数据还在积累中</p>
    <p>再导入一些数据解锁你的人格画像</p>
  </div>
</div>
```

- [ ] **Step 4: Add stellar chart rendering JavaScript**

Add a JavaScript function that takes dimension data and renders the SVG stellar chart:

```javascript
function renderStellarChart(svgEl, dimensions) {
  const cx = 200, cy = 200, maxR = 150;
  const entries = Object.entries(dimensions);
  const n = entries.length;
  if (n === 0) return;

  let svg = '';
  // Concentric guide circles
  for (let r of [0.25, 0.5, 0.75, 1.0]) {
    svg += `<circle cx="${cx}" cy="${cy}" r="${maxR * r}" fill="none" stroke="var(--border)" stroke-width="0.5" opacity="0.05"/>`;
  }

  const angleStep = (2 * Math.PI) / n;
  entries.forEach(([name, score], i) => {
    const angle = -Math.PI / 2 + i * angleStep;
    const r = (score / 100) * maxR;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;

    // Tapered bar (triangle from center to point)
    const perpAngle = angle + Math.PI / 2;
    const baseWidth = 8;
    const bx1 = cx + Math.cos(perpAngle) * baseWidth;
    const by1 = cy + Math.sin(perpAngle) * baseWidth;
    const bx2 = cx - Math.cos(perpAngle) * baseWidth;
    const by2 = cy - Math.sin(perpAngle) * baseWidth;

    svg += `<polygon points="${bx1},${by1} ${x},${y} ${bx2},${by2}" fill="var(--accent)" opacity="${0.3 + (score / 100) * 0.7}"/>`;

    // Label at tip
    const labelR = r + 20;
    const lx = cx + Math.cos(angle) * labelR;
    const ly = cy + Math.sin(angle) * labelR;
    const anchor = Math.abs(angle) > Math.PI / 2 ? 'end' : 'start';
    svg += `<text x="${lx}" y="${ly}" text-anchor="middle" fill="var(--text-dim)" font-size="11" font-family="'DM Sans'">${name}</text>`;
  });

  svgEl.innerHTML = svg;
}
```

- [ ] **Step 5: Add card data fetching and rendering logic**

```javascript
async function loadCard() {
  try {
    const resp = await fetch('/api/spectrum');
    const data = await resp.json();

    if (!data.eligible) {
      document.getElementById('cardCanvas').classList.add('view-hidden');
      document.getElementById('cardExportBtn').classList.add('view-hidden');
      document.getElementById('cardFallback').classList.remove('view-hidden');
      return;
    }

    document.getElementById('cardLabel').textContent = `「${data.label}」`;
    document.getElementById('cardDescription').textContent = data.description;

    // Render stellar chart
    renderStellarChart(document.getElementById('stellarChart'), data.dimensions);

    // Render insights
    const insightsEl = document.getElementById('cardInsights');
    insightsEl.innerHTML = data.insights
      .map(i => `<div class="card-insight-item">· ${i}</div>`)
      .join('');

    // Render footer
    const m = data.metrics;
    document.getElementById('cardFooter').textContent =
      `${m.source_count} sources · ${m.fragment_count} fragments · ${m.data_span_days} days`;

  } catch (e) {
    console.error('Failed to load card:', e);
  }
}
```

- [ ] **Step 6: Add image export function**

```javascript
async function exportCard() {
  const el = document.getElementById('cardCanvas');
  const btn = document.getElementById('cardExportBtn');
  btn.textContent = '正在生成...';
  btn.disabled = true;

  try {
    await document.fonts.ready;
    const dataUrl = await window.domToPng(el, {
      scale: 3,
      quality: 1.0,
      backgroundColor: '#131211',
    });

    const link = document.createElement('a');
    link.download = 'percent-persona.png';
    link.href = dataUrl;
    link.click();
  } catch (e) {
    console.error('Export failed:', e);
  } finally {
    btn.textContent = '保存为图片';
    btn.disabled = false;
  }
}

document.getElementById('cardExportBtn')?.addEventListener('click', exportCard);
```

- [ ] **Step 7: Add navigation to card view**

Add a "人格画像" button in the header, and wire up navigation so after analysis completes, the UI navigates to the card view instead of chat view.

- [ ] **Step 8: Test manually**

Run: `cd /Users/looanli/Projects/percent && uv run percent web`

Open `http://127.0.0.1:18900` in browser. If you have existing data with sufficient fragments, the card view should display. Verify:
- Stellar chart renders with correct dimensions
- Label and description display
- Insights show
- "保存为图片" exports a PNG
- If insufficient data, fallback message shows

- [ ] **Step 9: Commit**

```bash
cd /Users/looanli/Projects/percent
git add percent/static/index.html
git commit -m "feat: add persona card UI with stellar chart SVG and image export"
```

---

### Task 8: XHS parser CLI integration (parallel, does NOT block card)

**Files:**
- Modify: `percent/cli.py`
- Create: `tests/test_parsers/test_xiaohongshu.py`

- [ ] **Step 1: Write test for XHS parser**

Create `tests/test_parsers/test_xiaohongshu.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from percent.models import ChunkType
from percent.parsers.xiaohongshu import XiaohongshuParser


@pytest.fixture()
def parser() -> XiaohongshuParser:
    return XiaohongshuParser()


def test_validate_valid_json(parser: XiaohongshuParser, tmp_path: Path) -> None:
    data = [{"note_id": "123", "title": "Test Note", "desc": "Description"}]
    f = tmp_path / "xhs.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    assert parser.validate(f) is True


def test_validate_invalid_json(parser: XiaohongshuParser, tmp_path: Path) -> None:
    data = [{"random_key": "value"}]
    f = tmp_path / "data.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    assert parser.validate(f) is False


def test_parse_json_produces_chunks(parser: XiaohongshuParser, tmp_path: Path) -> None:
    data = [
        {"note_id": "1", "title": "Good Food", "desc": "Amazing restaurant", "time": "1700000000"},
        {"note_id": "2", "title": "Travel", "desc": "Beach trip", "time": "1700100000"},
    ]
    f = tmp_path / "xhs.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    chunks = parser.parse(f)
    assert len(chunks) == 2
    assert chunks[0].source == "xiaohongshu"
    assert chunks[0].type == ChunkType.SOCIAL_INTERACTION
    assert "Good Food" in chunks[0].content


def test_parse_skips_empty_notes(parser: XiaohongshuParser, tmp_path: Path) -> None:
    data = [
        {"note_id": "1", "title": "", "desc": ""},  # Empty
        {"note_id": "2", "title": "Real Note", "desc": "Content"},
    ]
    f = tmp_path / "xhs.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    chunks = parser.parse(f)
    assert len(chunks) == 1


def test_import_guide_nonempty(parser: XiaohongshuParser) -> None:
    guide = parser.get_import_guide()
    assert isinstance(guide, str) and len(guide) > 0
```

- [ ] **Step 2: Run tests to verify they pass** (parser already exists)

Run: `cd /Users/looanli/Projects/percent && uv run python -m pytest tests/test_parsers/test_xiaohongshu.py -v`

Expected: ALL PASS (parser code already written)

- [ ] **Step 3: Add xiaohongshu to CLI parser registry**

Find the parser registry in `percent/cli.py` and add:

```python
"xiaohongshu": "percent.parsers.xiaohongshu.XiaohongshuParser",
```

Also add the CLI command variant (follow the existing pattern for other sources).

- [ ] **Step 4: Commit**

```bash
cd /Users/looanli/Projects/percent
git add percent/cli.py tests/test_parsers/test_xiaohongshu.py
git commit -m "feat: complete XHS parser integration — CLI + tests"
```

---

### Task 9: Post-analysis flow redirect to card

**Files:**
- Modify: `percent/static/index.html`

- [ ] **Step 1: Change post-analysis navigation target**

Find the JavaScript code that handles the completion of analysis (the analyzing overlay success handler). Change it to navigate to the card view instead of the chat view:

```javascript
// After analysis success:
// OLD: showView('chat');
// NEW: showView('card');
loadCard();
```

- [ ] **Step 2: Test manually**

Upload a file through the import flow, run analysis, and verify the UI navigates to the card view after completion.

- [ ] **Step 3: Commit**

```bash
cd /Users/looanli/Projects/percent
git add percent/static/index.html
git commit -m "feat: redirect to persona card after analysis completion"
```

---

## Execution Summary

| Phase | Tasks | Goal |
|-------|-------|------|
| Phase 1 | Tasks 1-3 | P0 fixes — parser regression, evidence API, docs |
| Phase 2 | Tasks 4-6 | Spectrum engine — scoring, LLM labeling, API endpoint |
| Phase 3 | Tasks 7-9 | Card UI — stellar chart, layout, export, navigation |

**Total: 9 tasks, ~45 steps**

After Phase 3, the full user journey works:
```
pip install percent → percent init → import wechat + bilibili → percent web → see persona card → export image → share on 小红书
```

Phase 4-6 (imports.json provenance, PyPI publication, P2 items) can be planned separately after the card ships.
