"""Tests for the Telegram chat history export parser."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from percent.models import ChunkType
from percent.parsers.telegram import TelegramParser


@pytest.fixture()
def parser() -> TelegramParser:
    return TelegramParser(my_name="Me")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_export(path: Path, data: dict) -> Path:
    """Write a Telegram result.json export file."""
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _make_export(
    messages: list[dict],
    chat_name: str = "Test Chat",
    chat_type: str = "personal_chat",
    personal_info: dict | None = None,
) -> dict:
    data: dict = {
        "name": chat_name,
        "type": chat_type,
        "messages": messages,
    }
    if personal_info:
        data["personal_information"] = personal_info
    return data


def _make_message(
    msg_id: int,
    from_name: str,
    from_id: str,
    text: str | list,
    date: str = "2026-01-15T10:30:00",
    msg_type: str = "message",
) -> dict:
    return {
        "id": msg_id,
        "type": msg_type,
        "date": date,
        "from": from_name,
        "from_id": from_id,
        "text": text,
    }


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


def test_validate_valid_result_json(parser: TelegramParser, tmp_path: Path) -> None:
    f = _write_export(
        tmp_path / "result.json",
        _make_export([_make_message(1, "John", "user1", "Hello")]),
    )
    assert parser.validate(f) is True


def test_validate_non_telegram_json(parser: TelegramParser, tmp_path: Path) -> None:
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"key": "value", "items": [1, 2, 3]}), encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_non_json_file(parser: TelegramParser, tmp_path: Path) -> None:
    f = tmp_path / "chat.txt"
    f.write_text("not json", encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_directory_with_result_json(parser: TelegramParser, tmp_path: Path) -> None:
    _write_export(
        tmp_path / "result.json",
        _make_export([_make_message(1, "John", "user1", "Hello")]),
    )
    assert parser.validate(tmp_path) is True


def test_validate_directory_with_subdir_result_json(parser: TelegramParser, tmp_path: Path) -> None:
    subdir = tmp_path / "chat_john"
    subdir.mkdir()
    _write_export(
        subdir / "result.json",
        _make_export([_make_message(1, "John", "user1", "Hello")]),
    )
    assert parser.validate(tmp_path) is True


def test_validate_empty_directory(parser: TelegramParser, tmp_path: Path) -> None:
    assert parser.validate(tmp_path) is False


# ---------------------------------------------------------------------------
# parse() — basic parsing
# ---------------------------------------------------------------------------


def test_parse_basic_messages(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "John", "user1", "Hey!", date="2026-01-15T10:30:00"),
            _make_message(2, "Me", "user2", "Hi there!", date="2026-01-15T10:31:00"),
        ]),
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content
    assert "[John]" in chunks[0].content
    assert "Hi there!" in chunks[0].content


def test_parse_chunk_source_and_type(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Me", "user2", "Hello", date="2026-01-15T10:30:00"),
        ]),
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert chunks[0].source == "telegram"
    assert chunks[0].type == ChunkType.CONVERSATION


def test_parse_metadata_fields(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export(
            [
                _make_message(1, "John", "user1", "Hello", date="2026-01-15T10:30:00"),
                _make_message(2, "Me", "user2", "Hi", date="2026-01-15T10:31:00"),
                _make_message(3, "John", "user1", "How are you?", date="2026-01-15T10:32:00"),
            ],
            chat_name="John Chat",
        ),
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    meta = chunks[0].metadata
    assert meta["message_count"] == 3
    assert meta["self_message_count"] == 1
    assert meta["talker"] == "John Chat"


# ---------------------------------------------------------------------------
# parse() — text field handling
# ---------------------------------------------------------------------------


def test_parse_text_as_string(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Me", "user2", "Plain text message"),
        ]),
    )
    chunks = p.parse(f)
    assert "Plain text message" in chunks[0].content


def test_parse_text_as_list_of_strings(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Me", "user2", ["Hello ", "world"]),
        ]),
    )
    chunks = p.parse(f)
    assert "Hello world" in chunks[0].content


def test_parse_text_as_list_with_objects(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    formatted_text = [
        {"type": "text_link", "text": "Click here", "href": "https://example.com"},
        " for more info",
    ]
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Me", "user2", formatted_text),
        ]),
    )
    chunks = p.parse(f)
    assert "Click here" in chunks[0].content
    assert "for more info" in chunks[0].content


def test_skips_messages_with_empty_text(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Me", "user2", ""),
            _make_message(2, "Me", "user2", "Real message"),
        ]),
    )
    chunks = p.parse(f)
    combined = "\n".join(c.content for c in chunks)
    assert "Real message" in combined


# ---------------------------------------------------------------------------
# parse() — service message skipping
# ---------------------------------------------------------------------------


def test_skips_service_messages(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Me", "user2", "Hello", msg_type="message"),
            _make_message(2, "", "", "John joined the group", msg_type="service"),
            _make_message(3, "John", "user1", "Hi", msg_type="message"),
        ]),
    )
    chunks = p.parse(f)
    # Service message should not appear in content
    combined = "\n".join(c.content for c in chunks)
    assert "joined the group" not in combined


# ---------------------------------------------------------------------------
# parse() — conversation windowing
# ---------------------------------------------------------------------------


def test_groups_close_messages_into_one_chunk(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "John", "user1", "Hi", date="2026-01-15T10:00:00"),
            _make_message(2, "Me", "user2", "Hey", date="2026-01-15T10:10:00"),
            _make_message(3, "John", "user1", "What's up?", date="2026-01-15T10:20:00"),
        ]),
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert chunks[0].metadata["message_count"] == 3


def test_splits_on_30_minute_gap(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Me", "user2", "Morning", date="2026-01-15T10:00:00"),
            _make_message(2, "John", "user1", "Evening", date="2026-01-15T10:31:00"),
            _make_message(3, "Me", "user2", "Reply", date="2026-01-15T10:32:00"),
        ]),
    )
    chunks = p.parse(f)
    assert len(chunks) == 2


def test_window_without_self_excluded(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            # First window: only John speaks
            _make_message(1, "John", "user1", "Hello?", date="2026-01-15T10:00:00"),
            _make_message(2, "John", "user1", "Anyone?", date="2026-01-15T10:01:00"),
            # 31-min gap, second window: Me speaks
            _make_message(3, "Me", "user2", "Sorry, was away", date="2026-01-15T10:32:00"),
            _make_message(4, "John", "user1", "No worries", date="2026-01-15T10:33:00"),
        ]),
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content


# ---------------------------------------------------------------------------
# parse() — self identification
# ---------------------------------------------------------------------------


def test_identify_self_by_name(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Alice")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Bob", "user1", "Hi Alice", date="2026-01-15T10:30:00"),
            _make_message(2, "Alice", "user2", "Hey Bob!", date="2026-01-15T10:31:00"),
        ]),
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content
    assert "Hey Bob!" in chunks[0].content


def test_identify_self_by_user_id(tmp_path: Path) -> None:
    p = TelegramParser(my_user_id="user999")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Bob", "user1", "Hi", date="2026-01-15T10:30:00"),
            _make_message(2, "Carol", "user999", "Hello Bob", date="2026-01-15T10:31:00"),
        ]),
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content
    assert "Hello Bob" in chunks[0].content


def test_identify_self_from_personal_information(tmp_path: Path) -> None:
    """Self should be identified via personal_information.user_id in the export."""
    p = TelegramParser()  # no explicit name/id
    export = _make_export(
        messages=[
            _make_message(1, "John", "user111", "Hey", date="2026-01-15T10:30:00"),
            _make_message(2, "Carol", "user222", "Hi John", date="2026-01-15T10:31:00"),
        ],
        personal_info={"user_id": 222, "first_name": "Carol"},
    )
    f = _write_export(tmp_path / "result.json", export)
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content


def test_frequency_heuristic_for_personal_chat(tmp_path: Path) -> None:
    """In a personal chat with no explicit identity, the most frequent sender is self."""
    p = TelegramParser()  # no hints
    f = _write_export(
        tmp_path / "result.json",
        _make_export(
            messages=[
                _make_message(1, "Alice", "userA", "Hi", date="2026-01-15T10:00:00"),
                _make_message(2, "Alice", "userA", "How are you?", date="2026-01-15T10:01:00"),
                _make_message(3, "Alice", "userA", "Anyone?", date="2026-01-15T10:02:00"),
                _make_message(4, "Bob", "userB", "Hey", date="2026-01-15T10:03:00"),
            ],
            chat_type="personal_chat",
        ),
    )
    chunks = p.parse(f)
    # Alice is the most frequent sender, so Alice = self
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content


# ---------------------------------------------------------------------------
# parse() — directory / full export
# ---------------------------------------------------------------------------


def test_parse_single_result_json_file(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    f = _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Me", "user2", "Hi from result.json"),
        ]),
    )
    chunks = p.parse(f)
    assert len(chunks) == 1


def test_parse_directory_with_top_level_result_json(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    _write_export(
        tmp_path / "result.json",
        _make_export([
            _make_message(1, "Me", "user2", "Top level"),
        ]),
    )
    chunks = p.parse(tmp_path)
    assert len(chunks) >= 1


def test_parse_full_export_directory(tmp_path: Path) -> None:
    p = TelegramParser(my_name="Me")
    chat1 = tmp_path / "chat_john"
    chat1.mkdir()
    _write_export(
        chat1 / "result.json",
        _make_export(
            [
                _make_message(1, "John", "user1", "Hello", date="2026-01-15T10:30:00"),
                _make_message(2, "Me", "user2", "Hi John", date="2026-01-15T10:31:00"),
            ],
            chat_name="John",
        ),
    )
    chat2 = tmp_path / "chat_sarah"
    chat2.mkdir()
    _write_export(
        chat2 / "result.json",
        _make_export(
            [
                _make_message(1, "Sarah", "user3", "Hey", date="2026-01-16T10:30:00"),
                _make_message(2, "Me", "user2", "Hi Sarah", date="2026-01-16T10:31:00"),
            ],
            chat_name="Sarah",
        ),
    )
    chunks = p.parse(tmp_path)
    assert len(chunks) >= 2
    talkers = {c.metadata["talker"] for c in chunks}
    assert "John" in talkers
    assert "Sarah" in talkers


# ---------------------------------------------------------------------------
# get_import_guide()
# ---------------------------------------------------------------------------


def test_import_guide_is_nonempty_string(parser: TelegramParser) -> None:
    guide = parser.get_import_guide()
    assert isinstance(guide, str) and len(guide) > 0


def test_import_guide_mentions_telegram(parser: TelegramParser) -> None:
    guide = parser.get_import_guide()
    assert "Telegram" in guide or "telegram" in guide.lower()


def test_import_guide_mentions_result_json(parser: TelegramParser) -> None:
    guide = parser.get_import_guide()
    assert "result.json" in guide or "JSON" in guide
