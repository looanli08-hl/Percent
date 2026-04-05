from __future__ import annotations

import json
from pathlib import Path

import pytest

from engram.models import ChunkType
from engram.parsers.youtube import YouTubeParser


@pytest.fixture()
def parser() -> YouTubeParser:
    return YouTubeParser()


@pytest.fixture()
def valid_history(tmp_path: Path) -> Path:
    data = [
        {
            "title": "Watched How Neural Networks Work",
            "titleUrl": "https://www.youtube.com/watch?v=abc123",
            "time": "2024-03-01T14:30:00Z",
            "subtitles": [{"name": "3Blue1Brown", "url": "https://www.youtube.com/channel/xyz"}],
        },
        {
            "title": "Watched Lo-fi Beats to Study",
            "titleUrl": "https://www.youtube.com/watch?v=def456",
            "time": "2024-03-02T09:00:00Z",
            "subtitles": [],
        },
        {
            # Entry with no subtitles key at all
            "title": "Watched Cooking Basics",
            "titleUrl": "https://www.youtube.com/watch?v=ghi789",
            "time": "2024-03-03T18:00:00Z",
        },
    ]
    path = tmp_path / "watch-history.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


def test_validate_valid_json_list(parser: YouTubeParser, valid_history: Path) -> None:
    assert parser.validate(valid_history) is True


def test_validate_rejects_non_json(parser: YouTubeParser, tmp_path: Path) -> None:
    f = tmp_path / "watch-history.html"
    f.write_text("<html>not json</html>", encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_rejects_json_object(parser: YouTubeParser, tmp_path: Path) -> None:
    f = tmp_path / "watch-history.json"
    f.write_text(json.dumps({"title": "test"}), encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_rejects_malformed_json(parser: YouTubeParser, tmp_path: Path) -> None:
    f = tmp_path / "watch-history.json"
    f.write_text("{broken", encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_rejects_directory(parser: YouTubeParser, tmp_path: Path) -> None:
    assert parser.validate(tmp_path) is False


# ---------------------------------------------------------------------------
# parse()
# ---------------------------------------------------------------------------


def test_parse_returns_all_entries(parser: YouTubeParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    assert len(chunks) == 3


def test_parse_chunk_source_and_type(parser: YouTubeParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    for chunk in chunks:
        assert chunk.source == "youtube"
        assert chunk.type == ChunkType.WATCH_HISTORY


def test_parse_strips_watched_prefix(parser: YouTubeParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    first = chunks[0]
    assert "Watched " not in first.content or first.content.startswith("Watched:")
    assert "How Neural Networks Work" in first.content


def test_parse_extracts_channel_from_subtitles(parser: YouTubeParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    first = chunks[0]
    assert first.metadata.get("channel") == "3Blue1Brown"
    assert "3Blue1Brown" in first.content


def test_parse_handles_missing_subtitles(parser: YouTubeParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    # Second entry has empty subtitles list
    second = chunks[1]
    assert "channel" not in second.metadata or second.metadata["channel"] == ""


def test_parse_url_in_metadata(parser: YouTubeParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    first = chunks[0]
    assert first.metadata.get("url") == "https://www.youtube.com/watch?v=abc123"


def test_parse_timestamp_iso8601(parser: YouTubeParser, valid_history: Path) -> None:
    chunks = parser.parse(valid_history)
    first = chunks[0]
    assert first.timestamp.year == 2024
    assert first.timestamp.month == 3
    assert first.timestamp.day == 1


# ---------------------------------------------------------------------------
# get_import_guide()
# ---------------------------------------------------------------------------


def test_import_guide_is_nonempty_string(parser: YouTubeParser) -> None:
    guide = parser.get_import_guide()
    assert isinstance(guide, str) and len(guide) > 0


def test_import_guide_mentions_takeout(parser: YouTubeParser) -> None:
    guide = parser.get_import_guide()
    assert "takeout" in guide.lower() or "Takeout" in guide
