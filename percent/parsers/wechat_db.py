"""Parse decrypted WeChat 4.x SQLite databases directly."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import zstandard

from percent.models import ChunkType, DataChunk
from percent.parsers.base import DataParser

# wxid that owns this database (rowid=1 in Name2Id)
_SELF_ROWID = 1

# Regex to extract wxid prefix from group chat message content:
# Group messages are stored as "wxid_xxx:\nactual message"
_GROUP_MSG_PREFIX = re.compile(r"^(\S+?):\n(.+)$", re.DOTALL)


class WeChatDBParser(DataParser):
    name = "wechat-db"
    description = "Decrypted WeChat 4.x SQLite databases (from wechat-decrypt)"

    def validate(self, path: Path) -> bool:
        try:
            if path.is_dir():
                msg_dir = path / "message"
                if not msg_dir.exists():
                    msg_dir = path
                return any(f.suffix == ".db" and "message" in f.name for f in msg_dir.iterdir())
            return path.suffix == ".db"
        except Exception:
            return False

    def parse(self, path: Path) -> list[DataChunk]:
        if path.is_dir():
            msg_dir = path / "message"
            if not msg_dir.exists():
                msg_dir = path
            db_files = sorted(msg_dir.glob("message_*.db"))
        else:
            db_files = [path]

        # Load contact name mappings
        contact_names = self._load_contacts(path)        # MD5(wxid) -> display_name
        contacts_by_wxid = self._load_contacts_by_wxid(path)  # wxid -> display_name

        all_messages: list[dict] = []
        for db_file in db_files:
            all_messages.extend(self._extract_from_db(db_file, contact_names, contacts_by_wxid))

        chunks = self._group_messages(all_messages)

        # Parse Moments posts
        if path.is_dir():
            moments_chunks = self._parse_moments(path, contacts_by_wxid)
            chunks.extend(moments_chunks)

        # Report voice messages that are present but not yet transcribed
        if path.is_dir():
            voice_count = self._count_voice_messages(path)
            if voice_count > 0:
                print(
                    f"  Note: {voice_count} voice messages found in media_0.db — "
                    "transcription not yet supported (future feature)."
                )

        return chunks

    # ------------------------------------------------------------------
    # Contact loading
    # ------------------------------------------------------------------

    def _load_contacts(self, path: Path) -> dict[str, str]:
        """Build mapping from MD5(username) -> display name."""
        contact_db = None
        if path.is_dir():
            candidate = path / "contact" / "contact.db"
            if candidate.exists():
                contact_db = candidate
        if not contact_db:
            return {}

        name_map: dict[str, str] = {}
        try:
            conn = sqlite3.connect(str(contact_db))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT username, remark, nick_name FROM contact "
                "WHERE username IS NOT NULL AND username != ''"
            ).fetchall()
            for row in rows:
                username = row["username"]
                display = row["remark"] or row["nick_name"] or username
                md5_hash = hashlib.md5(username.encode()).hexdigest()
                name_map[md5_hash] = display
            conn.close()
        except Exception:
            pass
        return name_map

    def _load_contacts_by_wxid(self, path: Path) -> dict[str, str]:
        """Build mapping from wxid -> display name for sender identification."""
        if not path.is_dir():
            return {}
        contact_db = path / "contact" / "contact.db"
        if not contact_db.exists():
            return {}

        mapping: dict[str, str] = {}
        try:
            conn = sqlite3.connect(str(contact_db))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT username, remark, nick_name FROM contact "
                "WHERE username IS NOT NULL AND username != ''"
            ).fetchall()
            for row in rows:
                wxid = row["username"]
                name = row["remark"] or row["nick_name"] or wxid
                mapping[wxid] = name
            conn.close()
        except Exception:
            pass
        return mapping

    # ------------------------------------------------------------------
    # Message extraction
    # ------------------------------------------------------------------

    def _find_self_rowid(self, conn: sqlite3.Connection) -> int:
        """Find the user's own rowid in Name2Id (always rowid=1 for the owner)."""
        try:
            rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
            for row in rows:
                if row["rowid"] == 1:
                    return 1
        except Exception:
            pass
        return 1

    def _build_rowid_to_name(
        self,
        conn: sqlite3.Connection,
        contacts_by_wxid: dict[str, str],
    ) -> dict[int, str]:
        """Build rowid -> display_name mapping via Name2Id + contact.db."""
        rowid_to_name: dict[int, str] = {}
        try:
            rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
            for row in rows:
                wxid = row["user_name"] or ""
                display = contacts_by_wxid.get(wxid) or wxid[:20] or "unknown"
                rowid_to_name[row["rowid"]] = display
        except Exception:
            pass
        return rowid_to_name

    def _extract_from_db(
        self,
        db_path: Path,
        contact_names: dict[str, str] | None = None,
        contacts_by_wxid: dict[str, str] | None = None,
    ) -> list[dict]:
        messages = []
        contact_names = contact_names or {}
        contacts_by_wxid = contacts_by_wxid or {}

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            self_id = self._find_self_rowid(conn)
            rowid_to_name = self._build_rowid_to_name(conn, contacts_by_wxid)

            # Build hash -> (rowid, user_name) for table identification
            hash_to_user: dict[str, tuple[int, str]] = {}
            try:
                rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
                for row in rows:
                    uname = row["user_name"] or ""
                    if uname:
                        h = hashlib.md5(uname.encode()).hexdigest()
                        hash_to_user[h] = (row["rowid"], uname)
            except Exception:
                pass

            # Get all Msg_ tables
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"
            ).fetchall()

            dctx = zstandard.ZstdDecompressor()

            for table_row in tables:
                table_name = table_row["name"]
                table_hash = table_name.replace("Msg_", "")
                is_group_chat = False

                # Determine talker display name and whether this is a group chat
                if table_hash in hash_to_user:
                    _rowid, user_name = hash_to_user[table_hash]
                    is_group_chat = "@chatroom" in user_name
                    talker_name = contact_names.get(table_hash, user_name)
                else:
                    talker_name = contact_names.get(table_hash, table_hash[:12])

                try:
                    rows = conn.execute(f"""
                        SELECT create_time, local_type, message_content,
                               WCDB_CT_message_content, real_sender_id
                        FROM [{table_name}]
                        WHERE local_type = 1
                          AND message_content IS NOT NULL
                        ORDER BY create_time
                    """).fetchall()

                    for row in rows:
                        raw = row["message_content"]
                        ct = row["WCDB_CT_message_content"]

                        # Decompress zstd if needed
                        if ct and ct != 0 and isinstance(raw, bytes):
                            try:
                                if raw[:4] == b"\x28\xb5\x2f\xfd":
                                    content = dctx.decompress(raw).decode("utf-8")
                                else:
                                    continue
                            except Exception:
                                continue
                        elif isinstance(raw, str):
                            content = raw
                        else:
                            continue

                        if not content:
                            continue
                        if content.startswith("<") or content.startswith("<?"):
                            continue
                        content = content.strip()
                        if len(content) < 2:
                            continue

                        sender_id = row["real_sender_id"]
                        is_self = sender_id == self_id

                        # Determine sender display name
                        if is_self:
                            sender_name = "我"
                        elif is_group_chat:
                            # Group chat messages have "wxid:\ncontent" prefix
                            m = _GROUP_MSG_PREFIX.match(content)
                            if m:
                                sender_wxid = m.group(1)
                                content = m.group(2).strip()
                                sender_name = contacts_by_wxid.get(sender_wxid, sender_wxid[:20])
                            else:
                                # Fall back to rowid lookup
                                sender_name = rowid_to_name.get(sender_id, "群成员")
                        else:
                            # 1-on-1 chat: use the talker name
                            sender_name = talker_name

                        if not content or len(content) < 2:
                            continue

                        messages.append({
                            "talker": talker_name,
                            "content": content,
                            "timestamp": row["create_time"] or 0,
                            "is_self": is_self,
                            "sender_name": sender_name,
                        })
                except Exception:
                    continue

            conn.close()
        except Exception as e:
            print(f"  Warning: could not read {db_path}: {e}")

        return messages

    # ------------------------------------------------------------------
    # Message grouping into conversation chunks
    # ------------------------------------------------------------------

    def _group_messages(self, messages: list[dict]) -> list[DataChunk]:
        by_talker: dict[str, list[dict]] = defaultdict(list)
        for msg in messages:
            by_talker[msg["talker"]].append(msg)

        chunks = []
        for talker, msgs in by_talker.items():
            msgs.sort(key=lambda m: m["timestamp"])

            # Skip conversations with no messages from self
            if not any(m.get("is_self", False) for m in msgs):
                continue

            # Group into conversation windows (30 min gap)
            windows: list[list[dict]] = []
            current: list[dict] = [msgs[0]] if msgs else []
            for i in range(1, len(msgs)):
                if msgs[i]["timestamp"] - msgs[i - 1]["timestamp"] > 1800:
                    if current:
                        windows.append(current)
                    current = []
                current.append(msgs[i])
            if current:
                windows.append(current)

            for window in windows:
                # Only include windows where the user actually spoke
                if not any(m.get("is_self", False) for m in window):
                    continue

                lines = []
                for m in window:
                    if m.get("is_self", False):
                        prefix = "[我]"
                    else:
                        prefix = f"[{m.get('sender_name', talker)}]"
                    lines.append(f"{prefix} {m['content']}")
                content = "\n".join(lines)

                self_count = sum(1 for m in window if m.get("is_self", False))
                ts = window[0]["timestamp"]
                timestamp = (
                    datetime.fromtimestamp(ts, tz=UTC)
                    if ts
                    else datetime.now(tz=UTC)
                )
                chunks.append(DataChunk(
                    source="wechat",
                    type=ChunkType.CONVERSATION,
                    timestamp=timestamp,
                    content=content,
                    metadata={
                        "talker": talker,
                        "message_count": len(window),
                        "self_message_count": self_count,
                    },
                ))

        return chunks

    # ------------------------------------------------------------------
    # Moments (朋友圈) parsing
    # ------------------------------------------------------------------

    def _parse_moments(
        self,
        path: Path,
        contacts_by_wxid: dict[str, str],
    ) -> list[DataChunk]:
        """Parse the user's own Moments posts from sns/sns.db."""
        sns_db = path / "sns" / "sns.db"
        if not sns_db.exists():
            return []

        # Identify the user's own wxid from Name2Id (rowid=1)
        self_wxid = self._find_self_wxid(path)

        chunks: list[DataChunk] = []
        try:
            conn = sqlite3.connect(str(sns_db))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT user_name, content FROM SnsTimeLine "
                "WHERE user_name = ?",
                (self_wxid,),
            ).fetchall()

            for row in rows:
                xml_content = row["content"]
                if not xml_content:
                    continue

                text, create_time = self._parse_sns_xml(xml_content)
                if not text:
                    continue

                ts = create_time or 0
                timestamp = (
                    datetime.fromtimestamp(ts, tz=UTC)
                    if ts
                    else datetime.now(tz=UTC)
                )
                chunks.append(DataChunk(
                    source="wechat-moments",
                    type=ChunkType.POST,
                    timestamp=timestamp,
                    content=text,
                    metadata={
                        "platform": "wechat-moments",
                        "author_wxid": self_wxid,
                    },
                ))
            conn.close()
        except Exception as e:
            print(f"  Warning: could not parse Moments from {sns_db}: {e}")

        return chunks

    def _parse_sns_xml(self, xml_str: str) -> tuple[str, int]:
        """Extract (contentDesc, createTime) from a SnsTimeLine XML blob."""
        try:
            root = ET.fromstring(xml_str)
            timeline = root.find("TimelineObject")
            if timeline is None:
                timeline = root  # Some rows wrap directly

            text_el = timeline.find("contentDesc")
            time_el = timeline.find("createTime")

            text = (text_el.text or "").strip() if text_el is not None else ""
            create_time = int(time_el.text) if time_el is not None and time_el.text else 0
            return text, create_time
        except Exception:
            return "", 0

    def _find_self_wxid(self, path: Path) -> str:
        """Retrieve the owner's wxid from message/message_0.db Name2Id rowid=1."""
        msg_db = path / "message" / "message_0.db"
        if not msg_db.exists():
            return ""
        try:
            conn = sqlite3.connect(str(msg_db))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT user_name FROM Name2Id WHERE rowid = 1"
            ).fetchone()
            conn.close()
            if row:
                return row["user_name"] or ""
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------
    # Voice message awareness
    # ------------------------------------------------------------------

    def _count_voice_messages(self, path: Path) -> int:
        """Return the count of voice messages in media_0.db (not yet transcribed)."""
        media_db = path / "message" / "media_0.db"
        if not media_db.exists():
            return 0
        try:
            conn = sqlite3.connect(str(media_db))
            count = conn.execute("SELECT COUNT(*) FROM VoiceInfo").fetchone()[0]
            conn.close()
            return int(count)
        except Exception:
            return 0

    # ------------------------------------------------------------------

    def get_import_guide(self) -> str:
        return (
            "WeChat 4.x decrypted database import:\n"
            "1. Use wechat-decrypt (github.com/ylytdeng/wechat-decrypt) to decrypt\n"
            "2. Run: python main.py decrypt\n"
            "3. Copy the 'decrypted' folder to your Mac\n"
            "4. Run: percent import run wechat-db /path/to/decrypted"
        )
