"""Parse WhatsApp chat export (.txt) files."""
from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engram.models import ChunkType, DataChunk
from engram.parsers.base import DataParser

# Gap between messages (seconds) that starts a new conversation window
_WINDOW_GAP_SECONDS = 30 * 60  # 30 minutes

# System message patterns to skip
_SYSTEM_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^messages and calls are end-to-end encrypted",
        r"^.+ added .+$",
        r"^.+ removed .+$",
        r"^.+ left$",
        r"^.+ joined using this group's invite link$",
        r"^.+ changed the subject",
        r"^.+ changed the group",
        r"^.+ changed this group",
        r"^.+ was added$",
        r"^.+ changed the icon",
        r"^you created group",
        r"^.+ created group",
        r"^\u200e",  # Left-to-right mark prefix (WhatsApp system messages)
        r"^this message was deleted$",
        r"^\[?\d",  # Starts with a bracket+digit or digit — not a system msg, skip this one
    ]
]

# Patterns for WhatsApp timestamp/sender lines
# Format 1: [1/15/26, 10:30:15 AM] John: message
_PATTERN_BRACKET_US = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M)\]\s+(.+?):\s(.+)$",
    re.DOTALL,
)

# Format 2: 15/01/2026, 10:30:15 - John: message  (international / Android)
_PATTERN_INTL = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s+-\s+(.+?):\s(.+)$",
    re.DOTALL,
)

# Format 3: [2026/1/15 10:30:15] John: message
_PATTERN_BRACKET_ISO = re.compile(
    r"^\[(\d{4}/\d{1,2}/\d{1,2})\s+(\d{1,2}:\d{2}(?::\d{2})?)\]\s+(.+?):\s(.+)$",
    re.DOTALL,
)

# Format 4: [15.01.26, 10:30:15] John: message  (some locales use dots)
_PATTERN_BRACKET_DOT = re.compile(
    r"^\[(\d{1,2}\.\d{1,2}\.\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AP]M)?)\]\s+(.+?):\s(.+)$",
    re.DOTALL,
)

# Continuation line detection: starts with bracket timestamp or intl format
_CONTINUATION_START = re.compile(
    r"^\[?\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}"
)


def _parse_datetime(date_str: str, time_str: str) -> datetime | None:
    """Try various date/time format combinations and return a UTC datetime or None."""
    date_str = date_str.strip()
    time_str = time_str.strip()
    combined = f"{date_str} {time_str}"

    formats = [
        # US bracket format: 1/15/26, 10:30:15 AM
        "%m/%d/%y %I:%M:%S %p",
        "%m/%d/%y %I:%M %p",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        # International: 15/01/2026 10:30:15
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%y %H:%M",
        # International with AM/PM
        "%d/%m/%Y %I:%M:%S %p",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%y %I:%M:%S %p",
        "%d/%m/%y %I:%M %p",
        # ISO bracket: 2026/1/15 10:30:15
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        # Dot format: 15.01.26
        "%d.%m.%y %H:%M:%S",
        "%d.%m.%y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(combined, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _is_system_message(text: str) -> bool:
    """Return True if the text looks like a WhatsApp system/notification message."""
    text = text.strip()
    # The last pattern in _SYSTEM_PATTERNS is a negative guard — skip it
    for pattern in _SYSTEM_PATTERNS[:-1]:
        if pattern.search(text):
            return True
    return False


class WhatsAppParser(DataParser):
    name = "whatsapp"
    description = (
        "Parses WhatsApp chat exports (.txt). Supports US bracket format, "
        "international format, and ISO bracket format."
    )

    def __init__(self, my_name: str | None = None) -> None:
        """
        Args:
            my_name: The user's display name as it appears in the chat export.
                     WhatsApp often uses 'Me' for the exporting user's messages,
                     but this can vary by locale. If not provided, the parser
                     auto-detects by treating 'Me' as self, or falls back to the
                     most-frequent sender.
        """
        self.my_name = my_name

    def validate(self, path: Path) -> bool:
        if path.is_dir():
            return any(f.suffix.lower() == ".txt" and self._looks_like_whatsapp(f)
                       for f in path.iterdir() if f.is_file())
        return path.suffix.lower() == ".txt" and self._looks_like_whatsapp(path)

    def _looks_like_whatsapp(self, path: Path) -> bool:
        """Check if the first few non-empty lines match a known WhatsApp format."""
        try:
            lines_checked = 0
            with path.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if not line.strip():
                        continue
                    if (
                        _PATTERN_BRACKET_US.match(line)
                        or _PATTERN_INTL.match(line)
                        or _PATTERN_BRACKET_ISO.match(line)
                        or _PATTERN_BRACKET_DOT.match(line)
                    ):
                        return True
                    lines_checked += 1
                    if lines_checked >= 10:
                        break
        except OSError:
            pass
        return False

    def parse(self, path: Path) -> list[DataChunk]:
        if path.is_dir():
            files = sorted(f for f in path.iterdir()
                           if f.is_file() and f.suffix.lower() == ".txt")
        else:
            files = [path]

        all_messages: list[dict] = []
        for f in files:
            all_messages.extend(self._parse_file(f))

        if not all_messages:
            return []

        # Determine self name
        my_name = self._resolve_my_name(all_messages)

        # Annotate is_self
        for msg in all_messages:
            msg["is_self"] = (msg["sender"] == my_name)

        # Group by conversation (all messages from one file share the same "talker")
        # Identify talker per file group — use the non-self sender name
        all_messages.sort(key=lambda m: m["timestamp"])

        return self._group_into_chunks(all_messages, my_name)

    def _parse_file(self, path: Path) -> list[dict]:
        """Parse a single WhatsApp export file into raw message dicts."""
        messages: list[dict] = []
        current: dict | None = None

        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                for raw_line in f:
                    line = raw_line.rstrip("\n")
                    parsed = self._try_parse_line(line)
                    if parsed is not None:
                        if current is not None:
                            content = current["content"].strip()
                            if content and not _is_system_message(content):
                                messages.append(current)
                        current = parsed
                    elif current is not None:
                        # Continuation line — append to current message
                        current["content"] += "\n" + line
        except OSError:
            pass

        # Flush last message
        if current is not None:
            content = current["content"].strip()
            if content and not _is_system_message(content):
                messages.append(current)

        return messages

    def _try_parse_line(self, line: str) -> dict | None:
        """Try to parse a line as a new WhatsApp message. Returns dict or None."""
        for pattern in [
            _PATTERN_BRACKET_US,
            _PATTERN_BRACKET_ISO,
            _PATTERN_BRACKET_DOT,
            _PATTERN_INTL,
        ]:
            m = pattern.match(line)
            if m:
                date_str, time_str, sender, content = m.group(1), m.group(2), m.group(3), m.group(4)
                ts = _parse_datetime(date_str, time_str)
                if ts is None:
                    continue
                return {
                    "timestamp": ts,
                    "sender": sender.strip(),
                    "content": content.strip(),
                    "is_self": False,  # resolved later
                }
        return None

    def _resolve_my_name(self, messages: list[dict]) -> str:
        """Determine which sender name represents the user."""
        if self.my_name:
            return self.my_name

        senders = [m["sender"] for m in messages]
        # Check for explicit "Me" / "You" (locale-specific defaults)
        for me_alias in ("Me", "You", "Я", "Moi", "Yo", "Io", "Ich"):
            if me_alias in senders:
                return me_alias

        # Fall back to most frequent sender
        if senders:
            return Counter(senders).most_common(1)[0][0]
        return ""

    def _group_into_chunks(self, messages: list[dict], my_name: str) -> list[DataChunk]:
        """Group messages by talker and 30-minute windows into DataChunks."""
        # Identify the "talker" for each conversation as the non-self participant
        # For group chats, use a synthetic name from all unique non-self senders
        # For simplicity, we group all messages into one logical conversation per
        # unique set of non-self participants encountered in adjacent windows.
        # Since WhatsApp exports one file per conversation, all messages share a talker.

        # Find all non-self senders
        non_self = [m["sender"] for m in messages if not m["is_self"]]
        if non_self:
            # Most common non-self sender = the contact name for 1-on-1 chats
            # For group chats there will be multiple; use the chat's unique senders joined
            unique_non_self = list(dict.fromkeys(non_self))  # preserve order, deduplicate
            if len(unique_non_self) == 1:
                talker = unique_non_self[0]
            else:
                # Group chat: use the top two names + "..."
                talker = ", ".join(unique_non_self[:2])
                if len(unique_non_self) > 2:
                    talker += f" +{len(unique_non_self) - 2}"
        else:
            talker = "Unknown"

        gap = timedelta(seconds=_WINDOW_GAP_SECONDS)
        chunks: list[DataChunk] = []

        if not messages:
            return chunks

        window: list[dict] = [messages[0]]
        for msg in messages[1:]:
            if msg["timestamp"] - window[-1]["timestamp"] > gap:
                chunk = self._make_chunk(window, talker)
                if chunk is not None:
                    chunks.append(chunk)
                window = []
            window.append(msg)

        if window:
            chunk = self._make_chunk(window, talker)
            if chunk is not None:
                chunks.append(chunk)

        return chunks

    def _make_chunk(self, window: list[dict], talker: str) -> DataChunk | None:
        """Build a DataChunk from a window of messages. Returns None if user didn't speak."""
        if not any(m["is_self"] for m in window):
            return None

        lines = []
        for m in window:
            prefix = "[我]" if m["is_self"] else f"[{m['sender']}]"
            lines.append(f"{prefix} {m['content']}")

        self_count = sum(1 for m in window if m["is_self"])

        return DataChunk(
            source="whatsapp",
            type=ChunkType.CONVERSATION,
            timestamp=window[0]["timestamp"],
            content="\n".join(lines),
            metadata={
                "talker": talker,
                "message_count": len(window),
                "self_message_count": self_count,
            },
        )

    def get_import_guide(self) -> str:
        return (
            "WhatsApp Chat Export Guide\n"
            "==========================\n"
            "\n"
            "1. Open WhatsApp on your iPhone or Android.\n"
            "2. Open the chat you want to export.\n"
            "3. Tap the contact/group name at the top.\n"
            "4. Scroll down and tap 'Export Chat'.\n"
            "5. Choose 'Without Media' for text-only export.\n"
            "6. Save or share the resulting .txt file.\n"
            "7. Run: engram import run whatsapp /path/to/chat.txt\n"
            "\n"
            "Notes:\n"
            "  - Your messages will appear as '[我]' in the output.\n"
            "  - WhatsApp typically labels your own messages as 'Me'.\n"
            "  - If your name appears differently, pass --my-name 'YourName'.\n"
            "  - Supported formats: US bracket [M/D/YY, H:MM AM], international\n"
            "    (DD/MM/YYYY, H:MM - ), and ISO bracket [YYYY/M/D H:MM].\n"
        )
