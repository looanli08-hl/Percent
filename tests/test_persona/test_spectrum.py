"""Tests for the SpectrumEngine — 8-dimension personality scoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from percent.models import FindingCategory, Fragment

UTC = timezone.utc


# ─── helpers ────────────────────────────────────────────────────────────────


def _frag(
    content: str,
    source: str = "wechat",
    category: FindingCategory = FindingCategory.HABIT,
    confidence: float = 0.8,
    hours_offset: int = 0,
    evidence: str = "",
) -> Fragment:
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


def _make_fragments(
    n: int,
    source: str = "wechat",
    content: str = "test content",
    hours_offset: int = 0,
) -> list[Fragment]:
    """Create n identical fragments from the same source."""
    return [_frag(content, source=source, hours_offset=hours_offset) for _ in range(n)]


def _make_eligible_fragments(
    n: int = 35,
    sources: list[str] | None = None,
    span_days: int = 10,
) -> list[Fragment]:
    """Create a set of fragments that clears the eligibility gate."""
    if sources is None:
        sources = ["wechat", "bilibili"]
    frags = []
    per_source = n // len(sources)
    for i, src in enumerate(sources):
        for j in range(per_source):
            # Spread timestamps across span_days
            offset_hours = int(j * (span_days * 24 / per_source))
            frags.append(_frag(f"content {j}", source=src, hours_offset=offset_hours))
    # Top up to n if needed
    while len(frags) < n:
        offset_hours = span_days * 24 - 1
        frags.append(_frag("extra content", source=sources[0], hours_offset=offset_hours))
    return frags


# ─── TestSpectrumScoring ─────────────────────────────────────────────────────


class TestSpectrumScoring:
    def test_returns_spectrum_result(self):
        from percent.persona.spectrum import SpectrumEngine, SpectrumResult

        engine = SpectrumEngine()
        frags = _make_eligible_fragments()
        result = engine.compute(frags)
        assert isinstance(result, SpectrumResult)

    def test_eligible_result_has_dimensions_dict(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_eligible_fragments()
        result = engine.compute(frags)
        assert result.eligible is True
        assert isinstance(result.dimensions, dict)

    def test_all_scores_in_range_0_to_100(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_eligible_fragments()
        result = engine.compute(frags)
        for name, score in result.dimensions.items():
            assert 0 <= score <= 100, f"Dimension {name!r} score {score} out of range"

    def test_night_owl_high_when_all_night(self):
        """Fragments entirely in 0-6am should yield 夜行性 = 100."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # hours 0-5: night time, spread across 10 days to satisfy data span gate
        frags = []
        sources = ["wechat", "bilibili"]
        for i in range(35):
            src = sources[i % 2]
            night_hour = i % 5  # 0..4 (safely within 0-6am)
            day_offset = i * 10 // 34  # spread 35 frags over 10 days
            hours_offset = day_offset * 24 + night_hour
            frags.append(_frag(f"night content {i}", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["夜行性"] == 100

    def test_night_owl_low_when_all_daytime(self):
        """Fragments entirely in 9am-10pm should yield 夜行性 = 0."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        sources = ["wechat", "bilibili"]
        for i in range(35):
            src = sources[i % 2]
            # 10am each day, spread over 10 days
            hours_offset = (i // 4) * 24 + 10
            frags.append(_frag(f"day content {i}", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["夜行性"] == 0

    def test_night_owl_mid_when_half_night(self):
        """50% night fragments should yield exactly 100 (boundary case at >=50%)."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        sources = ["wechat", "bilibili"]
        for i in range(40):
            src = sources[i % 2]
            # Even indices: 3am (night), odd indices: 10am (day)
            if i % 2 == 0:
                hour = 3
            else:
                hour = 10
            day = i // 2
            hours_offset = day * 24 + hour
            frags.append(_frag(f"mixed {i}", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        # 50% night = score 100 (at the cap)
        assert result.dimensions["夜行性"] == 100

    def test_chat_dimensions_absent_without_chat_source(self):
        """Without wechat/telegram/whatsapp, chat-only dimensions should be absent."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # Only content sources, with enough fragments
        frags = []
        for i in range(55):
            src = "bilibili" if i % 2 == 0 else "youtube"
            hours_offset = (i // 4) * 24 + 10
            frags.append(_frag(f"video content {i}", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        # Chat-only dimensions must not appear
        chat_dims = {"回复惯性", "表达锋利度", "社交温差", "情绪外显度"}
        for dim in chat_dims:
            assert dim not in result.dimensions, f"{dim!r} should be absent without chat source"

    def test_content_dimensions_absent_without_content_source(self):
        """Without bilibili/youtube/xiaohongshu, content-only dimensions should be absent."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # Only chat sources
        frags = []
        for i in range(55):
            src = "wechat" if i % 2 == 0 else "telegram"
            hours_offset = (i // 4) * 24 + 10
            frags.append(_frag(f"chat message {i}", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        content_dims = {"内容杂食度", "品味独占欲"}
        for dim in content_dims:
            assert dim not in result.dimensions, f"{dim!r} should be absent without content source"

    def test_cross_platform_absent_with_single_source(self):
        """跨平台反差 requires 2+ sources."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # Single source with >50 fragments and span >= 7 days
        frags = []
        for i in range(55):
            hours_offset = (i // 8) * 24 + 10
            frags.append(_frag(f"single source content {i}", source="wechat", hours_offset=hours_offset))
        result = engine.compute(frags)
        assert "跨平台反差" not in result.dimensions

    def test_cross_platform_present_with_two_sources(self):
        """跨平台反差 should appear when 2+ sources exist."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_eligible_fragments(n=40, sources=["wechat", "bilibili"])
        result = engine.compute(frags)
        assert result.eligible is True
        assert "跨平台反差" in result.dimensions

    def test_reply_inertia_high_for_short_replies(self):
        """回复惯性 should be high when most chat messages are < 10 chars."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        # 35+ fragments from 2 sources, all short chat messages
        for i in range(40):
            src = "wechat" if i % 2 == 0 else "telegram"
            hours_offset = (i // 4) * 24 + 10
            frags.append(_frag("ok", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["回复惯性"] >= 80

    def test_reply_inertia_low_for_long_replies(self):
        """回复惯性 should be low when most chat messages are >= 10 chars."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        for i in range(40):
            src = "wechat" if i % 2 == 0 else "telegram"
            hours_offset = (i // 4) * 24 + 10
            frags.append(_frag("This is a long message that definitely exceeds ten characters.", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["回复惯性"] <= 20

    def test_expression_sharpness_low_for_heavy_hedging(self):
        """表达锋利度 should be low when hedging language is frequent."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        for i in range(40):
            src = "wechat" if i % 2 == 0 else "telegram"
            hours_offset = (i // 4) * 24 + 10
            # Heavy hedging
            frags.append(_frag("没事 还好 随便 都行 无所谓", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["表达锋利度"] <= 30

    def test_expression_sharpness_high_for_no_hedging(self):
        """表达锋利度 should be high when no hedging language is present."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        for i in range(40):
            src = "wechat" if i % 2 == 0 else "telegram"
            hours_offset = (i // 4) * 24 + 10
            frags.append(_frag("I strongly believe this is correct and will act on it.", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["表达锋利度"] >= 70

    def test_emotional_visibility_high_with_markers(self):
        """情绪外显度 should be high with lots of emotional markers."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        for i in range(40):
            src = "wechat" if i % 2 == 0 else "telegram"
            hours_offset = (i // 4) * 24 + 10
            frags.append(_frag("哈哈哈！😂笑死了！真的太崩溃了！", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["情绪外显度"] >= 70

    def test_emotional_visibility_low_without_markers(self):
        """情绪外显度 should be low with no emotional markers."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        for i in range(40):
            src = "wechat" if i % 2 == 0 else "telegram"
            hours_offset = (i // 4) * 24 + 10
            frags.append(_frag("The project status update is completed as scheduled.", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["情绪外显度"] <= 20

    def test_content_omnivore_high_for_diverse_categories(self):
        """内容杂食度 should be high for diverse content prefixes."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        categories = ["科技", "音乐", "美食", "旅行", "体育", "历史", "艺术", "游戏"]
        for i in range(40):
            src = "bilibili" if i % 2 == 0 else "youtube"
            cat = categories[i % len(categories)]
            hours_offset = (i // 4) * 24 + 10
            frags.append(_frag(f"{cat}：content {i}", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["内容杂食度"] >= 70

    def test_taste_exclusivity_high_for_concentrated_topics(self):
        """品味独占欲 should be high when most content is the same category."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = []
        for i in range(40):
            src = "bilibili" if i % 2 == 0 else "youtube"
            hours_offset = (i // 4) * 24 + 10
            # All the same category
            frags.append(_frag(f"科技：video about AI and technology {i}", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.dimensions["品味独占欲"] >= 70


# ─── TestSpectrumMetrics ─────────────────────────────────────────────────────


class TestSpectrumMetrics:
    def test_fragment_count_in_metrics(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_eligible_fragments(n=35)
        result = engine.compute(frags)
        assert result.metrics["fragment_count"] == 35

    def test_source_count_in_metrics(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_eligible_fragments(n=40, sources=["wechat", "bilibili"])
        result = engine.compute(frags)
        assert result.metrics["source_count"] == 2

    def test_sources_list_in_metrics(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_eligible_fragments(n=40, sources=["wechat", "bilibili"])
        result = engine.compute(frags)
        assert set(result.metrics["sources"]) == {"wechat", "bilibili"}

    def test_data_span_days_correct(self):
        """data_span_days should reflect the actual spread in timestamps."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_eligible_fragments(n=40, sources=["wechat", "bilibili"], span_days=14)
        result = engine.compute(frags)
        # Should be at least 13 days (exact depends on helper spacing)
        assert result.metrics["data_span_days"] >= 13

    def test_data_span_days_single_day(self):
        """When all fragments are on the same day, span should be 0."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # Build ineligible set (just to check span math)
        frags = [_frag(f"msg {i}", source="wechat", hours_offset=i % 12) for i in range(10)]
        result = engine.compute(frags)
        assert result.metrics["data_span_days"] == 0

    def test_metrics_always_present_even_when_ineligible(self):
        """Metrics should be computed regardless of eligibility."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_fragments(5, source="wechat")
        result = engine.compute(frags)
        assert result.eligible is False
        assert "fragment_count" in result.metrics
        assert result.metrics["fragment_count"] == 5


# ─── TestEligibilityGate ─────────────────────────────────────────────────────


class TestEligibilityGate:
    def test_too_few_fragments_ineligible(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # 29 fragments from 2 sources, 10 days — should fail fragment count gate
        frags = _make_eligible_fragments(n=29, sources=["wechat", "bilibili"], span_days=10)
        result = engine.compute(frags)
        assert result.eligible is False
        assert result.ineligible_reason != ""

    def test_single_source_under_50_ineligible(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # Single source, 35 fragments, 10-day span
        frags = [
            _frag(f"msg {i}", source="wechat", hours_offset=(i // 4) * 24 + 10)
            for i in range(35)
        ]
        result = engine.compute(frags)
        assert result.eligible is False
        assert "single" in result.ineligible_reason.lower() or "source" in result.ineligible_reason.lower()

    def test_single_source_over_50_eligible(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # Single source, 55 fragments, 10-day span
        frags = [
            _frag(f"msg {i}", source="wechat", hours_offset=(i // 6) * 24 + 10)
            for i in range(55)
        ]
        result = engine.compute(frags)
        assert result.eligible is True

    def test_two_sources_30_fragments_eligible(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_eligible_fragments(n=30, sources=["wechat", "bilibili"], span_days=10)
        result = engine.compute(frags)
        assert result.eligible is True

    def test_short_data_span_ineligible(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # 35 fragments, 2 sources, but only 3-day span
        frags = []
        for i in range(35):
            src = "wechat" if i % 2 == 0 else "bilibili"
            # 3 days = 72 hours max
            hours_offset = (i % 72)
            frags.append(_frag(f"msg {i}", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is False
        assert "span" in result.ineligible_reason.lower() or "day" in result.ineligible_reason.lower()

    def test_exactly_7_days_span_eligible(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        # 30 fragments, 2 sources, at least 7-day span
        frags = []
        for i in range(30):
            src = "wechat" if i % 2 == 0 else "bilibili"
            # Spread over 7 days: last fragment at hour 7*24=168
            hours_offset = i * 168 // (30 - 1)
            frags.append(_frag(f"msg {i}", source=src, hours_offset=hours_offset))
        result = engine.compute(frags)
        assert result.eligible is True

    def test_ineligible_result_has_empty_dimensions(self):
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_fragments(5, source="wechat")
        result = engine.compute(frags)
        assert result.eligible is False
        assert result.dimensions == {}

    def test_eligible_result_has_non_empty_reason(self):
        """Eligible results should have an empty ineligible_reason."""
        from percent.persona.spectrum import SpectrumEngine

        engine = SpectrumEngine()
        frags = _make_eligible_fragments(n=35, sources=["wechat", "bilibili"], span_days=10)
        result = engine.compute(frags)
        assert result.eligible is True
        assert result.ineligible_reason == ""
