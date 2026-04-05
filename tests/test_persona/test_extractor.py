from __future__ import annotations

import json
from datetime import datetime

import pytest

from engram.models import ChunkType, DataChunk, FindingCategory
from engram.persona.extractor import PersonaExtractor


def make_chunk(content: str, source: str = "wechat") -> DataChunk:
    return DataChunk(
        source=source,
        type=ChunkType.CONVERSATION,
        timestamp=datetime(2024, 1, 1),
        content=content,
    )


VALID_FINDINGS_JSON = json.dumps(
    [
        {
            "category": "trait",
            "content": "Values intellectual honesty over social harmony",
            "confidence": 0.85,
            "evidence": "consistently challenges incorrect claims even in group settings",
        },
        {
            "category": "preference",
            "content": "Prefers hard sci-fi with physics-based worldbuilding",
            "confidence": 0.9,
            "evidence": "recommends The Three-Body Problem and mentions liking realistic science",
        },
    ]
)


def test_extract_returns_findings(mock_llm_response, tmp_path):
    mock_llm_response(VALID_FINDINGS_JSON)
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    extractor = PersonaExtractor(client, prompts_dir=None)

    chunks = [make_chunk("I love The Three-Body Problem")]
    findings = extractor.extract(chunks)

    assert len(findings) == 2
    assert findings[0].category == FindingCategory.TRAIT
    assert findings[0].content == "Values intellectual honesty over social harmony"
    assert findings[0].confidence == pytest.approx(0.85)
    assert findings[0].source == "wechat"
    assert findings[1].category == FindingCategory.PREFERENCE


def test_extract_attaches_source_from_chunk(mock_llm_response, tmp_path):
    mock_llm_response(VALID_FINDINGS_JSON)
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    extractor = PersonaExtractor(client, prompts_dir=None)

    chunks = [make_chunk("some text", source="bilibili")]
    findings = extractor.extract(chunks)

    for f in findings:
        assert f.source == "bilibili"


def test_extract_handles_json_embedded_in_text(mock_llm_response):
    """LLM sometimes wraps JSON in prose — extractor should still parse it."""
    response_with_text = "Here are my findings:\n\n" + VALID_FINDINGS_JSON + "\n\nThat's all."
    mock_llm_response(response_with_text)
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    extractor = PersonaExtractor(client, prompts_dir=None)

    findings = extractor.extract([make_chunk("text")])
    assert len(findings) == 2


def test_extract_handles_invalid_json_gracefully(mock_llm_response):
    """Invalid JSON should return empty list without raising."""
    mock_llm_response("This is not JSON at all!")
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    extractor = PersonaExtractor(client, prompts_dir=None)

    findings = extractor.extract([make_chunk("text")])
    assert findings == []


def test_extract_batches_chunks(mock_llm_response):
    """More than batch_size chunks should trigger multiple LLM calls."""
    original_findings = json.dumps(
        [
            {
                "category": "trait",
                "content": "Curious",
                "confidence": 0.7,
                "evidence": "reads widely",
            },
        ]
    )

    call_log = []

    def fake_completion(**kwargs):
        call_log.append(1)

        class FakeChoice:
            class FakeMessage:
                content = original_findings

            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]

        return FakeResponse()

    import unittest.mock

    with unittest.mock.patch("litellm.completion", fake_completion):
        from engram.llm.client import LLMClient

        client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
        extractor = PersonaExtractor(client, prompts_dir=None, batch_size=3)
        chunks = [make_chunk(f"message {i}") for i in range(7)]
        findings = extractor.extract(chunks)

    # 7 chunks with batch_size=3 → 3 batches
    assert len(call_log) == 3
    assert len(findings) == 3  # 1 finding per batch × 3 batches


def test_extract_empty_chunks_returns_empty():
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    extractor = PersonaExtractor(client, prompts_dir=None)
    assert extractor.extract([]) == []
