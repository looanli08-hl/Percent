"""Fetch Telegram chat history via Telethon API."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from percent.models import ChunkType, DataChunk


async def _fetch_history(
    api_id: int,
    api_hash: str,
    phone: str,
    max_messages: int = 5000,
    session_path: Path | None = None,
) -> list[DataChunk]:
    """Fetch personal chats from Telegram using Telethon.

    Requires: pip install telethon
    """
    try:
        from telethon import TelegramClient
        from telethon.tl.types import User
    except ImportError:
        raise ImportError(
            "Telethon is required for Telegram auto-import.\n"
            "Install it: pip install telethon"
        )

    session = str(session_path or "percent_telegram")
    client = TelegramClient(session, api_id, api_hash)

    await client.start(phone=phone)

    me = await client.get_me()
    my_id = me.id

    chunks: list[DataChunk] = []
    msg_count = 0

    # Get recent dialogs (personal chats only)
    async for dialog in client.iter_dialogs(limit=50):
        if not isinstance(dialog.entity, User):
            continue
        if dialog.entity.bot:
            continue

        contact_name = _get_display_name(dialog.entity)
        batch: list[str] = []
        batch_timestamps: list[datetime] = []

        async for message in client.iter_messages(dialog.entity, limit=200):
            if not message.text:
                continue

            sender = "[我]" if message.sender_id == my_id else f"[{contact_name}]"
            batch.append(f"{sender} {message.text}")
            batch_timestamps.append(message.date.replace(tzinfo=timezone.utc))
            msg_count += 1

            if msg_count >= max_messages:
                break

        if batch:
            # Group into chunks of ~50 messages
            for i in range(0, len(batch), 50):
                segment = batch[i : i + 50]
                ts = batch_timestamps[i] if i < len(batch_timestamps) else datetime.now(tz=timezone.utc)
                chunks.append(
                    DataChunk(
                        source="telegram",
                        type=ChunkType.CONVERSATION,
                        timestamp=ts,
                        content="\n".join(segment),
                        metadata={"contact": contact_name},
                    )
                )

        if msg_count >= max_messages:
            break

    await client.disconnect()
    return chunks


def _get_display_name(user: object) -> str:
    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    name = f"{first} {last}".strip()
    return name or getattr(user, "username", "") or "Unknown"


def fetch_telegram_history(
    api_id: int,
    api_hash: str,
    phone: str,
    max_messages: int = 5000,
    session_path: Path | None = None,
) -> list[DataChunk]:
    """Synchronous wrapper for Telegram history fetch."""
    return asyncio.run(
        _fetch_history(api_id, api_hash, phone, max_messages, session_path)
    )
