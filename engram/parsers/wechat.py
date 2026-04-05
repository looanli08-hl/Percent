from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engram.models import ChunkType, DataChunk
from engram.parsers.base import DataParser

# Only process text messages (Type == 1 in PyWxDump CSV)
_TEXT_TYPE = "1"
# Gap between messages (seconds) that starts a new conversation window
_WINDOW_GAP_SECONDS = 30 * 60  # 30 minutes


class WeChatParser(DataParser):
    name = "wechat"
    description = (
        "Parses WeChat chat logs exported by PyWxDump (CSV) or WechatExporter (JSON). "
        "Supports single files or a directory of files."
    )

    def validate(self, path: Path) -> bool:
        """Return True if path is a supported CSV/JSON file or a directory containing them."""
        if path.is_dir():
            return any(self._validate_single_file(f) for f in path.iterdir() if f.is_file())
        return self._validate_single_file(path)

    def _validate_single_file(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self._validate_csv(path)
        if suffix == ".json":
            return self._validate_json(path)
        return False

    def _validate_csv(self, path: Path) -> bool:
        try:
            with path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                required = {"StrTalker", "StrContent", "CreateTime", "Type"}
                if reader.fieldnames is None:
                    return False
                return required.issubset(set(reader.fieldnames))
        except (OSError, csv.Error):
            return False

    def _validate_json(self, path: Path) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(data, list)
        except (json.JSONDecodeError, OSError):
            return False

    def parse(self, path: Path) -> list[DataChunk]:
        """Parse WeChat export(s) into conversation-window DataChunks."""
        if path.is_dir():
            files = sorted(f for f in path.iterdir() if f.is_file())
        else:
            files = [path]

        all_messages: list[tuple[str, datetime, str]] = []  # (talker, ts, content)

        for f in files:
            suffix = f.suffix.lower()
            if suffix == ".csv":
                all_messages.extend(self._read_csv(f))
            elif suffix == ".json":
                all_messages.extend(self._read_json(f))

        # Sort by timestamp
        all_messages.sort(key=lambda x: x[1])

        # Group into conversation windows per talker
        return self._group_into_chunks(all_messages)

    def _read_csv(self, path: Path) -> list[tuple[str, datetime, str]]:
        messages: list[tuple[str, datetime, str]] = []
        try:
            with path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("Type") != _TEXT_TYPE:
                        continue
                    content = row.get("StrContent", "").strip()
                    talker = row.get("StrTalker", "unknown").strip()
                    raw_time = row.get("CreateTime", "").strip()
                    ts = self._parse_timestamp(raw_time)
                    if content:
                        messages.append((talker, ts, content))
        except (OSError, csv.Error):
            pass
        return messages

    def _read_json(self, path: Path) -> list[tuple[str, datetime, str]]:
        messages: list[tuple[str, datetime, str]] = []
        try:
            data: list[dict] = json.loads(path.read_text(encoding="utf-8"))
            for entry in data:
                # Skip non-text messages; JSON exports may use "type" or "msg_type"
                msg_type = str(entry.get("type", entry.get("msg_type", _TEXT_TYPE)))
                if msg_type != _TEXT_TYPE:
                    continue
                content = entry.get("content", entry.get("StrContent", "")).strip()
                talker = entry.get("talker", entry.get("StrTalker", "unknown")).strip()
                raw_time = str(entry.get("create_time", entry.get("CreateTime", "")))
                ts = self._parse_timestamp(raw_time)
                if content:
                    messages.append((talker, ts, content))
        except (json.JSONDecodeError, OSError):
            pass
        return messages

    def _parse_timestamp(self, raw: str) -> datetime:
        """Parse a Unix timestamp string or ISO 8601 string into a datetime."""
        raw = raw.strip()
        # Try as Unix timestamp (int or float)
        try:
            return datetime.fromtimestamp(float(raw), tz=UTC)
        except (ValueError, OSError):
            pass
        # Try ISO 8601
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
        return datetime.now(tz=UTC)

    def _group_into_chunks(self, messages: list[tuple[str, datetime, str]]) -> list[DataChunk]:
        """Group messages by talker and 30-minute conversation windows."""
        # Bucket messages by talker
        by_talker: dict[str, list[tuple[datetime, str]]] = {}
        for talker, ts, content in messages:
            by_talker.setdefault(talker, []).append((ts, content))

        chunks: list[DataChunk] = []
        gap = timedelta(seconds=_WINDOW_GAP_SECONDS)

        for talker, msgs in by_talker.items():
            msgs.sort(key=lambda x: x[0])
            window_start: datetime = msgs[0][0]
            window_msgs: list[str] = []
            prev_ts: datetime = msgs[0][0]

            for ts, content in msgs:
                if ts - prev_ts > gap and window_msgs:
                    # Flush current window
                    chunks.append(self._make_chunk(talker, window_start, window_msgs))
                    window_start = ts
                    window_msgs = []
                window_msgs.append(content)
                prev_ts = ts

            if window_msgs:
                chunks.append(self._make_chunk(talker, window_start, window_msgs))

        # Sort final chunks by timestamp
        chunks.sort(key=lambda c: c.timestamp)
        return chunks

    def _make_chunk(self, talker: str, timestamp: datetime, messages: list[str]) -> DataChunk:
        content = "\n".join(messages)
        return DataChunk(
            source="wechat",
            type=ChunkType.CONVERSATION,
            timestamp=timestamp,
            content=content,
            metadata={
                "talker": talker,
                "message_count": len(messages),
            },
        )

    def get_import_guide(self) -> str:
        return (
            "WeChat Chat Log Export Guide\n"
            "=============================\n"
            "\n"
            "Option A — PyWxDump (Windows, exports CSV):\n"
            "  1. Download PyWxDump from https://github.com/xaoyaoo/PyWxDump\n"
            "  2. Run the tool while WeChat is logged in on your PC.\n"
            "  3. Export the desired chat to CSV format.\n"
            "  4. The CSV must contain columns: StrTalker, StrContent, CreateTime, Type.\n"
            "  5. Pass the CSV file (or a directory of CSV files) to the parser.\n"
            "\n"
            "Option B — WechatExporter / manual JSON:\n"
            "  1. Export your chat history to JSON format.\n"
            "  2. Each entry should include: talker/StrTalker, content/StrContent,\n"
            "     create_time/CreateTime, type/msg_type (1 = text).\n"
            "  3. Pass the JSON file to the parser.\n"
            "\n"
            "Note: Only text messages (Type=1) are imported.\n"
            "      Messages within a 30-minute gap are grouped into one conversation chunk.\n"
        )
