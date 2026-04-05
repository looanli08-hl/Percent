from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from engram.models import ChunkType
from engram.parsers.wechat import WeChatParser


@pytest.fixture()
def parser() -> WeChatParser:
    return WeChatParser()


# ---------------------------------------------------------------------------
# Helpers to create test files
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict]) -> Path:
    """Write a PyWxDump-style CSV file."""
    fieldnames = ["StrTalker", "StrContent", "CreateTime", "Type"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_json(path: Path, data: list[dict]) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


def test_validate_valid_csv(parser: WeChatParser, tmp_path: Path) -> None:
    f = _write_csv(
        tmp_path / "chat.csv",
        [{"StrTalker": "Alice", "StrContent": "Hi", "CreateTime": "1700000000", "Type": "1"}],
    )
    assert parser.validate(f) is True


def test_validate_csv_missing_required_column(parser: WeChatParser, tmp_path: Path) -> None:
    f = tmp_path / "chat.csv"
    # Missing "Type" column
    with f.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["StrTalker", "StrContent", "CreateTime"])
        writer.writeheader()
    assert parser.validate(f) is False


def test_validate_valid_json(parser: WeChatParser, tmp_path: Path) -> None:
    f = _write_json(
        tmp_path / "chat.json",
        [{"talker": "Bob", "content": "Hey", "create_time": "1700000000", "type": "1"}],
    )
    assert parser.validate(f) is True


def test_validate_json_non_list(parser: WeChatParser, tmp_path: Path) -> None:
    f = tmp_path / "chat.json"
    f.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_unsupported_extension(parser: WeChatParser, tmp_path: Path) -> None:
    f = tmp_path / "chat.txt"
    f.write_text("data", encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_directory_with_csv(parser: WeChatParser, tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "chat.csv",
        [{"StrTalker": "Alice", "StrContent": "Hi", "CreateTime": "1700000000", "Type": "1"}],
    )
    assert parser.validate(tmp_path) is True


def test_validate_empty_directory(parser: WeChatParser, tmp_path: Path) -> None:
    assert parser.validate(tmp_path) is False


# ---------------------------------------------------------------------------
# parse() — CSV
# ---------------------------------------------------------------------------


def test_parse_csv_text_messages_only(parser: WeChatParser, tmp_path: Path) -> None:
    rows = [
        {"StrTalker": "Alice", "StrContent": "Hello", "CreateTime": "1700000000", "Type": "1"},
        {"StrTalker": "Alice", "StrContent": "[image]", "CreateTime": "1700000100", "Type": "3"},
        {"StrTalker": "Alice", "StrContent": "World", "CreateTime": "1700000200", "Type": "1"},
    ]
    f = _write_csv(tmp_path / "chat.csv", rows)
    chunks = parser.parse(f)
    combined = "\n".join(c.content for c in chunks)
    assert "[image]" not in combined
    assert "Hello" in combined
    assert "World" in combined


def test_parse_csv_chunks_source_and_type(parser: WeChatParser, tmp_path: Path) -> None:
    rows = [
        {"StrTalker": "Alice", "StrContent": "Hi", "CreateTime": "1700000000", "Type": "1"},
    ]
    f = _write_csv(tmp_path / "chat.csv", rows)
    chunks = parser.parse(f)
    assert len(chunks) == 1
    assert chunks[0].source == "wechat"
    assert chunks[0].type == ChunkType.CONVERSATION


def test_parse_csv_metadata_talker(parser: WeChatParser, tmp_path: Path) -> None:
    rows = [
        {"StrTalker": "Alice", "StrContent": "Hi", "CreateTime": "1700000000", "Type": "1"},
    ]
    f = _write_csv(tmp_path / "chat.csv", rows)
    chunks = parser.parse(f)
    assert chunks[0].metadata["talker"] == "Alice"


# ---------------------------------------------------------------------------
# parse() — conversation window grouping
# ---------------------------------------------------------------------------


def test_parse_groups_close_messages_into_one_chunk(
    parser: WeChatParser, tmp_path: Path
) -> None:
    rows = [
        {"StrTalker": "Alice", "StrContent": "Hello", "CreateTime": "1700000000", "Type": "1"},
        {"StrTalker": "Alice", "StrContent": "How are you?", "CreateTime": "1700000600", "Type": "1"},
        # 10 minutes apart — same window
    ]
    f = _write_csv(tmp_path / "chat.csv", rows)
    chunks = parser.parse(f)
    assert len(chunks) == 1
    assert chunks[0].metadata["message_count"] == 2


def test_parse_splits_on_30_minute_gap(parser: WeChatParser, tmp_path: Path) -> None:
    base = 1700000000
    gap = 31 * 60  # 31 minutes
    rows = [
        {"StrTalker": "Alice", "StrContent": "Morning", "CreateTime": str(base), "Type": "1"},
        {"StrTalker": "Alice", "StrContent": "Evening", "CreateTime": str(base + gap), "Type": "1"},
    ]
    f = _write_csv(tmp_path / "chat.csv", rows)
    chunks = parser.parse(f)
    assert len(chunks) == 2


def test_parse_separate_talkers_produce_separate_chunks(
    parser: WeChatParser, tmp_path: Path
) -> None:
    base = 1700000000
    rows = [
        {"StrTalker": "Alice", "StrContent": "Hi from Alice", "CreateTime": str(base), "Type": "1"},
        {"StrTalker": "Bob", "StrContent": "Hi from Bob", "CreateTime": str(base + 60), "Type": "1"},
    ]
    f = _write_csv(tmp_path / "chat.csv", rows)
    chunks = parser.parse(f)
    assert len(chunks) == 2
    talkers = {c.metadata["talker"] for c in chunks}
    assert talkers == {"Alice", "Bob"}


# ---------------------------------------------------------------------------
# parse() — JSON format
# ---------------------------------------------------------------------------


def test_parse_json_format(parser: WeChatParser, tmp_path: Path) -> None:
    data = [
        {"talker": "Charlie", "content": "JSON Hello", "create_time": "1700000000", "type": "1"},
        {"talker": "Charlie", "content": "JSON World", "create_time": "1700000300", "type": "1"},
    ]
    f = _write_json(tmp_path / "chat.json", data)
    chunks = parser.parse(f)
    assert len(chunks) == 1
    assert "JSON Hello" in chunks[0].content
    assert "JSON World" in chunks[0].content


def test_parse_json_skips_non_text_messages(parser: WeChatParser, tmp_path: Path) -> None:
    data = [
        {"talker": "Dave", "content": "text msg", "create_time": "1700000000", "type": "1"},
        {"talker": "Dave", "content": "[sticker]", "create_time": "1700000060", "type": "43"},
    ]
    f = _write_json(tmp_path / "chat.json", data)
    chunks = parser.parse(f)
    combined = "\n".join(c.content for c in chunks)
    assert "[sticker]" not in combined
    assert "text msg" in combined


# ---------------------------------------------------------------------------
# parse() — directory of files
# ---------------------------------------------------------------------------


def test_parse_directory_merges_multiple_files(
    parser: WeChatParser, tmp_path: Path
) -> None:
    _write_csv(
        tmp_path / "chat_alice.csv",
        [{"StrTalker": "Alice", "StrContent": "From Alice", "CreateTime": "1700000000", "Type": "1"}],
    )
    _write_csv(
        tmp_path / "chat_bob.csv",
        [{"StrTalker": "Bob", "StrContent": "From Bob", "CreateTime": "1700000060", "Type": "1"}],
    )
    chunks = parser.parse(tmp_path)
    talkers = {c.metadata["talker"] for c in chunks}
    assert "Alice" in talkers
    assert "Bob" in talkers


# ---------------------------------------------------------------------------
# get_import_guide()
# ---------------------------------------------------------------------------


def test_import_guide_is_nonempty_string(parser: WeChatParser) -> None:
    guide = parser.get_import_guide()
    assert isinstance(guide, str) and len(guide) > 0


def test_import_guide_mentions_pywxdump(parser: WeChatParser) -> None:
    guide = parser.get_import_guide()
    assert "PyWxDump" in guide or "pywxdump" in guide.lower()
