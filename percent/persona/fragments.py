from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np

from percent.models import FindingCategory, Fragment


class FragmentStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS fragments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,
                embedding TEXT NOT NULL,
                created_at TEXT NOT NULL,
                content_hash TEXT
            )
        """)
        # Add content_hash column if missing (migration for existing DBs)
        try:
            self._conn.execute("SELECT content_hash FROM fragments LIMIT 1")
        except sqlite3.OperationalError:
            self._conn.execute("ALTER TABLE fragments ADD COLUMN content_hash TEXT")
            self._conn.commit()

        # Backfill NULL content_hash on existing rows
        null_rows = self._conn.execute(
            "SELECT id, content, source FROM fragments WHERE content_hash IS NULL"
        ).fetchall()
        for row in null_rows:
            h = self._hash_content(row["content"], row["source"])
            self._conn.execute("UPDATE fragments SET content_hash = ? WHERE id = ?", (h, row["id"]))
        if null_rows:
            self._conn.commit()

    @staticmethod
    def _hash_content(content: str, source: str) -> str:
        return hashlib.sha256(f"{source}:{content}".encode()).hexdigest()

    def add(self, fragment: Fragment) -> Fragment:
        content_hash = self._hash_content(fragment.content, fragment.source)

        # Skip if duplicate content from same source already exists
        existing = self._conn.execute(
            "SELECT id FROM fragments WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if existing:
            fragment.id = existing[0]
            return fragment

        cursor = self._conn.execute(
            "INSERT INTO fragments (category, content, confidence,"
            " source, embedding, created_at, content_hash)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                fragment.category.value,
                fragment.content,
                fragment.confidence,
                fragment.source,
                json.dumps(fragment.embedding),
                fragment.created_at.isoformat(),
                content_hash,
            ),
        )
        self._conn.commit()
        fragment.id = cursor.lastrowid
        return fragment

    def get(self, fragment_id: int) -> Fragment:
        row = self._conn.execute("SELECT * FROM fragments WHERE id = ?", (fragment_id,)).fetchone()
        if row is None:
            raise ValueError(f"Fragment {fragment_id} not found")
        return self._row_to_fragment(row)

    def get_all(self) -> list[Fragment]:
        rows = self._conn.execute("SELECT * FROM fragments").fetchall()
        return [self._row_to_fragment(row) for row in rows]

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[Fragment]:
        rows = self._conn.execute("SELECT * FROM fragments").fetchall()
        if not rows:
            return []

        query_vec = np.array(query_embedding)
        scored = []
        for row in rows:
            emb = np.array(json.loads(row["embedding"]))
            if len(emb) != len(query_vec):
                continue
            norm_q = np.linalg.norm(query_vec)
            norm_e = np.linalg.norm(emb)
            if norm_q == 0 or norm_e == 0:
                continue
            similarity = float(np.dot(query_vec, emb) / (norm_q * norm_e))
            scored.append((similarity, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._row_to_fragment(row) for _, row in scored[:top_k]]

    def update_confidence(self, fragment_id: int, confidence: float) -> None:
        """Update the confidence score of a fragment."""
        self._conn.execute(
            "UPDATE fragments SET confidence = ? WHERE id = ?",
            (confidence, fragment_id),
        )
        self._conn.commit()

    def stats(self) -> dict:
        total = self._conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0]
        source_rows = self._conn.execute(
            "SELECT source, COUNT(*) as cnt FROM fragments GROUP BY source"
        ).fetchall()
        by_source = {row["source"]: row["cnt"] for row in source_rows}
        cat_rows = self._conn.execute(
            "SELECT category, COUNT(*) as cnt FROM fragments GROUP BY category"
        ).fetchall()
        by_category = {row["category"]: row["cnt"] for row in cat_rows}
        return {"total": total, "by_source": by_source, "by_category": by_category}

    def _row_to_fragment(self, row: sqlite3.Row) -> Fragment:
        from datetime import datetime

        return Fragment(
            id=row["id"],
            category=FindingCategory(row["category"]),
            content=row["content"],
            confidence=row["confidence"],
            source=row["source"],
            embedding=json.loads(row["embedding"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def close(self) -> None:
        self._conn.close()
