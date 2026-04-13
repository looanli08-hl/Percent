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
                content_hash TEXT,
                evidence TEXT DEFAULT ''
            )
        """)
        # Add content_hash column if missing (migration for existing DBs)
        try:
            self._conn.execute("SELECT content_hash FROM fragments LIMIT 1")
        except sqlite3.OperationalError:
            self._conn.execute("ALTER TABLE fragments ADD COLUMN content_hash TEXT")
            self._conn.commit()
        # Add evidence column if missing (migration)
        try:
            self._conn.execute("SELECT evidence FROM fragments LIMIT 1")
        except sqlite3.OperationalError:
            self._conn.execute("ALTER TABLE fragments ADD COLUMN evidence TEXT DEFAULT ''")
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

    # Semantic similarity threshold — fragments above this are considered duplicates
    DEDUP_SIMILARITY_THRESHOLD = 0.85

    def add(self, fragment: Fragment) -> Fragment:
        content_hash = self._hash_content(fragment.content, fragment.source)

        # Skip if exact duplicate content from same source already exists
        existing = self._conn.execute(
            "SELECT id FROM fragments WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if existing:
            fragment.id = existing[0]
            return fragment

        # Semantic dedup: check if a similar fragment from the same source exists
        if fragment.embedding:
            merged = self._try_merge_similar(fragment)
            if merged:
                return merged

        cursor = self._conn.execute(
            "INSERT INTO fragments (category, content, confidence,"
            " source, embedding, created_at, content_hash, evidence)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fragment.category.value,
                fragment.content,
                fragment.confidence,
                fragment.source,
                json.dumps(fragment.embedding),
                fragment.created_at.isoformat(),
                content_hash,
                getattr(fragment, 'evidence', ''),
            ),
        )
        self._conn.commit()
        fragment.id = cursor.lastrowid
        return fragment

    def _try_merge_similar(self, fragment: Fragment) -> Fragment | None:
        """If a semantically similar fragment from the same source exists, keep the better one."""
        rows = self._conn.execute(
            "SELECT * FROM fragments WHERE source = ?", (fragment.source,)
        ).fetchall()

        if not rows:
            return None

        new_vec = np.array(fragment.embedding)
        norm_new = np.linalg.norm(new_vec)
        if norm_new == 0:
            return None

        for row in rows:
            existing_emb = np.array(json.loads(row["embedding"]))
            if len(existing_emb) != len(new_vec):
                continue
            norm_existing = np.linalg.norm(existing_emb)
            if norm_existing == 0:
                continue
            similarity = float(np.dot(new_vec, existing_emb) / (norm_new * norm_existing))

            if similarity >= self.DEDUP_SIMILARITY_THRESHOLD:
                # Keep the one with more content (more specific), break ties by confidence
                existing_frag = self._row_to_fragment(row)
                if len(fragment.content) > len(existing_frag.content) or (
                    len(fragment.content) == len(existing_frag.content)
                    and fragment.confidence > existing_frag.confidence
                ):
                    # New one is better — replace existing
                    new_hash = self._hash_content(fragment.content, fragment.source)
                    self._conn.execute(
                        "UPDATE fragments SET content = ?, confidence = ?, "
                        "embedding = ?, content_hash = ?, evidence = ? WHERE id = ?",
                        (
                            fragment.content,
                            fragment.confidence,
                            json.dumps(fragment.embedding),
                            new_hash,
                            getattr(fragment, 'evidence', ''),
                            row["id"],
                        ),
                    )
                    self._conn.commit()
                    fragment.id = row["id"]
                else:
                    # Existing one is better — skip new
                    fragment.id = row["id"]
                return fragment

        return None

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
            evidence=row["evidence"] if "evidence" in row.keys() else "",
            embedding=json.loads(row["embedding"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get_cross_source_insights(self, similarity_threshold: float = 0.75) -> list[dict]:
        """Group similar fragments across data sources into cross-validated insights."""
        fragments = self.get_all()
        if not fragments:
            return []

        # Build embeddings matrix
        embeddings = []
        for f in fragments:
            if f.embedding:
                embeddings.append(np.array(f.embedding))
            else:
                embeddings.append(np.zeros(384))

        # Group fragments by similarity
        used = set()
        insights = []

        for i, frag in enumerate(fragments):
            if i in used:
                continue

            group = [frag]
            used.add(i)
            sources = {frag.source}

            # Find similar fragments from OTHER sources
            for j, other in enumerate(fragments):
                if j in used or other.source == frag.source:
                    continue
                if len(embeddings[i]) != len(embeddings[j]):
                    continue
                norm_i = np.linalg.norm(embeddings[i])
                norm_j = np.linalg.norm(embeddings[j])
                if norm_i == 0 or norm_j == 0:
                    continue
                sim = float(np.dot(embeddings[i], embeddings[j]) / (norm_i * norm_j))
                if sim >= similarity_threshold:
                    group.append(other)
                    used.add(j)
                    sources.add(other.source)

            # Build insight
            # Use highest-confidence fragment as the main content
            group.sort(key=lambda f: f.confidence, reverse=True)
            main = group[0]

            evidence_by_source = {}
            for f in group:
                if f.source not in evidence_by_source:
                    evidence_by_source[f.source] = []
                evidence_by_source[f.source].append({
                    "content": f.content,
                    "evidence": f.evidence,
                    "confidence": f.confidence,
                })

            # Cross-source boost: more sources = higher confidence
            base_conf = main.confidence
            source_boost = min(len(sources) * 0.05, 0.15)
            boosted_conf = min(base_conf + source_boost, 1.0)

            insights.append({
                "content": main.content,
                "category": main.category.value,
                "confidence": round(boosted_conf, 2),
                "source_count": len(sources),
                "sources": evidence_by_source,
            })

        # Sort by confidence descending, then by source_count
        insights.sort(key=lambda x: (x["source_count"], x["confidence"]), reverse=True)
        return insights

    def close(self) -> None:
        self._conn.close()
