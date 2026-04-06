from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from percent.models import ChunkType, DataChunk
from percent.parsers.base import DataParser

_INVALID_TITLE = "已失效视频"


class BilibiliParser(DataParser):
    name = "bilibili"
    description = "Parses Bilibili watch history exported as JSON."

    def validate(self, path: Path) -> bool:
        """Return True if path is a JSON file containing a list of watch-history entries."""
        if not path.is_file() or path.suffix.lower() != ".json":
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(data, list)
        except (json.JSONDecodeError, OSError):
            return False

    def parse(self, path: Path) -> list[DataChunk]:
        """Parse Bilibili watch-history JSON into DataChunks."""
        data: list[dict] = json.loads(path.read_text(encoding="utf-8"))
        chunks: list[DataChunk] = []

        for entry in data:
            title = entry.get("title", "")
            if title == _INVALID_TITLE:
                continue

            view_at = entry.get("view_at")
            timestamp = datetime.fromtimestamp(view_at, tz=UTC) if view_at else datetime.now(tz=UTC)

            author = entry.get("author_name", "")
            tag = entry.get("tag_name", "")
            duration = entry.get("duration", 0)

            parts = [f"Watched: {title}"]
            if author:
                parts.append(f"by {author}")
            if tag:
                parts.append(f"[{tag}]")
            content = " ".join(parts)

            metadata: dict = {}
            if author:
                metadata["author"] = author
            if tag:
                metadata["category"] = tag
            if duration:
                metadata["duration_seconds"] = duration

            chunks.append(
                DataChunk(
                    source="bilibili",
                    type=ChunkType.WATCH_HISTORY,
                    timestamp=timestamp,
                    content=content,
                    metadata=metadata,
                )
            )

        return chunks

    def get_import_guide(self) -> str:
        return (
            "Bilibili Watch History Export Guide\n"
            "====================================\n"
            "1. Visit https://www.bilibili.com and log in.\n"
            "2. Go to '历史记录' (History) via your avatar menu.\n"
            "3. Use a browser extension such as 'Bilibili History Export' or\n"
            "   the unofficial API endpoint:\n"
            "   https://api.bilibili.com/x/web-interface/history/cursor\n"
            "   to export your history as a JSON file.\n"
            "4. Save the exported file and pass its path to the parser.\n"
            "\n"
            "Expected format: a JSON array where each object has at minimum:\n"
            "  title      — video title (str)\n"
            "  tag_name   — category tag (str)\n"
            "  view_at    — Unix timestamp of when you watched (int)\n"
            "  author_name — uploader name (str)\n"
            "  duration   — video length in seconds (int)\n"
        )
