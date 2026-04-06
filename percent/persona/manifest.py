"""Import manifest — tracks what was imported, when, and what it produced."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


class ImportManifest:
    """Append-only import history stored as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: list[dict] = []
        if path.exists():
            try:
                self._entries = json.loads(
                    path.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                self._entries = []

    def record(
        self,
        source: str,
        file_path: str | None = None,
        file_hash: str | None = None,
        chunks_parsed: int = 0,
        fragments_before: int = 0,
        fragments_after: int = 0,
        artifacts: list[str] | None = None,
    ) -> dict:
        """Record an import event."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "file_path": file_path,
            "file_hash": file_hash,
            "chunks_parsed": chunks_parsed,
            "fragments_before": fragments_before,
            "fragments_after": fragments_after,
            "new_fragments": fragments_after - fragments_before,
            "artifacts": artifacts or [],
        }
        self._entries.append(entry)
        self._save()
        return entry

    def get_all(self) -> list[dict]:
        """Return all import entries."""
        return list(self._entries)

    def summary(self) -> dict:
        """Return a summary of all imports."""
        if not self._entries:
            return {
                "total_imports": 0,
                "sources": [],
                "total_chunks": 0,
            }
        sources = list(
            {e["source"] for e in self._entries}
        )
        total_chunks = sum(
            e.get("chunks_parsed", 0) for e in self._entries
        )
        return {
            "total_imports": len(self._entries),
            "sources": sources,
            "total_chunks": total_chunks,
            "first_import": self._entries[0]["timestamp"],
            "last_import": self._entries[-1]["timestamp"],
        }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                self._entries, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )

    @staticmethod
    def hash_file(path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
