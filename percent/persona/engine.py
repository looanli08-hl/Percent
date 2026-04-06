from __future__ import annotations

from pathlib import Path

from sentence_transformers import SentenceTransformer

from percent.llm.client import LLMClient
from percent.models import DataChunk, Finding, Fragment
from percent.persona.cross_validate import (
    DeepAnalyzer,
    cross_validate_fragments,
)
from percent.persona.extractor import PersonaExtractor
from percent.persona.fragments import FragmentStore
from percent.persona.manifest import ImportManifest
from percent.persona.synthesizer import PersonaSynthesizer
from percent.persona.validator import PersonaValidator

_DEFAULT_MODEL = "all-MiniLM-L6-v2"


class PersonaEngine:
    """
    Orchestrates the full persona pipeline:
      extract → embed → store → synthesize → (optionally) validate
    """

    def __init__(
        self,
        client: LLMClient,
        percent_dir: Path,
        prompts_dir: Path | None = None,
        embedding_model: str = _DEFAULT_MODEL,
        batch_size: int = 20,
    ) -> None:
        self.client = client
        self.percent_dir = percent_dir
        self._core_path = percent_dir / "core.md"

        self._extractor = PersonaExtractor(client, prompts_dir=prompts_dir, batch_size=batch_size)
        self._synthesizer = PersonaSynthesizer(client, prompts_dir=prompts_dir)
        self._validator = PersonaValidator(client, prompts_dir=prompts_dir)
        self._deep_analyzer = DeepAnalyzer(client, prompts_dir=prompts_dir)

        db_path = percent_dir / "fragments.db"
        self._store = FragmentStore(db_path)

        self._embedder: SentenceTransformer = SentenceTransformer(
            embedding_model
        )
        self._manifest = ImportManifest(percent_dir / "imports.json")

    # ── public API ──────────────────────────────────────────────────────────

    def run(self, chunks: list[DataChunk], validate: bool = True) -> str:
        """
        Full pipeline:
          1. Extract findings from chunks
          2. Embed each finding and store as a Fragment
          3. Synthesize core.md from all stored fragments
          4. Generate behavioral fingerprint
          5. Optionally validate against the input chunks

        Returns the core.md content as a string.
        """
        # Track state for manifest
        fragments_before = self._store.stats().get("total", 0)
        sources = list({c.source for c in chunks})

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

        # 3. Synthesize
        all_findings = self._fragments_to_findings(self._store.get_all())
        core_md = self._synthesizer.synthesize_and_save(
            all_findings, self._core_path
        )

        # 4. Generate behavioral fingerprint
        self._generate_fingerprint(chunks)

        # 5. Record import manifest
        fragments_after = self._store.stats().get("total", 0)
        artifacts = ["core.md"]
        if (self.percent_dir / "fingerprint.json").exists():
            artifacts.append("fingerprint.json")
        for src in sources:
            self._manifest.record(
                source=src,
                chunks_parsed=len(
                    [c for c in chunks if c.source == src]
                ),
                fragments_before=fragments_before,
                fragments_after=fragments_after,
                artifacts=artifacts,
            )

        # 6. Validate
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

    def deep_analyze(self) -> str:
        """Run cross-validation + deep analysis on all stored fragments, then re-synthesize.

        1. Cross-validate: adjust confidence based on cross-source corroboration
        2. Deep analyze: LLM second pass to find deeper patterns and contradictions
        3. Store new deep findings as fragments
        4. Re-synthesize core.md with updated data

        Returns the new core.md content.
        """
        all_fragments = self._store.get_all()
        if not all_fragments:
            return ""

        # 1. Cross-validate — adjust confidence scores
        validated = cross_validate_fragments(all_fragments)

        # Update confidence in store
        for orig, updated in zip(all_fragments, validated):
            if orig.confidence != updated.confidence and orig.id is not None:
                self._store.update_confidence(orig.id, updated.confidence)

        # 2. Deep analysis — find deeper patterns
        all_findings = self._fragments_to_findings(validated)
        deep_findings = self._deep_analyzer.analyze(all_findings)

        # 3. Store deep findings as new fragments
        for finding in deep_findings:
            embedding = self._embedder.encode(finding.content).tolist()
            fragment = Fragment(
                category=finding.category,
                content=finding.content,
                confidence=finding.confidence,
                source=finding.source,
                embedding=embedding,
            )
            self._store.add(fragment)

        # 4. Re-synthesize with everything
        all_findings = self._fragments_to_findings(self._store.get_all())
        return self._synthesizer.synthesize_and_save(all_findings, self._core_path)

    def _generate_fingerprint(self, chunks: list[DataChunk]) -> None:
        """Generate behavioral fingerprint from chunks if applicable."""
        import json

        from percent.persona.fingerprint import analyze_fingerprint

        try:
            fp = analyze_fingerprint(chunks)
            fp_path = self.percent_dir / "fingerprint.json"
            fp_path.write_text(
                json.dumps(fp.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass  # Fingerprint is best-effort, don't block pipeline

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _fragments_to_findings(fragments: list[Fragment]) -> list[Finding]:
        from percent.models import Finding

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
