"""Tests for PersonaBench."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from engram.models import ChunkType, DataChunk
from engram.persona.bench import PersonaBench
from engram.persona.validator import PersonaValidator

# ─── helpers ────────────────────────────────────────────────────────────────


def make_chunk(content: str, source: str = "wechat") -> DataChunk:
    return DataChunk(
        source=source,
        type=ChunkType.CONVERSATION,
        timestamp=datetime(2024, 1, 1),
        content=content,
    )


CORE_MD = """\
## Personality Traits
- Intellectually honest, challenges incorrect claims

## Values
- Deep understanding over surface-level knowledge
"""

VALIDATE_RESPONSE = json.dumps(
    {
        "predicted_response": "Would challenge the claim",
        "actual_response": "That's not right",
        "alignment_score": 0.85,
        "reasoning": "Profile predicted confrontation; actual matches",
    }
)


def _make_mock_validator(score: float = 0.85) -> MagicMock:
    """Return a mock PersonaValidator with a fixed validate response."""
    validator = MagicMock(spec=PersonaValidator)
    validator.validate.return_value = {
        "score": score,
        "tests_run": 1,
        "details": [
            {
                "alignment_score": score,
                "reasoning": "Profile predicted confrontation; actual matches",
            }
        ],
    }
    return validator


# ─── evaluate ───────────────────────────────────────────────────────────────


class TestPersonaBenchEvaluate:
    def test_evaluate_returns_required_keys(self):
        bench = PersonaBench(_make_mock_validator())
        chunks = [make_chunk("some text")]
        result = bench.evaluate(CORE_MD, chunks)

        assert "overall_score" in result
        assert "tests_run" in result
        assert "details" in result
        assert "bench_version" in result

    def test_evaluate_score_between_0_and_1(self):
        bench = PersonaBench(_make_mock_validator(score=0.85))
        chunks = [make_chunk("some text")]
        result = bench.evaluate(CORE_MD, chunks)

        assert 0.0 <= result["overall_score"] <= 1.0

    def test_evaluate_bench_version_matches(self):
        bench = PersonaBench(_make_mock_validator())
        result = bench.evaluate(CORE_MD, [make_chunk("text")])
        assert result["bench_version"] == PersonaBench.VERSION

    def test_evaluate_respects_num_tests_limit(self):
        validator = _make_mock_validator()
        validator.validate.return_value = {
            "score": 0.8,
            "tests_run": 3,
            "details": [{"alignment_score": 0.8, "reasoning": "ok"}] * 3,
        }
        bench = PersonaBench(validator)
        chunks = [make_chunk(f"chunk {i}") for i in range(10)]

        bench.evaluate(CORE_MD, chunks, num_tests=3)

        # validator should receive exactly 3 chunks
        called_chunks = validator.validate.call_args[0][1]
        assert len(called_chunks) == 3

    def test_evaluate_with_live_mock_llm(self, mock_llm_response):
        """Integration-style: use mock_llm_response fixture like other persona tests."""
        mock_llm_response(VALIDATE_RESPONSE)

        from engram.llm.client import LLMClient

        client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
        validator = PersonaValidator(client, prompts_dir=None)
        bench = PersonaBench(validator)

        chunks = [make_chunk("That's not right")]
        result = bench.evaluate(CORE_MD, chunks)

        assert result["overall_score"] == pytest.approx(0.85)
        assert result["tests_run"] == 1


# ─── format_report ──────────────────────────────────────────────────────────


class TestPersonaBenchFormatReport:
    def test_format_report_contains_persona_bench(self):
        bench = PersonaBench(_make_mock_validator())
        result = bench.evaluate(CORE_MD, [make_chunk("text")])
        report = bench.format_report(result)
        assert "PersonaBench" in report

    def test_format_report_contains_percentage(self):
        bench = PersonaBench(_make_mock_validator(score=0.75))
        result = bench.evaluate(CORE_MD, [make_chunk("text")])
        report = bench.format_report(result)
        assert "%" in report

    def test_format_report_contains_score_value(self):
        bench = PersonaBench(_make_mock_validator(score=0.75))
        result = bench.evaluate(CORE_MD, [make_chunk("text")])
        report = bench.format_report(result)
        # 75.0% should appear somewhere
        assert "75.0" in report

    def test_format_report_contains_test_count(self):
        bench = PersonaBench(_make_mock_validator())
        result = bench.evaluate(CORE_MD, [make_chunk("text")])
        report = bench.format_report(result)
        assert str(result["tests_run"]) in report

    def test_format_report_contains_version(self):
        bench = PersonaBench(_make_mock_validator())
        result = bench.evaluate(CORE_MD, [make_chunk("text")])
        report = bench.format_report(result)
        assert PersonaBench.VERSION in report
