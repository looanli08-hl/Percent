from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser as _HTMLParser
from pathlib import Path

from engram.models import ChunkType, DataChunk
from engram.parsers.base import DataParser

_WATCHED_PREFIX = "Watched "


class YouTubeParser(DataParser):
    name = "youtube"
    description = "Parses YouTube watch history from Google Takeout (JSON or HTML)."

    def validate(self, path: Path) -> bool:
        """Return True if path is a JSON or HTML YouTube history file."""
        if not path.is_file():
            return False
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return isinstance(data, list)
            except (json.JSONDecodeError, OSError):
                return False
        if suffix in (".html", ".htm"):
            try:
                text = path.read_text(encoding="utf-8")
                return "youtube.com/watch" in text
            except OSError:
                return False
        return False

    def parse(self, path: Path) -> list[DataChunk]:
        """Parse Google Takeout YouTube watch-history (JSON or HTML) into DataChunks."""
        if path.suffix.lower() in (".html", ".htm"):
            return self._parse_html(path)
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

    def _parse_html(self, path: Path) -> list[DataChunk]:
        """Parse Google Takeout YouTube watch-history HTML into DataChunks."""

        class _Parser(_HTMLParser):
            def __init__(self):
                super().__init__()
                self.items: list[dict] = []
                self._cur: dict = {}
                self._in_content = False
                self._in_link = False
                self._buf = ""

            def handle_starttag(self, tag, attrs):
                ad = dict(attrs)
                if tag == "div" and "content-cell" in ad.get("class", ""):
                    self._in_content = True
                    self._cur = {}
                if self._in_content and tag == "a":
                    self._in_link = True
                    href = ad.get("href", "")
                    if "youtube.com/watch" in href and "url" not in self._cur:
                        self._cur["url"] = href
                    elif ("youtube.com/channel" in href or "youtube.com/@" in href) \
                            and "channel" not in self._cur:
                        self._cur["_channel_link"] = True

            def handle_data(self, data):
                d = data.strip()
                if not d or not self._in_content:
                    return
                if self._in_link:
                    if "url" in self._cur and "title" not in self._cur:
                        self._cur["title"] = d
                    elif self._cur.get("_channel_link") and "channel" not in self._cur:
                        self._cur["channel"] = d
                        del self._cur["_channel_link"]
                else:
                    # Timestamp lines like "2026年4月5日 UTC+8 下午11:00:00"
                    if re.search(r"\d{4}", d) and ("UTC" in d or "年" in d or "," in d):
                        self._cur["time_str"] = d

            def handle_endtag(self, tag):
                if tag == "a":
                    self._in_link = False
                if tag == "div" and self._in_content and self._cur.get("title"):
                    self.items.append(self._cur)
                    self._cur = {}
                    self._in_content = False

        p = _Parser()
        p.feed(path.read_text(encoding="utf-8"))

        chunks: list[DataChunk] = []
        for item in p.items:
            title = item.get("title", "")
            channel = item.get("channel", "")
            url = item.get("url", "")

            parts = [f"Watched: {title}"]
            if channel:
                parts.append(f"by {channel}")
            content = " ".join(parts)

            metadata: dict = {}
            if channel:
                metadata["channel"] = channel
            if url:
                metadata["url"] = url

            chunks.append(DataChunk(
                source="youtube",
                type=ChunkType.WATCH_HISTORY,
                timestamp=datetime.now(tz=UTC),
                content=content,
                metadata=metadata,
            ))

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
