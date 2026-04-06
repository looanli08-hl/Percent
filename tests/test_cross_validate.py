"""Tests for cross-source validation and deep analysis."""

from datetime import datetime
from unittest.mock import MagicMock

import numpy as np

from percent.models import Finding, FindingCategory, Fragment
from percent.persona.cross_validate import DeepAnalyzer, cross_validate_fragments


def _make_fragment(
    content: str,
    source: str,
    confidence: float = 0.7,
    embedding: list[float] | None = None,
    fid: int | None = None,
) -> Fragment:
    if embedding is None:
        embedding = np.random.randn(8).tolist()
    return Fragment(
        id=fid,
        category=FindingCategory.TRAIT,
        content=content,
        confidence=confidence,
        source=source,
        embedding=embedding,
        created_at=datetime.now(),
    )


class TestCrossValidateFragments:
    def test_single_source_no_change(self):
        frags = [
            _make_fragment("likes football", "wechat", 0.7),
            _make_fragment("plays games", "wechat", 0.6),
        ]
        result = cross_validate_fragments(frags)
        # Single source — no cross-validation possible
        assert [f.confidence for f in result] == [0.7, 0.6]

    def test_corroborated_findings_boosted(self):
        # Same embedding = high similarity = cross-source corroboration
        shared_emb = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        frags = [
            _make_fragment("likes football", "wechat", 0.7, embedding=shared_emb, fid=1),
            _make_fragment("enjoys football", "bilibili", 0.6, embedding=shared_emb, fid=2),
        ]
        result = cross_validate_fragments(frags)
        # Both should be boosted
        assert result[0].confidence > 0.7
        assert result[1].confidence > 0.6

    def test_uncorroborated_findings_penalized(self):
        # Very different embeddings = no corroboration
        frags = [
            _make_fragment("likes football", "wechat", 0.7,
                          embedding=[1, 0, 0, 0, 0, 0, 0, 0], fid=1),
            _make_fragment("hates cooking", "bilibili", 0.7,
                          embedding=[0, 0, 0, 0, 0, 0, 0, 1], fid=2),
        ]
        result = cross_validate_fragments(frags)
        # Both uncorroborated across sources — slight penalty
        assert result[0].confidence < 0.7
        assert result[1].confidence < 0.7

    def test_empty_list(self):
        assert cross_validate_fragments([]) == []

    def test_single_fragment(self):
        frags = [_make_fragment("solo", "wechat")]
        result = cross_validate_fragments(frags)
        assert len(result) == 1


class TestDeepAnalyzer:
    def test_analyze_returns_findings(self):
        mock_client = MagicMock()
        mock_client.complete.return_value = """[
            {
                "type": "pattern",
                "content": "表面上的直接和偏好节省的行为共同指向务实主义",
                "confidence": 0.85,
                "related_findings": [1, 3],
                "reasoning": "多个行为共同指向一个核心特质"
            }
        ]"""

        analyzer = DeepAnalyzer(mock_client)
        findings = [
            Finding(
                category=FindingCategory.TRAIT,
                content="说话直接",
                confidence=0.8,
                source="wechat",
                evidence="...",
            ),
        ]
        result = analyzer.analyze(findings)
        assert len(result) == 1
        assert result[0].source == "deep_analysis"
        assert result[0].confidence == 0.85

    def test_analyze_empty_findings(self):
        mock_client = MagicMock()
        analyzer = DeepAnalyzer(mock_client)
        result = analyzer.analyze([])
        assert result == []

    def test_analyze_handles_invalid_json(self):
        mock_client = MagicMock()
        mock_client.complete.return_value = "not json at all"
        analyzer = DeepAnalyzer(mock_client)
        findings = [
            Finding(
                category=FindingCategory.TRAIT,
                content="test",
                confidence=0.5,
                source="test",
                evidence="test",
            ),
        ]
        result = analyzer.analyze(findings)
        assert result == []
