"""Spectrum dimension scoring engine.

Computes 8 personality dimensions (0-100) from Fragment lists using
purely rule-based / statistical heuristics — no LLM calls.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import timezone
from pathlib import Path

from percent.models import Fragment

# ─── Source groupings ────────────────────────────────────────────────────────

CHAT_SOURCES: frozenset[str] = frozenset({"wechat", "telegram", "whatsapp"})
CONTENT_SOURCES: frozenset[str] = frozenset({"bilibili", "youtube", "xiaohongshu"})

# ─── Hedging vocabulary ──────────────────────────────────────────────────────

_HEDGE_WORDS: list[str] = [
    "没事", "还好", "随便", "都行", "无所谓", "算了", "也行", "差不多",
]

# ─── Emotional marker patterns ───────────────────────────────────────────────

_EMOTION_WORDS: list[str] = [
    "哈哈", "嘿嘿", "呜呜", "唉", "哭", "笑死", "崩溃", "感动",
]
_EMOTION_EMOJIS: list[str] = [
    "😂", "😭", "🥺", "😡", "❤", "💔",
]
_EMOTION_PUNCT: list[str] = ["！！", "？？"]  # doubled punctuation counts as emotional

# Pre-compiled patterns
_HEDGE_PATTERN = re.compile("|".join(re.escape(w) for w in _HEDGE_WORDS))
_EMOTION_WORD_PATTERN = re.compile("|".join(re.escape(w) for w in _EMOTION_WORDS))
_EMOTION_EMOJI_PATTERN = re.compile("|".join(re.escape(e) for e in _EMOTION_EMOJIS))
_EMOTION_PUNCT_PATTERN = re.compile("|".join(re.escape(p) for p in _EMOTION_PUNCT))
# Single ! or ? are also counted but weighted less
_EXCLAIM_PATTERN = re.compile(r"[！!]")


# ─── Data structures ─────────────────────────────────────────────────────────


@dataclass
class SpectrumResult:
    """Output of SpectrumEngine.compute()."""

    dimensions: dict[str, int] = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    eligible: bool = False
    ineligible_reason: str = ""


# ─── Engine ──────────────────────────────────────────────────────────────────


class SpectrumEngine:
    """Compute spectrum dimensions from a list of Fragment objects."""

    # ── public API ──────────────────────────────────────────────────────────

    def compute(self, fragments: list[Fragment]) -> SpectrumResult:
        """Return a SpectrumResult for the given fragment set."""
        metrics = self._compute_metrics(fragments)
        result = SpectrumResult(metrics=metrics)

        eligible, reason = self._check_eligibility(metrics, fragments)
        result.eligible = eligible
        result.ineligible_reason = reason

        if not eligible:
            return result

        result.dimensions = self._score_dimensions(fragments, metrics)
        return result

    # ── eligibility ─────────────────────────────────────────────────────────

    def _check_eligibility(
        self,
        metrics: dict,
        fragments: list[Fragment],
    ) -> tuple[bool, str]:
        n = metrics["fragment_count"]
        sources = metrics["source_count"]
        span = metrics["data_span_days"]

        if n < 30:
            return False, f"Too few fragments: {n} (minimum 30)"

        if sources < 2:
            # Single source allowed only with >= 50 fragments
            if n < 50:
                return (
                    False,
                    f"Single source with only {n} fragments (need 50 for single source or use 2+ sources)",
                )

        # Note: data_span is based on fragment created_at (import time), not
        # original data timestamps.  For batch imports the span is always short,
        # so we only enforce the span check when there is a single source with
        # borderline fragment count.  Multi-source or high-fragment users pass.
        if sources < 2 and n < 50 and span < 7:
            return False, f"Data span too short: {span} days (minimum 7 for single source)"

        return True, ""

    # ── metrics ─────────────────────────────────────────────────────────────

    def _compute_metrics(self, fragments: list[Fragment]) -> dict:
        n = len(fragments)
        sources = sorted({f.source for f in fragments})

        # data_span_days: from earliest to latest created_at
        if n < 2:
            span_days = 0
        else:
            timestamps = [
                f.created_at.replace(tzinfo=timezone.utc)
                if f.created_at.tzinfo is None
                else f.created_at
                for f in fragments
            ]
            earliest = min(timestamps)
            latest = max(timestamps)
            span_days = (latest - earliest).days

        return {
            "fragment_count": n,
            "source_count": len(sources),
            "sources": sources,
            "data_span_days": span_days,
        }

    # ── dimension scoring ───────────────────────────────────────────────────

    def _score_dimensions(
        self,
        fragments: list[Fragment],
        metrics: dict,
    ) -> dict[str, int]:
        source_set = set(metrics["sources"])
        has_chat = bool(source_set & CHAT_SOURCES)
        has_content = bool(source_set & CONTENT_SOURCES)
        multi_source = metrics["source_count"] >= 2

        chat_frags = [f for f in fragments if f.source in CHAT_SOURCES]
        content_frags = [f for f in fragments if f.source in CONTENT_SOURCES]

        dims: dict[str, int] = {}

        # 夜行性 — available for any source
        dims["夜行性"] = self._score_night_owl(fragments)

        # Chat-only dimensions
        if has_chat:
            dims["回复惯性"] = self._score_reply_inertia(chat_frags)
            dims["表达锋利度"] = self._score_expression_sharpness(chat_frags)
            dims["社交温差"] = self._score_social_temperature_gap(chat_frags)
            dims["情绪外显度"] = self._score_emotional_visibility(chat_frags)

        # Content-only dimensions
        if has_content:
            dims["内容杂食度"] = self._score_content_omnivore(content_frags)
            dims["品味独占欲"] = self._score_taste_exclusivity(content_frags)

        # Requires 2+ sources
        if multi_source:
            dims["跨平台反差"] = self._score_cross_platform_contrast(fragments, source_set)

        return dims

    # ── individual scorers ──────────────────────────────────────────────────

    @staticmethod
    def _clamp(value: float) -> int:
        """Clamp a 0.0-1.0 ratio to 0-100 int."""
        return max(0, min(100, round(value * 100)))

    def _score_night_owl(self, fragments: list[Fragment]) -> int:
        """Ratio of fragments in 0-6am hours. 50%+ → 100."""
        if not fragments:
            return 0
        night = sum(1 for f in fragments if f.created_at.hour < 6)
        ratio = night / len(fragments)
        # Scale: 0% → 0, 50%+ → 100 (linear, capped)
        scaled = min(ratio / 0.5, 1.0)
        return self._clamp(scaled)

    def _score_reply_inertia(self, chat_frags: list[Fragment]) -> int:
        """Ratio of chat messages shorter than 10 chars → 0-100."""
        if not chat_frags:
            return 0
        short = sum(1 for f in chat_frags if len(f.content) < 10)
        return self._clamp(short / len(chat_frags))

    def _score_expression_sharpness(self, chat_frags: list[Fragment]) -> int:
        """Hedging frequency per 100 chars, inverted.

        More hedging → lower sharpness.
        """
        if not chat_frags:
            return 50  # neutral default
        total_chars = sum(len(f.content) for f in chat_frags)
        if total_chars == 0:
            return 50
        all_text = "".join(f.content for f in chat_frags)
        hedge_count = len(_HEDGE_PATTERN.findall(all_text))
        # Rate per 100 chars; cap at 5 hedges/100 chars → 0 sharpness
        hedge_rate = hedge_count / total_chars * 100
        cap = 5.0
        hedge_ratio = min(hedge_rate / cap, 1.0)
        # Invert: high hedging = low sharpness
        return self._clamp(1.0 - hedge_ratio)

    def _score_social_temperature_gap(self, chat_frags: list[Fragment]) -> int:
        """Topic concentration (unique content prefixes / total).

        Lower diversity → higher temperature gap.
        """
        if not chat_frags:
            return 0
        # Use first word as "topic prefix"
        prefixes = [f.content.split()[0] if f.content.split() else "" for f in chat_frags]
        unique_prefixes = len(set(prefixes))
        total = len(chat_frags)
        diversity_ratio = unique_prefixes / total  # 0 = all same, 1 = all unique
        # Invert: low diversity = high temperature gap
        return self._clamp(1.0 - diversity_ratio)

    def _score_emotional_visibility(self, chat_frags: list[Fragment]) -> int:
        """Emotional marker frequency per 100 chars → 0-100."""
        if not chat_frags:
            return 0
        all_text = "".join(f.content for f in chat_frags)
        total_chars = len(all_text)
        if total_chars == 0:
            return 0

        count = (
            len(_EMOTION_WORD_PATTERN.findall(all_text))
            + len(_EMOTION_EMOJI_PATTERN.findall(all_text))
            + len(_EMOTION_PUNCT_PATTERN.findall(all_text))
            + len(_EXCLAIM_PATTERN.findall(all_text)) // 2  # single ! weighted less
        )

        # Cap at 10 markers per 100 chars → 100
        rate = count / total_chars * 100
        cap = 10.0
        return self._clamp(min(rate / cap, 1.0))

    def _score_content_omnivore(self, content_frags: list[Fragment]) -> int:
        """Unique content-category variety among content fragments → 0-100.

        Extracts the topic prefix (before ：) or first word as category label.
        Normalises the unique count against a reasonable ceiling (8 categories).
        """
        if not content_frags:
            return 0
        prefixes = [
            f.content.split("：")[0] if "：" in f.content
            else (f.content.split()[0] if f.content.split() else "")
            for f in content_frags
        ]
        unique = len(set(prefixes))
        # 8 distinct categories = full score; scale linearly up to that ceiling
        CATEGORY_CEILING = 8
        diversity = unique / CATEGORY_CEILING
        return self._clamp(diversity)

    def _score_taste_exclusivity(self, content_frags: list[Fragment]) -> int:
        """Concentration of most common topic prefix → 0-100."""
        if not content_frags:
            return 0
        prefixes = [f.content.split("：")[0] if "：" in f.content else f.content.split()[0] if f.content.split() else "" for f in content_frags]
        counter = Counter(prefixes)
        most_common_count = counter.most_common(1)[0][1]
        concentration = most_common_count / len(content_frags)
        return self._clamp(concentration)

    def _score_cross_platform_contrast(
        self,
        fragments: list[Fragment],
        source_set: set[str],
    ) -> int:
        """Category distribution difference across platforms → 0-100."""
        by_source: dict[str, Counter] = {}
        for f in fragments:
            by_source.setdefault(f.source, Counter())[f.category.value] += 1

        sources = list(by_source.keys())
        if len(sources) < 2:
            return 0

        # Compare first two sources' category distributions
        s1, s2 = sources[0], sources[1]
        all_cats = set(by_source[s1]) | set(by_source[s2])
        total_s1 = sum(by_source[s1].values()) or 1
        total_s2 = sum(by_source[s2].values()) or 1

        total_diff = 0.0
        for cat in all_cats:
            ratio1 = by_source[s1].get(cat, 0) / total_s1
            ratio2 = by_source[s2].get(cat, 0) / total_s2
            total_diff += abs(ratio1 - ratio2)

        # Max possible diff = 2.0 (completely disjoint distributions)
        contrast = total_diff / 2.0
        return self._clamp(contrast)


# ─── Card data ───────────────────────────────────────────────────────────────


@dataclass
class FacetTag:
    """A single generative label derived from behavioral analysis."""

    title: str
    gloss: str
    facet: str
    confidence: float = 0.0


@dataclass
class CardData:
    """Complete data needed to render a persona card."""

    spectrum: SpectrumResult
    label: str = ""
    description: str = ""
    facet_tags: list[FacetTag] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)


def generate_card_data(
    fragments: list[Fragment],
    llm_client,
    prompts_dir: Path | None = None,
) -> CardData:
    """Compute spectrum + generate label/description/insights via LLM.

    Dimension scores are generated by the LLM based on fragment content,
    because fragments are extracted personality summaries (not raw messages)
    and statistical heuristics cannot meaningfully score them.
    """
    engine = SpectrumEngine()
    spectrum = engine.compute(fragments)

    card = CardData(spectrum=spectrum)
    if not spectrum.eligible:
        return card

    # Prepare prompt inputs
    metrics_text = "\n".join(f"- {k}: {v}" for k, v in spectrum.metrics.items())

    # Tell LLM which dimensions already have rule-based scores
    rule_dims = spectrum.dimensions
    rule_dims_text = "\n".join(f"- {k}: {v}" for k, v in rule_dims.items())

    # All 8 dimension names — LLM should fill in any missing ones
    all_dims = ["夜行性", "回复惯性", "表达锋利度", "社交温差", "情绪外显度", "内容杂食度", "品味独占欲", "跨平台反差"]
    missing_dims = [d for d in all_dims if d not in rule_dims]

    # Include all fragments grouped by source for context
    by_source: dict[str, list[str]] = {}
    for f in fragments:
        by_source.setdefault(f.source, []).append(f.content[:120])

    frag_lines = []
    for source, contents in by_source.items():
        frag_lines.append(f"\n### {source} ({len(contents)} fragments)")
        for c in contents[:30]:  # Cap at 30 per source to avoid token overflow
            frag_lines.append(f"- {c}")
    frag_text = "\n".join(frag_lines)

    # Load prompt template
    if prompts_dir is None:
        prompts_dir = Path(__file__).parent.parent / "prompts"
    template_path = prompts_dir / "spectrum_label.md"
    template = template_path.read_text(encoding="utf-8")

    prompt = template.format(
        metrics=metrics_text,
        fragments=frag_text,
        rule_dimensions=rule_dims_text,
        missing_dimensions=", ".join(missing_dims) if missing_dims else "（无，全部已有规则分数）",
    )

    # Call LLM
    raw = llm_client.complete(prompt)

    # Parse JSON response
    try:
        import json as json_mod

        json_str = raw
        if "```json" in raw:
            json_str = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            json_str = raw.split("```")[1].split("```")[0]
        data = json_mod.loads(json_str.strip())

        # LLM only fills dimensions that rules couldn't compute
        llm_dims = data.get("dimensions", {})
        if llm_dims:
            for k, v in llm_dims.items():
                if k in missing_dims and isinstance(v, (int, float)):
                    spectrum.dimensions[k] = max(0, min(100, int(v)))

        card.label = data.get("master_label", "") or data.get("label", "")
        card.description = data.get("master_gloss", "") or data.get("description", "")

        # Parse facet_tags (new generative label system)
        raw_tags = data.get("facet_tags", [])
        for tag in raw_tags[:8]:
            if isinstance(tag, dict) and tag.get("title"):
                card.facet_tags.append(FacetTag(
                    title=tag.get("title", ""),
                    gloss=tag.get("gloss", ""),
                    facet=tag.get("facet", ""),
                    confidence=float(tag.get("confidence", 0.0)),
                ))

        # Legacy fallback
        card.insights = data.get("insights", [])[:8]
    except (json_mod.JSONDecodeError, IndexError, KeyError):
        card.label = "数字旅人"
        card.description = "你的数据正在讲述你的故事"
        card.facet_tags = []
        card.insights = []

    return card


def generate_poster_data(
    fragments: list[Fragment],
    llm_client,
    prompts_dir: Path | None = None,
) -> dict:
    """Generate rich poster data — 6 chapters with micro-observations."""
    import json as json_mod

    if prompts_dir is None:
        prompts_dir = Path(__file__).parent.parent / "prompts"

    template_path = prompts_dir / "poster_generate.md"
    if not template_path.exists():
        return {}

    template = template_path.read_text(encoding="utf-8")

    by_source: dict[str, list[str]] = {}
    for f in fragments:
        by_source.setdefault(f.source, []).append(f.content[:150])

    frag_lines = []
    for source, contents in by_source.items():
        frag_lines.append(f"\n### {source} ({len(contents)} fragments)")
        for c in contents[:50]:
            frag_lines.append(f"- {c}")
    frag_text = "\n".join(frag_lines)

    metrics = {
        "fragment_count": len(fragments),
        "source_count": len(by_source),
        "sources": list(by_source.keys()),
    }
    metrics_text = "\n".join(f"- {k}: {v}" for k, v in metrics.items())

    prompt = template.format(fragments=frag_text, metrics=metrics_text)
    raw = llm_client.complete(prompt)

    try:
        json_str = raw
        if "```json" in raw:
            json_str = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            json_str = raw.split("```")[1].split("```")[0]
        data = json_mod.loads(json_str.strip())
        data["metrics"] = metrics
        return data
    except (json_mod.JSONDecodeError, IndexError, KeyError):
        return {"error": "Failed to parse poster data"}
