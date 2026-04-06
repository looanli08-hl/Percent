from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from percent.models import ChunkType, DataChunk

# ─── helpers ────────────────────────────────────────────────────────────────


def make_chunk(content: str, source: str = "wechat") -> DataChunk:
    return DataChunk(
        source=source,
        type=ChunkType.CONVERSATION,
        timestamp=datetime(2024, 1, 1),
        content=content,
    )


EXTRACT_RESPONSE = json.dumps(
    [
        {
            "category": "trait",
            "content": "Values intellectual honesty",
            "confidence": 0.85,
            "evidence": "challenges incorrect claims",
        },
    ]
)

SYNTHESIZE_RESPONSE = """\
## Personality Traits
- Values intellectual honesty over social harmony

## Values
- Prioritizes deep understanding

## Thinking Patterns
- Systems thinker

## Core Preferences
- Hard sci-fi

## Social Style
- Low tolerance for small talk

## Expression Characteristics
- Dense, precise prose
"""

VALIDATE_RESPONSE = json.dumps(
    {
        "predicted_response": "Would challenge the incorrect claim",
        "actual_response": "That's not right, here's why...",
        "alignment_score": 0.82,
        "reasoning": "Profile predicted confrontation; actual response matches",
    }
)


def make_dummy_embedder():
    """Return a mock SentenceTransformer that yields fixed-size embeddings."""
    embedder = MagicMock()
    embedder.encode.return_value = np.ones(384, dtype=np.float32)
    return embedder


# ─── validator tests ─────────────────────────────────────────────────────────


class TestPersonaValidator:
    def test_validate_returns_score_and_details(self, mock_llm_response):
        mock_llm_response(VALIDATE_RESPONSE)
        from percent.llm.client import LLMClient
        from percent.persona.validator import PersonaValidator

        client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
        validator = PersonaValidator(client, prompts_dir=None)

        test_chunks = [make_chunk("That's not right, here's why...")]
        result = validator.validate(
            core_md=SYNTHESIZE_RESPONSE,
            test_chunks=test_chunks,
        )

        assert "score" in result
        assert "tests_run" in result
        assert "details" in result
        assert result["tests_run"] == 1
        assert result["score"] == pytest.approx(0.82)

    def test_validate_averages_multiple_chunks(self):
        """Multiple test chunks → averaged score."""
        call_n = 0
        scores = [0.8, 0.6]

        def fake_completion(**kwargs):
            nonlocal call_n
            resp_json = json.dumps(
                {
                    "predicted_response": "x",
                    "actual_response": "y",
                    "alignment_score": scores[call_n],
                    "reasoning": "ok",
                }
            )
            call_n += 1

            class FakeChoice:
                class FakeMessage:
                    content = resp_json

                message = FakeMessage()

            class FakeResponse:
                choices = [FakeChoice()]

            return FakeResponse()

        with patch("litellm.completion", fake_completion):
            from percent.llm.client import LLMClient
            from percent.persona.validator import PersonaValidator

            client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
            validator = PersonaValidator(client, prompts_dir=None)
            chunks = [make_chunk("msg1"), make_chunk("msg2")]
            result = validator.validate(SYNTHESIZE_RESPONSE, chunks)

        assert result["tests_run"] == 2
        assert result["score"] == pytest.approx(0.7)
        assert len(result["details"]) == 2

    def test_validate_handles_invalid_json(self, mock_llm_response):
        mock_llm_response("not json")
        from percent.llm.client import LLMClient
        from percent.persona.validator import PersonaValidator

        client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
        validator = PersonaValidator(client, prompts_dir=None)

        result = validator.validate(SYNTHESIZE_RESPONSE, [make_chunk("text")])
        assert result["tests_run"] == 1
        # Bad parse → score defaults to 0.0
        assert result["score"] == pytest.approx(0.0)

    def test_validate_empty_chunks_returns_zero(self):
        from percent.llm.client import LLMClient
        from percent.persona.validator import PersonaValidator

        client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
        validator = PersonaValidator(client, prompts_dir=None)
        result = validator.validate(SYNTHESIZE_RESPONSE, [])
        assert result["score"] == 0.0
        assert result["tests_run"] == 0


# ─── engine tests ─────────────────────────────────────────────────────────────


class TestPersonaEngine:
    """
    Every test patches SentenceTransformer at the engine module level so no
    model download occurs.
    """

    @pytest.fixture(autouse=True)
    def patch_embedder(self):
        dummy = make_dummy_embedder()
        with patch("percent.persona.engine.SentenceTransformer", return_value=dummy):
            yield dummy

    def _make_sequential_llm(self, responses: list[str]):
        """Return a fake litellm.completion that cycles through *responses*."""
        call_n = 0

        def fake_completion(**kwargs):
            nonlocal call_n
            content = responses[call_n % len(responses)]
            call_n += 1

            class FakeChoice:
                class FakeMessage:
                    pass

                message = FakeMessage()

            FakeChoice.message.content = content

            class FakeResponse:
                choices = [FakeChoice()]

            return FakeResponse()

        return fake_completion

    def test_run_returns_core_md(self, tmp_percent_dir):
        from percent.llm.client import LLMClient
        from percent.persona.engine import PersonaEngine

        responses = [EXTRACT_RESPONSE, SYNTHESIZE_RESPONSE]
        with patch("litellm.completion", self._make_sequential_llm(responses)):
            client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
            engine = PersonaEngine(
                client,
                percent_dir=tmp_percent_dir,
                prompts_dir=None,
            )
            chunks = [make_chunk("I love The Three-Body Problem")]
            result = engine.run(chunks, validate=False)

        assert "## Personality Traits" in result

    def test_run_stores_fragments(self, tmp_percent_dir):
        from percent.llm.client import LLMClient
        from percent.persona.engine import PersonaEngine

        responses = [EXTRACT_RESPONSE, SYNTHESIZE_RESPONSE]
        with patch("litellm.completion", self._make_sequential_llm(responses)):
            client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
            engine = PersonaEngine(client, percent_dir=tmp_percent_dir, prompts_dir=None)
            chunks = [make_chunk("some text")]
            engine.run(chunks, validate=False)

        stats = engine.stats()
        assert stats["total"] == 1  # one finding → one fragment

    def test_run_with_validate_calls_validator(self, tmp_percent_dir):
        from percent.llm.client import LLMClient
        from percent.persona.engine import PersonaEngine

        # extract → synthesize → validate
        responses = [EXTRACT_RESPONSE, SYNTHESIZE_RESPONSE, VALIDATE_RESPONSE]
        with patch("litellm.completion", self._make_sequential_llm(responses)):
            client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
            engine = PersonaEngine(client, percent_dir=tmp_percent_dir, prompts_dir=None)
            chunks = [make_chunk("some text")]
            result = engine.run(chunks, validate=True)

        assert "## Personality Traits" in result

    def test_run_saves_core_md_to_disk(self, tmp_percent_dir):
        from percent.llm.client import LLMClient
        from percent.persona.engine import PersonaEngine

        responses = [EXTRACT_RESPONSE, SYNTHESIZE_RESPONSE]
        with patch("litellm.completion", self._make_sequential_llm(responses)):
            client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
            engine = PersonaEngine(client, percent_dir=tmp_percent_dir, prompts_dir=None)
            engine.run([make_chunk("text")], validate=False)

        core_path = tmp_percent_dir / "core.md"
        assert core_path.exists()
        assert "## Personality Traits" in core_path.read_text()

    def test_rebuild_core_from_stored_fragments(self, tmp_percent_dir):
        from percent.llm.client import LLMClient
        from percent.persona.engine import PersonaEngine

        # First run: extract + synthesize
        responses_run = [EXTRACT_RESPONSE, SYNTHESIZE_RESPONSE]
        # Rebuild: another synthesize call
        responses_rebuild = [SYNTHESIZE_RESPONSE]
        all_responses = responses_run + responses_rebuild

        with patch("litellm.completion", self._make_sequential_llm(all_responses)):
            client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
            engine = PersonaEngine(client, percent_dir=tmp_percent_dir, prompts_dir=None)
            engine.run([make_chunk("text")], validate=False)
            rebuilt = engine.rebuild_core()

        assert "## Personality Traits" in rebuilt

    def test_embed_query_returns_list(self, tmp_percent_dir):
        from percent.llm.client import LLMClient
        from percent.persona.engine import PersonaEngine

        client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
        engine = PersonaEngine(client, percent_dir=tmp_percent_dir, prompts_dir=None)
        embedding = engine.embed_query("How does this person react to conflict?")

        assert isinstance(embedding, list)
        assert len(embedding) == 384

    def test_stats_delegates_to_store(self, tmp_percent_dir):
        from percent.llm.client import LLMClient
        from percent.persona.engine import PersonaEngine

        client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
        engine = PersonaEngine(client, percent_dir=tmp_percent_dir, prompts_dir=None)
        stats = engine.stats()

        assert "total" in stats
        assert stats["total"] == 0
