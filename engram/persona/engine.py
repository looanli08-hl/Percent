from __future__ import annotations

from pathlib import Path

from sentence_transformers import SentenceTransformer

from engram.llm.client import LLMClient
from engram.models import DataChunk, Finding, Fragment
from engram.persona.extractor import PersonaExtractor
from engram.persona.fragments import FragmentStore
from engram.persona.synthesizer import PersonaSynthesizer
from engram.persona.validator import PersonaValidator

_DEFAULT_MODEL = "all-MiniLM-L6-v2"


class PersonaEngine:
    """
    Orchestrates the full persona pipeline:
      extract → embed → store → synthesize → (optionally) validate
    """

    def __init__(
        self,
        client: LLMClient,
        engram_dir: Path,
        prompts_dir: Path | None = None,
        embedding_model: str = _DEFAULT_MODEL,
        batch_size: int = 20,
    ) -> None:
        self.client = client
        self.engram_dir = engram_dir
        self._core_path = engram_dir / "core.md"

        self._extractor = PersonaExtractor(client, prompts_dir=prompts_dir, batch_size=batch_size)
        self._synthesizer = PersonaSynthesizer(client, prompts_dir=prompts_dir)
        self._validator = PersonaValidator(client, prompts_dir=prompts_dir)

        db_path = engram_dir / "fragments.db"
        self._store = FragmentStore(db_path)

        self._embedder: SentenceTransformer = SentenceTransformer(embedding_model)

    # ── public API ──────────────────────────────────────────────────────────

    def run(self, chunks: list[DataChunk], validate: bool = True) -> str:
        """
        Full pipeline:
          1. Extract findings from chunks
          2. Embed each finding and store as a Fragment
          3. Synthesize core.md from all stored fragments
          4. Optionally validate against the input chunks

        Returns the core.md content as a string.
        """
        # 1. Extract
        findings = self._extractor.extract(chunks)

        # 2. Embed + store
        for finding in findings:
            embedding = self._embedder.encode(finding.content).tolist()
            fragment = Fragment(
                category=finding.category,
                content=finding.content,
                confidence=finding.confidence,
                source=finding.source,
                embedding=embedding,
            )
            self._store.add(fragment)

        # 3. Synthesize — build findings list from all stored fragments for
        #    consistency (in case prior fragments exist too)
        all_findings = self._fragments_to_findings(self._store.get_all())
        core_md = self._synthesizer.synthesize_and_save(all_findings, self._core_path)

        # 4. Validate
        if validate and chunks:
            self._validator.validate(core_md, test_chunks=chunks[:5])

        return core_md

    def rebuild_core(self) -> str:
        """Re-synthesize core.md from all stored fragments (no new extraction)."""
        all_findings = self._fragments_to_findings(self._store.get_all())
        return self._synthesizer.synthesize_and_save(all_findings, self._core_path)

    def stats(self) -> dict:
        """Return fragment store statistics."""
        return self._store.stats()

    def embed_query(self, text: str) -> list[float]:
        """Encode *text* for vector search against the fragment store."""
        return self._embedder.encode(text).tolist()

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _fragments_to_findings(fragments: list[Fragment]) -> list[Finding]:
        from engram.models import Finding

        return [
            Finding(
                category=f.category,
                content=f.content,
                confidence=f.confidence,
                source=f.source,
                evidence="(stored fragment)",
            )
            for f in fragments
        ]
