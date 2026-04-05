from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from engram.models import ChunkType, DataChunk
from engram.parsers.base import DataParser

_WATCHED_PREFIX = "Watched "


class YouTubeParser(DataParser):
    name = "youtube"
    description = "Parses YouTube watch history from Google Takeout (watch-history.json)."

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
        """Parse Google Takeout YouTube watch-history JSON into DataChunks."""
        data: list[dict] = json.loads(path.read_text(encoding="utf-8"))
        chunks: list[DataChunk] = []

        for entry in data:
            raw_title: str = entry.get("title", "")
            # Strip "Watched " prefix if present
            title = raw_title.removeprefix(_WATCHED_PREFIX)

            time_str: str = entry.get("time", "")
            try:
                timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now(tz=UTC)

            # Extract channel name from subtitles array
            subtitles: list[dict] = entry.get("subtitles", [])
            channel = subtitles[0].get("name", "") if subtitles else ""

            title_url: str = entry.get("titleUrl", "")

            parts = [f"Watched: {title}"]
            if channel:
                parts.append(f"by {channel}")
            content = " ".join(parts)

            metadata: dict = {}
            if channel:
                metadata["channel"] = channel
            if title_url:
                metadata["url"] = title_url

            chunks.append(
                DataChunk(
                    source="youtube",
                    type=ChunkType.WATCH_HISTORY,
                    timestamp=timestamp,
                    content=content,
                    metadata=metadata,
                )
            )

        return chunks

    def get_import_guide(self) -> str:
        return (
            "YouTube Watch History Export Guide (Google Takeout)\n"
            "====================================================\n"
            "1. Go to https://takeout.google.com and sign in.\n"
            "2. Click 'Deselect all', then scroll to 'YouTube and YouTube Music'\n"
            "   and enable it.\n"
            "3. Click 'All YouTube data included', deselect everything except\n"
            "   'history', then click OK.\n"
            "4. Choose export format JSON (not HTML) under 'history'.\n"
            "5. Create the export and download the archive when ready.\n"
            "6. Inside the archive, locate:\n"
            "   Takeout/YouTube and YouTube Music/history/watch-history.json\n"
            "7. Pass that file's path to the parser.\n"
            "\n"
            "Expected format: a JSON array where each object has:\n"
            "  title      — 'Watched <video title>' (str)\n"
            "  titleUrl   — YouTube video URL (str)\n"
            "  time       — ISO 8601 timestamp (str, e.g. '2024-01-15T10:30:00Z')\n"
            '  subtitles  — array with channel info, e.g. [{"name": "Channel", ...}]\n'
        )
