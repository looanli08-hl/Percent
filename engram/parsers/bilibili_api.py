"""Fetch Bilibili watch history via API using user's cookie."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

from engram.models import ChunkType, DataChunk


HISTORY_API = "https://api.bilibili.com/x/web-interface/history/cursor"


def fetch_bilibili_history(cookie: str, max_pages: int = 50) -> list[DataChunk]:
    """Fetch all watch history from Bilibili API.

    Args:
        cookie: Browser cookie string from bilibili.com
        max_pages: Maximum number of pages to fetch (each page ~20 items)

    Returns:
        List of DataChunk objects with watch history
    """
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
    }

    chunks = []
    view_at = 0  # cursor for pagination
    business = ""

    for page in range(max_pages):
        params = {"view_at": view_at, "business": business} if view_at else {}

        try:
            resp = requests.get(HISTORY_API, headers=headers, params=params, timeout=10)
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            print(f"  Request failed on page {page + 1}: {e}")
            break

        if data.get("code") != 0:
            msg = data.get("message", "unknown error")
            if data.get("code") == -101:
                raise ValueError(
                    "Cookie expired or invalid. Please get a fresh cookie from your browser."
                )
            print(f"  API error: {msg}")
            break

        cursor = data.get("data", {}).get("cursor", {})
        items = data.get("data", {}).get("list", [])

        if not items:
            break

        for item in items:
            title = item.get("title", "")
            if not title or title == "已失效视频":
                continue

            author = item.get("author_name", "unknown")
            tag_name = item.get("tag_name", "unknown")
            duration = item.get("duration", 0)
            item_view_at = item.get("view_at", 0)

            timestamp = (
                datetime.fromtimestamp(item_view_at, tz=timezone.utc)
                if item_view_at
                else datetime.now(tz=timezone.utc)
            )

            content = f"Watched: {title} (by {author})"
            if duration:
                content += f" [{duration // 60}min]"

            chunks.append(
                DataChunk(
                    source="bilibili",
                    type=ChunkType.WATCH_HISTORY,
                    timestamp=timestamp,
                    content=content,
                    metadata={
                        "category": tag_name,
                        "author": author,
                        "duration_seconds": duration,
                        "title": title,
                    },
                )
            )

        # Update cursor for next page
        view_at = cursor.get("view_at", 0)
        business = cursor.get("business", "")

        if not view_at:
            break

        # Be polite to the API
        time.sleep(0.5)

    return chunks
