"""Parse Telegram chat history exports (JSON from Telegram Desktop)."""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engram.models import ChunkType, DataChunk
from engram.parsers.base import DataParser

# Gap between messages (seconds) that starts a new conversation window
_WINDOW_GAP_SECONDS = 30 * 60  # 30 minutes

# Message types to include (skip service messages like "joined group")
_INCLUDE_TYPES = {"message"}


def _flatten_text(text: str | list) -> str:
    """Flatten Telegram's text field, which can be a string or a list of objects."""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        parts = []
        for item in text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                # Extract visible text from formatted segments
                parts.append(item.get("text", ""))
        return "".join(parts)
    return str(text)


def _parse_telegram_datetime(date_str: str) -> datetime:
    """Parse a Telegram ISO 8601 datetime string into a UTC datetime."""
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, AttributeError):
        return datetime.now(tz=UTC)


class TelegramParser(DataParser):
    name = "telegram"
    description = (
        "Parses Telegram Desktop chat history exports (result.json). "
        "Supports single chat exports and full export directories."
    )

    def __init__(self, my_name: str | None = None, my_user_id: str | None = None) -> None:
        """
        Args:
            my_name: The user's display name as it appears in the export's 'from' field.
            my_user_id: The user's Telegram user ID (e.g. 'user123456'). Takes precedence
                        over my_name if provided.
        """
        self.my_name = my_name
        self.my_user_id = my_user_id

    def validate(self, path: Path) -> bool:
        if path.is_dir():
            # Full export: look for result.json anywhere in the directory tree
            return (
                (path / "result.json").exists()
                or any(path.glob("*/result.json"))
            )
        return path.suffix.lower() == ".json" and self._looks_like_telegram(path)

    def _looks_like_telegram(self, path: Path) -> bool:
        """Check if a JSON file looks like a Telegram export."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(data, dict) and "messages" in data
        except (json.JSONDecodeError, OSError):
            return False

    def parse(self, path: Path) -> list[DataChunk]:
        result_files = self._find_result_files(path)
        if not result_files:
            return []

        chunks: list[DataChunk] = []
        for result_file in sorted(result_files):
            chunks.extend(self._parse_single_export(result_file))

        return chunks

    def _find_result_files(self, path: Path) -> list[Path]:
        """Find all result.json files under path (or path itself if a file)."""
        if path.is_file():
            return [path]
        # Check top-level result.json
        found: list[Path] = []
        top = path / "result.json"
        if top.exists():
            found.append(top)
        # Check one level deep (chat sub-folders in full export)
        for child in sorted(path.iterdir()):
            if child.is_dir():
                child_result = child / "result.json"
                if child_result.exists():
                    found.append(child_result)
        return found

    def _parse_single_export(self, result_file: Path) -> list[DataChunk]:
        """Parse one result.json export file into DataChunks."""
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(data, dict):
            return []

        chat_name = data.get("name", "Unknown")
        chat_type = data.get("type", "")
        raw_messages = data.get("messages", [])

        if not isinstance(raw_messages, list):
            return []

        # Try to determine self identity from personal_information block
        my_id = self.my_user_id
        my_name = self.my_name
        if not my_id:
            personal_info = data.get("personal_information", {})
            if isinstance(personal_info, dict):
                user_id = personal_info.get("user_id")
                if user_id:
                    my_id = f"user{user_id}"

        # Parse messages
        messages: list[dict] = []
        for raw in raw_messages:
            if not isinstance(raw, dict):
                continue
            if raw.get("type") not in _INCLUDE_TYPES:
                continue

            text = _flatten_text(raw.get("text", "")).strip()
            if not text:
                continue

            date_str = raw.get("date", "")
            timestamp = _parse_telegram_datetime(date_str)
            sender = raw.get("from") or raw.get("actor") or ""
            from_id = str(raw.get("from_id", ""))

            messages.append({
                "timestamp": timestamp,
                "sender": sender,
                "from_id": from_id,
                "content": text,
                "is_self": False,  # resolved below
            })

        if not messages:
            return []

        # Resolve which sender is "self"
        resolved_my_id, resolved_my_name = self._resolve_self(
            messages, my_id, my_name, chat_type
        )

        for msg in messages:
            if resolved_my_id and msg["from_id"] == resolved_my_id:
                msg["is_self"] = True
            elif resolved_my_name and msg["sender"] == resolved_my_name:
                msg["is_self"] = True

        messages.sort(key=lambda m: m["timestamp"])

        # Determine talker name
        talker = self._determine_talker(messages, chat_name, chat_type, resolved_my_name)

        return self._group_into_chunks(messages, talker)

    def _resolve_self(
        self,
        messages: list[dict],
        my_id: str | None,
        my_name: str | None,
        chat_type: str,
    ) -> tuple[str | None, str | None]:
        """
        Determine the from_id and name that represent the user.
        Priority: explicit my_id > explicit my_name > frequency heuristic.
        """
        if my_id:
            # Find name from messages
            for msg in messages:
                if msg["from_id"] == my_id:
                    return my_id, msg["sender"]
            return my_id, my_name

        if my_name:
            # Find from_id from messages
            for msg in messages:
                if msg["sender"] == my_name:
                    return msg["from_id"] or None, my_name
            return None, my_name

        # Heuristic: in personal_chat the user is typically one of two participants;
        # use the most frequent sender as self.
        if chat_type == "personal_chat":
            from_ids = [m["from_id"] for m in messages if m["from_id"]]
            if from_ids:
                most_common_id = Counter(from_ids).most_common(1)[0][0]
                for msg in messages:
                    if msg["from_id"] == most_common_id:
                        return most_common_id, msg["sender"]

        # For group chats without explicit identity, we cannot safely assume
        return None, None

    def _determine_talker(
        self,
        messages: list[dict],
        chat_name: str,
        chat_type: str,
        my_name: str | None,
    ) -> str:
        """Determine a display name for the conversation partner / group."""
        if chat_name and chat_name != "Unknown":
            return chat_name

        # Fallback: use non-self senders
        non_self_senders = list(dict.fromkeys(
            m["sender"] for m in messages
            if not m["is_self"] and m["sender"]
        ))
        if non_self_senders:
            if len(non_self_senders) == 1:
                return non_self_senders[0]
            return ", ".join(non_self_senders[:2]) + (
                f" +{len(non_self_senders) - 2}" if len(non_self_senders) > 2 else ""
            )
        return "Unknown"

    def _group_into_chunks(self, messages: list[dict], talker: str) -> list[DataChunk]:
        """Group messages into 30-minute conversation windows."""
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
        """Build a DataChunk from a window. Returns None if user didn't speak."""
        if not any(m["is_self"] for m in window):
            return None

        lines = []
        for m in window:
            prefix = "[我]" if m["is_self"] else f"[{m['sender']}]"
            lines.append(f"{prefix} {m['content']}")

        self_count = sum(1 for m in window if m["is_self"])

        return DataChunk(
            source="telegram",
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
            "Telegram Chat Export Guide\n"
            "==========================\n"
            "\n"
            "Single Chat Export:\n"
            "  1. Open Telegram Desktop.\n"
            "  2. Open the chat you want to export.\n"
            "  3. Click the three-dot menu (top right) > Export Chat History.\n"
            "  4. Uncheck media, select 'Machine-readable JSON' format.\n"
            "  5. Click Export. You will get a result.json file.\n"
            "  6. Run: engram import run telegram /path/to/result.json\n"
            "\n"
            "Full Export (all chats):\n"
            "  1. In Telegram Desktop, go to Settings > Advanced > Export Telegram Data.\n"
            "  2. Select 'Personal chats' and/or 'Group chats'.\n"
            "  3. Set format to JSON.\n"
            "  4. Click Export. You will get a directory with chat sub-folders.\n"
            "  5. Run: engram import run telegram /path/to/export/directory\n"
            "\n"
            "Notes:\n"
            "  - Your messages will appear as '[我]' in the output.\n"
            "  - In personal chats, the most frequent sender is treated as you.\n"
            "  - For group chats, pass --my-name 'YourName' to identify your messages.\n"
        )
