from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ChunkType(StrEnum):
    CONVERSATION = "conversation"
    WATCH_HISTORY = "watch_history"
    LISTEN_HISTORY = "listen_history"
    POST = "post"


class DataChunk(BaseModel):
    source: str
    type: ChunkType
    timestamp: datetime
    content: str
    metadata: dict = Field(default_factory=dict)


class FindingCategory(StrEnum):
    TRAIT = "trait"
    OPINION = "opinion"
    PREFERENCE = "preference"
    RELATIONSHIP = "relationship"
    HABIT = "habit"


class Finding(BaseModel):
    category: FindingCategory
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    evidence: str


class Fragment(BaseModel):
    id: int | None = None
    category: FindingCategory
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    embedding: list[float] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
