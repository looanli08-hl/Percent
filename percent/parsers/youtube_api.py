"""Fetch YouTube watch history via internal API using user's cookie."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import requests

from percent.models import ChunkType, DataChunk

# YouTube browse endpoint for watch history
_BROWSE_API = "https://www.youtube.com/youtubei/v1/browse"

_INNERTUBE_CONTEXT = {
    "client": {
        "clientName": "WEB",
        "clientVersion": "2.20250101.00.00",
        "hl": "en",
        "gl": "US",
    }
}


def fetch_youtube_history(cookie: str, max_pages: int = 20) -> list[DataChunk]:
    """Fetch YouTube watch history using browser cookie.

    Args:
        cookie: Browser cookie string from youtube.com (must include SID, HSID, SSID)
        max_pages: Maximum continuation pages to fetch

    Returns:
        List of DataChunk objects with watch history
    """
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Origin": "https://www.youtube.com",
        "Referer": "https://www.youtube.com/feed/history",
    }

    # Extract SAPISID for authorization header
    sapisidhash = _generate_sapisidhash(cookie)
    if sapisidhash:
        headers["Authorization"] = f"SAPISIDHASH {sapisidhash}"

    chunks: list[DataChunk] = []
    continuation = None

    for page in range(max_pages):
        try:
            payload: dict = {"context": _INNERTUBE_CONTEXT}
            if continuation:
                payload["continuation"] = continuation
            else:
                payload["browseId"] = "FEhistory"

            resp = requests.post(_BROWSE_API, json=payload, headers=headers, timeout=15)
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            print(f"  Request failed on page {page + 1}: {e}")
            break

        # Check for auth errors
        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            raise ValueError(f"YouTube API error: {error_msg}. Cookie may be expired.")

        # Parse items and continuation
        items, next_cont = _extract_items(data, page == 0)

        for item in items:
            chunk = _item_to_chunk(item)
            if chunk:
                chunks.append(chunk)

        if not next_cont:
            break
        continuation = next_cont

        time.sleep(0.5)  # Rate limiting

    return chunks


def _generate_sapisidhash(cookie: str) -> str | None:
    """Generate SAPISIDHASH from cookie for YouTube API auth."""
    import hashlib

    # Extract SAPISID or __Secure-3PAPISID
    sapisid = None
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith("SAPISID="):
            sapisid = part.split("=", 1)[1]
        elif part.startswith("__Secure-3PAPISID="):
            sapisid = part.split("=", 1)[1]

    if not sapisid:
        return None

    timestamp = str(int(time.time()))
    origin = "https://www.youtube.com"
    hash_input = f"{timestamp} {sapisid} {origin}"
    hash_value = hashlib.sha1(hash_input.encode()).hexdigest()
    return f"{timestamp}_{hash_value}"


def _extract_items(data: dict, first_page: bool) -> tuple[list[dict], str | None]:
    """Extract video items and continuation token from API response."""
    items: list[dict] = []
    continuation: str | None = None

    if first_page:
        # First page: browse response
        tabs = data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
        for tab in tabs:
            section_contents = (
                tab.get("tabRenderer", {})
                .get("content", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            for section in section_contents:
                shelf = section.get("itemSectionRenderer", {})
                for item in shelf.get("contents", []):
                    if "videoRenderer" in item:
                        items.append(item["videoRenderer"])
                # Check for continuation
                for cont in shelf.get("continuations", []):
                    token = cont.get("nextContinuationData", {}).get("continuation")
                    if token:
                        continuation = token
    else:
        # Continuation page
        actions = data.get("onResponseReceivedActions", [])
        for action in actions:
            append = action.get("appendContinuationItemsAction", {})
            for item in append.get("continuationItems", []):
                if "videoRenderer" in item:
                    items.append(item["videoRenderer"])
                elif "continuationItemRenderer" in item:
                    endpoint = (
                        item["continuationItemRenderer"]
                        .get("continuationEndpoint", {})
                        .get("continuationCommand", {})
                    )
                    continuation = endpoint.get("token")

    return items, continuation


def _item_to_chunk(item: dict) -> DataChunk | None:
    """Convert a videoRenderer item to a DataChunk."""
    title = ""
    title_runs = item.get("title", {}).get("runs", [])
    if title_runs:
        title = title_runs[0].get("text", "")
    if not title:
        title = item.get("title", {}).get("simpleText", "")

    if not title:
        return None

    # Channel
    channel = ""
    channel_runs = item.get("shortBylineText", {}).get("runs", [])
    if channel_runs:
        channel = channel_runs[0].get("text", "")

    # Video ID
    video_id = item.get("videoId", "")

    # Build content
    parts = [f"Watched: {title}"]
    if channel:
        parts.append(f"by {channel}")
    content = " ".join(parts)

    metadata: dict = {}
    if channel:
        metadata["channel"] = channel
    if video_id:
        metadata["url"] = f"https://www.youtube.com/watch?v={video_id}"

    return DataChunk(
        source="youtube",
        type=ChunkType.WATCH_HISTORY,
        timestamp=datetime.now(tz=timezone.utc),
        content=content,
        metadata=metadata,
    )
