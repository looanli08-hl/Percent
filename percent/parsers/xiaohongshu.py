"""Parse Xiaohongshu (小红书) exported data — liked/bookmarked notes."""
from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from percent.models import ChunkType, DataChunk
from percent.parsers.base import DataParser


def _get(entry: dict, *keys: str, default: str = "") -> str:
    """Try multiple keys, return first non-empty value."""
    for k in keys:
        val = entry.get(k)
        if val is not None:
            return str(val).strip()
    return default


def _parse_time(raw: str) -> datetime:
    """Parse XHS time formats: '2024.01.15 14:30:00', ISO 8601, or Unix timestamp."""
    raw = raw.strip()
    if not raw:
        return datetime.now(tz=UTC)
    # Unix timestamp
    try:
        ts = float(raw)
        if ts > 1e12:
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=UTC)
    except (ValueError, OSError):
        pass
    # XHS dot-separated format: "2024.01.15 14:30:00"
    for fmt in (
        "%Y.%m.%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    # ISO 8601
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass
    return datetime.now(tz=UTC)


def _parse_tags(entry: dict) -> list[str]:
    """Extract tag names from various tag_list formats."""
    raw = entry.get("tag_list")
    if not raw:
        return []
    if isinstance(raw, list):
        return [t.get("name", "") for t in raw if isinstance(t, dict) and t.get("name")]
    if isinstance(raw, str):
        try:
            tags = json.loads(raw)
            if isinstance(tags, list):
                return [t.get("name", "") for t in tags if isinstance(t, dict)]
        except json.JSONDecodeError:
            return [t.strip() for t in raw.split(",") if t.strip()]
    return []


def _note_to_chunk(entry: dict) -> DataChunk | None:
    """Convert a single note dict to a DataChunk."""
    title = _get(entry, "title", "作品标题")
    desc = _get(entry, "desc", "content", "description", "作品描述")
    author = _get(entry, "nickname", "nick", "author_name", "user_nickname", "作者昵称", default="unknown")
    note_type = _get(entry, "type", "note_type", "作品类型", default="normal")
    raw_time = _get(entry, "time", "create_time", "publish_time", "发布时间", "last_update_time")
    note_id = _get(entry, "note_id", "num_iid", "id", "作品ID")
    tags = _parse_tags(entry)

    # Build content string
    parts = []
    if title:
        parts.append(title)
    if desc and desc != title:
        parts.append(desc)
    if not parts:
        return None

    content = "\n".join(parts)
    if tags:
        content += f"\nTags: {', '.join(tags)}"

    # Extract interaction counts
    interact = entry.get("interact_info", {})
    liked = _get(interact, "liked_count") or _get(entry, "liked_count", "点赞数量")
    collected = _get(interact, "collected_count") or _get(entry, "collected_count", "收藏数量")
    comment_count = _get(interact, "comment_count") or _get(entry, "comment_count", "评论数量")

    timestamp = _parse_time(raw_time)

    return DataChunk(
        source="xiaohongshu",
        type=ChunkType.SOCIAL_INTERACTION,
        timestamp=timestamp,
        content=content,
        metadata={
            "author": author,
            "note_type": note_type,
            "note_id": note_id,
            "tags": tags,
            "liked_count": liked,
            "collected_count": collected,
            "comment_count": comment_count,
        },
    )


class XiaohongshuParser(DataParser):
    name = "xiaohongshu"
    description = (
        "Parses Xiaohongshu (小红书) exported data — liked notes, bookmarked notes, "
        "or published notes. Supports JSON and CSV from various export tools."
    )

    def validate(self, path: Path) -> bool:
        if path.is_dir():
            return any(self._validate_file(f) for f in path.iterdir() if f.is_file())
        return self._validate_file(path)

    def _validate_file(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        if suffix == ".json":
            return self._validate_json(path)
        if suffix == ".csv":
            return self._validate_csv(path)
        return False

    def _validate_json(self, path: Path) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict):
                    # Check for common XHS fields
                    keys = set(first.keys())
                    xhs_keys = {"note_id", "title", "desc", "nickname", "nick", "num_iid",
                                "作品标题", "作品描述", "作者昵称"}
                    return bool(keys & xhs_keys)
            return False
        except (json.JSONDecodeError, OSError):
            return False

    def _validate_csv(self, path: Path) -> bool:
        try:
            with path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    return False
                fields = set(reader.fieldnames)
                xhs_fields = {"note_id", "title", "desc", "nickname",
                              "作品标题", "作品描述", "作者昵称"}
                return bool(fields & xhs_fields)
        except (OSError, csv.Error):
            return False

    def parse(self, path: Path) -> list[DataChunk]:
        if path.is_dir():
            files = sorted(f for f in path.iterdir() if f.is_file())
        else:
            files = [path]

        chunks: list[DataChunk] = []
        for f in files:
            suffix = f.suffix.lower()
            if suffix == ".json":
                chunks.extend(self._parse_json(f))
            elif suffix == ".csv":
                chunks.extend(self._parse_csv(f))

        chunks.sort(key=lambda c: c.timestamp)
        return chunks

    def _parse_json(self, path: Path) -> list[DataChunk]:
        chunks: list[DataChunk] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = [data]
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                chunk = _note_to_chunk(entry)
                if chunk:
                    chunks.append(chunk)
        except (json.JSONDecodeError, OSError):
            pass
        return chunks

    def _parse_csv(self, path: Path) -> list[DataChunk]:
        chunks: list[DataChunk] = []
        try:
            with path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    chunk = _note_to_chunk(row)
                    if chunk:
                        chunks.append(chunk)
        except (OSError, csv.Error):
            pass
        return chunks

    def get_import_guide(self) -> str:
        return (
            "Xiaohongshu (小红书) Data Export Guide\n"
            "======================================\n"
            "\n"
            "Export your liked and bookmarked notes using a Chrome extension:\n"
            "  1. Install the '小红书导出' Chrome extension\n"
            "  2. Log in to xiaohongshu.com in your browser\n"
            "  3. Navigate to your liked or bookmarked notes\n"
            "  4. Use the extension to export as JSON\n"
            "  5. Upload the exported JSON file here\n"
            "\n"
            "Alternative: Use XHS-Downloader to export your saved content.\n"
            "\n"
            "Note: Only text content is analyzed (titles, descriptions, tags).\n"
        )
