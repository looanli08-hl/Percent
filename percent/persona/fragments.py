from __future__ import annotations

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
                created_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def add(self, fragment: Fragment) -> Fragment:
        cursor = self._conn.execute(
            "INSERT INTO fragments (category, content, confidence, source, embedding, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                fragment.category.value,
                fragment.content,
                fragment.confidence,
                fragment.source,
                json.dumps(fragment.embedding),
                fragment.created_at.isoformat(),
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
