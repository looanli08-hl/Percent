from datetime import datetime

from engram.models import (
    ChunkType,
    DataChunk,
    Finding,
    FindingCategory,
    Fragment,
)


def test_data_chunk_creation():
    chunk = DataChunk(
        source="bilibili",
        type=ChunkType.WATCH_HISTORY,
        timestamp=datetime(2026, 1, 15, 22, 30),
        content="Watched: 3Blue1Brown - Linear Algebra",
        metadata={"category": "education", "duration_minutes": 18},
    )
    assert chunk.source == "bilibili"
    assert chunk.type == ChunkType.WATCH_HISTORY
    assert chunk.metadata["duration_minutes"] == 18


def test_finding_confidence_bounds():
    finding = Finding(
        category=FindingCategory.PREFERENCE,
        content="Prefers hard sci-fi over soft sci-fi",
        confidence=0.85,
        source="wechat",
        evidence="Multiple conversations expressing preference for Liu Cixin",
    )
    assert 0 <= finding.confidence <= 1


def test_fragment_default_values():
    fragment = Fragment(
        category=FindingCategory.TRAIT,
        content="Tends to analyze problems from first principles",
        confidence=0.9,
        source="wechat",
    )
    assert fragment.id is None
    assert fragment.embedding == []
    assert fragment.created_at is not None
