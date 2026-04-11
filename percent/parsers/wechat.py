from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from percent.models import ChunkType, DataChunk
from percent.parsers.base import DataParser

# Text message type identifiers across different export formats
_TEXT_TYPES = {"1", "text", "文本"}
# Gap between messages (seconds) that starts a new conversation window
_WINDOW_GAP_SECONDS = 30 * 60  # 30 minutes

# Column name mappings for different CSV export tools
# Each tuple: (talker_col, content_col, time_col, type_col)
_CSV_FORMATS = [
    # Original raw DB format
    {"talker": "StrTalker", "content": "StrContent", "time": "CreateTime", "type": "Type"},
    # WeFlow / PyWxDump export format
    {"talker": "talker", "content": "msg", "time": "CreateTime", "type": "type_name"},
    # MemoTrace export format (Chinese headers)
    {"talker": "发送人", "content": "内容", "time": "时间", "type": "类型"},
]


def _detect_csv_format(fieldnames: list[str]) -> dict[str, str] | None:
    """Detect which CSV format matches the given column headers."""
    field_set = set(fieldnames)
    for fmt in _CSV_FORMATS:
        required = {fmt["talker"], fmt["content"], fmt["time"]}
        if required.issubset(field_set):
            return fmt
    return None


class WeChatParser(DataParser):
    name = "wechat"
    description = (
        "Parses WeChat chat logs exported by WeFlow, MemoTrace, PyWxDump (CSV) "
        "or WechatExporter (JSON). Supports single files or a directory of files."
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
                if reader.fieldnames is None:
                    return False
                return _detect_csv_format(list(reader.fieldnames)) is not None
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
                if reader.fieldnames is None:
                    return messages
                fmt = _detect_csv_format(list(reader.fieldnames))
                if fmt is None:
                    return messages

                for row in reader:
                    # Filter text messages only (skip if type column exists)
                    type_val = row.get(fmt["type"], "").strip().lower()
                    if type_val and type_val not in _TEXT_TYPES:
                        continue

                    content = row.get(fmt["content"], "").strip()
                    talker = row.get(fmt["talker"], "unknown").strip()
                    raw_time = row.get(fmt["time"], "").strip()
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
                msg_type = str(entry.get("type", entry.get("msg_type", "1"))).strip().lower()
                if msg_type not in _TEXT_TYPES:
                    continue
                content = entry.get("content", entry.get("msg", entry.get("StrContent", ""))).strip()
                talker = entry.get("talker", entry.get("StrTalker", "unknown")).strip()
                raw_time = str(entry.get("create_time", entry.get("CreateTime", "")))
                ts = self._parse_timestamp(raw_time)
                if content:
                    messages.append((talker, ts, content))
        except (json.JSONDecodeError, OSError):
            pass
        return messages

    def _parse_timestamp(self, raw: str) -> datetime:
        """Parse a Unix timestamp string, ISO 8601 string, or Chinese date format."""
        raw = raw.strip()
        # Try as Unix timestamp (int or float)
        try:
            ts = float(raw)
            if ts > 1e12:  # milliseconds
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=UTC)
        except (ValueError, OSError):
            pass
        # Try ISO 8601
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
        # Try common Chinese date formats: "2024-01-15 14:30:00"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
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
            "Option A — WeFlow (macOS, recommended):\n"
            "  1. Download WeFlow from https://github.com/hicccc77/WeFlow/releases\n"
            "  2. Install the .dmg and open while WeChat is running.\n"
            "  3. Export chats as CSV.\n"
            "  4. Upload the exported file(s) here.\n"
            "\n"
            "Option B — MemoTrace (Windows, recommended):\n"
            "  1. Download MemoTrace from https://github.com/shixiaogaoya/MemoTrace/releases\n"
            "  2. Run the tool while WeChat is logged in on your PC.\n"
            "  3. Export chats as CSV.\n"
            "  4. Upload the exported file(s) here.\n"
            "\n"
            "Note: Only text messages are imported.\n"
            "      Messages within a 30-minute gap are grouped into one conversation chunk.\n"
        )
