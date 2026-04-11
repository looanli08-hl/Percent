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
        {"note_id": "1", "title": "", "desc": ""},
        {"note_id": "2", "title": "Real Note", "desc": "Content"},
    ]
    f = tmp_path / "xhs.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    chunks = parser.parse(f)
    assert len(chunks) == 1


def test_import_guide_nonempty(parser: XiaohongshuParser) -> None:
    guide = parser.get_import_guide()
    assert isinstance(guide, str) and len(guide) > 0
