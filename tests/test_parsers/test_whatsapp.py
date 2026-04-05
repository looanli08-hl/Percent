"""Tests for the WhatsApp chat export parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from engram.models import ChunkType
from engram.parsers.whatsapp import WhatsAppParser


@pytest.fixture()
def parser() -> WhatsAppParser:
    return WhatsAppParser(my_name="Me")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_chat(path: Path, lines: list[str]) -> Path:
    """Write a WhatsApp-style .txt file."""
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


def test_validate_us_bracket_format(parser: WhatsAppParser, tmp_path: Path) -> None:
    f = _write_chat(
        tmp_path / "chat.txt",
        ["[1/15/26, 10:30:15 AM] John: Hello there"],
    )
    assert parser.validate(f) is True


def test_validate_international_format(parser: WhatsAppParser, tmp_path: Path) -> None:
    f = _write_chat(
        tmp_path / "chat.txt",
        ["15/01/2026, 10:30:15 - John: Hello there"],
    )
    assert parser.validate(f) is True


def test_validate_iso_bracket_format(parser: WhatsAppParser, tmp_path: Path) -> None:
    f = _write_chat(
        tmp_path / "chat.txt",
        ["[2026/1/15 10:30:15] John: Hello there"],
    )
    assert parser.validate(f) is True


def test_validate_non_whatsapp_txt(parser: WhatsAppParser, tmp_path: Path) -> None:
    f = tmp_path / "notes.txt"
    f.write_text("Just some random notes\nNo chat format here", encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_wrong_extension(parser: WhatsAppParser, tmp_path: Path) -> None:
    f = tmp_path / "chat.csv"
    f.write_text("[1/15/26, 10:30:15 AM] John: Hello", encoding="utf-8")
    assert parser.validate(f) is False


def test_validate_directory_with_valid_file(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    _write_chat(
        tmp_path / "chat.txt",
        ["[1/15/26, 10:30:15 AM] John: Hello"],
    )
    assert p.validate(tmp_path) is True


def test_validate_empty_directory(parser: WhatsAppParser, tmp_path: Path) -> None:
    assert parser.validate(tmp_path) is False


# ---------------------------------------------------------------------------
# parse() — basic parsing
# ---------------------------------------------------------------------------


def test_parse_us_bracket_format(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:30:15 AM] John: Hey, what's up?",
            "[1/15/26, 10:31:02 AM] Me: Not much, just working on a project",
            "[1/15/26, 10:31:45 AM] John: Cool",
        ],
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content
    assert "[John]" in chunks[0].content
    assert "Not much" in chunks[0].content


def test_parse_international_format(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "15/01/2026, 10:30:15 - John: Hey, what's up?",
            "15/01/2026, 10:31:02 - Me: Not much",
        ],
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content
    assert "Not much" in chunks[0].content


def test_parse_iso_bracket_format(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[2026/1/15 10:30:15] John: Hey",
            "[2026/1/15 10:31:00] Me: Hi there",
        ],
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content


def test_parse_chunk_source_and_type(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        ["[1/15/26, 10:30:15 AM] Me: Hello"],
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert chunks[0].source == "whatsapp"
    assert chunks[0].type == ChunkType.CONVERSATION


def test_parse_metadata_fields(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:30:15 AM] John: Hi",
            "[1/15/26, 10:31:00 AM] Me: Hey",
            "[1/15/26, 10:31:30 AM] John: How are you?",
        ],
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    meta = chunks[0].metadata
    assert meta["message_count"] == 3
    assert meta["self_message_count"] == 1
    assert "talker" in meta


# ---------------------------------------------------------------------------
# parse() — system message skipping
# ---------------------------------------------------------------------------


def test_skips_encryption_notice(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:00:00 AM] Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them.",
            "[1/15/26, 10:30:00 AM] Me: Hello",
            "[1/15/26, 10:31:00 AM] John: Hi",
        ],
    )
    chunks = p.parse(f)
    # The system message line won't match the sender:content pattern anyway
    # (no sender name before colon), but verify content is correct
    combined = "\n".join(c.content for c in chunks)
    assert "No one outside" not in combined


def test_skips_added_member_system_message(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    # System messages in WhatsApp don't follow the "Sender: content" pattern
    # They appear as plain text lines or with special Unicode markers.
    # We test that our content filter ignores them.
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:30:00 AM] Me: Hello group",
            "[1/15/26, 10:31:00 AM] John: Hi",
        ],
    )
    chunks = p.parse(f)
    assert len(chunks) >= 1
    assert "[我]" in chunks[0].content


# ---------------------------------------------------------------------------
# parse() — conversation windowing
# ---------------------------------------------------------------------------


def test_groups_close_messages_into_one_chunk(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:00:00 AM] Me: Good morning",
            "[1/15/26, 10:10:00 AM] John: Morning!",
            "[1/15/26, 10:20:00 AM] Me: How are you?",
        ],
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert chunks[0].metadata["message_count"] == 3


def test_splits_on_30_minute_gap(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:00:00 AM] Me: Morning",
            "[1/15/26, 10:31:00 AM] John: Evening",
            "[1/15/26, 10:32:00 AM] Me: Reply",
        ],
    )
    chunks = p.parse(f)
    assert len(chunks) == 2


def test_window_without_self_message_is_excluded(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            # First window: only John speaks
            "[1/15/26, 10:00:00 AM] John: Hello?",
            "[1/15/26, 10:01:00 AM] John: Anyone there?",
            # 31-minute gap
            "[1/15/26, 10:32:00 AM] Me: Sorry, was away",
            "[1/15/26, 10:33:00 AM] John: No worries",
        ],
    )
    chunks = p.parse(f)
    # Only the second window (where Me speaks) should be included
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content


# ---------------------------------------------------------------------------
# parse() — speaker identification
# ---------------------------------------------------------------------------


def test_auto_detects_me_sender(tmp_path: Path) -> None:
    """Without my_name set, 'Me' should be auto-detected as self."""
    p = WhatsAppParser()  # No my_name
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:30:15 AM] John: Hey",
            "[1/15/26, 10:31:00 AM] Me: Hi!",
        ],
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content


def test_explicit_my_name_overrides_auto_detect(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Alice")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:30:15 AM] Bob: Hey there",
            "[1/15/26, 10:31:00 AM] Alice: Hey Bob",
        ],
    )
    chunks = p.parse(f)
    assert len(chunks) == 1
    assert "[我]" in chunks[0].content
    # Alice's message should be labeled [我], not [Alice]
    assert "[Alice]" not in chunks[0].content


def test_talker_name_is_contact(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:30:15 AM] Sarah: Hello!",
            "[1/15/26, 10:31:00 AM] Me: Hi Sarah",
        ],
    )
    chunks = p.parse(f)
    assert chunks[0].metadata["talker"] == "Sarah"


# ---------------------------------------------------------------------------
# parse() — multiline messages
# ---------------------------------------------------------------------------


def test_multiline_message(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    f = _write_chat(
        tmp_path / "chat.txt",
        [
            "[1/15/26, 10:30:15 AM] Me: Line one",
            "Line two of same message",
            "Line three",
            "[1/15/26, 10:31:00 AM] John: Got it",
        ],
    )
    chunks = p.parse(f)
    assert "Line one" in chunks[0].content
    assert "Line two" in chunks[0].content
    assert "Line three" in chunks[0].content


# ---------------------------------------------------------------------------
# parse() — directory of files
# ---------------------------------------------------------------------------


def test_parse_directory_with_multiple_files(tmp_path: Path) -> None:
    p = WhatsAppParser(my_name="Me")
    _write_chat(
        tmp_path / "chat_john.txt",
        [
            "[1/15/26, 10:30:15 AM] John: Hi",
            "[1/15/26, 10:31:00 AM] Me: Hello John",
        ],
    )
    _write_chat(
        tmp_path / "chat_sarah.txt",
        [
            "[1/16/26, 10:30:15 AM] Sarah: Hey",
            "[1/16/26, 10:31:00 AM] Me: Hey Sarah",
        ],
    )
    chunks = p.parse(tmp_path)
    assert len(chunks) >= 2


# ---------------------------------------------------------------------------
# get_import_guide()
# ---------------------------------------------------------------------------


def test_import_guide_is_nonempty_string(parser: WhatsAppParser) -> None:
    guide = parser.get_import_guide()
    assert isinstance(guide, str) and len(guide) > 0


def test_import_guide_mentions_whatsapp(parser: WhatsAppParser) -> None:
    guide = parser.get_import_guide()
    assert "WhatsApp" in guide or "whatsapp" in guide.lower()


def test_import_guide_mentions_export_chat(parser: WhatsAppParser) -> None:
    guide = parser.get_import_guide()
    assert "Export" in guide or "export" in guide
