from __future__ import annotations

import json
from pathlib import Path

import pytest

from percent.models import ChunkType
from percent.parsers.bilibili import BilibiliParser


@pytest.fixture()
def parser() -> BilibiliParser:
    return BilibiliParser()


@pytest.fixture()
def valid_history(tmp_path: Path) -> Path:
    data = [
        {
            "title": "Linear Algebra Full Course",
            "tag_name": "Education",
            "view_at": 1700000000,
            "author_name": "3Blue1Brown",
            "duration": 1080,
        },
        {
            "title": "已失效视频",
            "tag_name": "",
            "view_at": 1700001000,
            "author_name": "",
            "duration": 0,
        },
        {
            "title": "Lo-fi Hip Hop Mix",
            "tag_name": "Music",
            "view_at": 1700002000,
            "author_name": "ChilledCow",
            "duration": 3600,
        },
    ]
    path = tmp_path / "history.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


def test_validate_valid_json_list(parser: BilibiliParser, valid_history: Path) -> None:
    assert parser.validate(valid_history) is True


def test_validate_rejects_non_json(parser: BilibiliParser, tmp_path: Path) -> None:
    f = tmp_path / "history.txt"
    f.write_text("not json", encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_rejects_json_object(parser: BilibiliParser, tmp_path: Path) -> None:
    f = tmp_path / "history.json"
    f.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_rejects_malformed_json(parser: BilibiliParser, tmp_path: Path) -> None:
    f = tmp_path / "history.json"
    f.write_text("{bad json", encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_rejects_directory(parser: BilibiliParser, tmp_path: Path) -> None:
    assert parser.validate(tmp_path) is False


# ---------------------------------------------------------------------------
# parse()
# ---------------------------------------------------------------------------


def test_parse_skips_invalid_videos(parser: BilibiliParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    titles = [c.content for c in chunks]
    assert all("已失效视频" not in t for t in titles)


def test_parse_returns_correct_count(parser: BilibiliParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    # 3 entries but 1 is invalid → 2 chunks
    assert len(chunks) == 2


def test_parse_chunk_source_and_type(parser: BilibiliParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    for chunk in chunks:
        assert chunk.source == "bilibili"
        assert chunk.type == ChunkType.WATCH_HISTORY


def test_parse_chunk_content_includes_title_and_author(
    parser: BilibiliParser, valid_history: Path
) -> None:
    chunks = parser.parse(valid_history)
    first = chunks[0]
    assert "Linear Algebra Full Course" in first.content
    assert "3Blue1Brown" in first.content


def test_parse_chunk_metadata(parser: BilibiliParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    first = chunks[0]
    assert first.metadata["author"] == "3Blue1Brown"
    assert first.metadata["category"] == "Education"
    assert first.metadata["duration_seconds"] == 1080


def test_parse_timestamp_from_unix(parser: BilibiliParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    first = chunks[0]
    assert first.timestamp.year == 2023  # 1700000000 → Nov 2023


# ---------------------------------------------------------------------------
# get_import_guide()
# ---------------------------------------------------------------------------


def test_import_guide_is_nonempty_string(parser: BilibiliParser) -> None:
    guide = parser.get_import_guide()
    assert isinstance(guide, str) and len(guide) > 0


def test_import_guide_mentions_bilibili(parser: BilibiliParser) -> None:
    guide = parser.get_import_guide()
    assert "bilibili" in guide.lower() or "Bilibili" in guide
