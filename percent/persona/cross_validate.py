"""Cross-source validation and confidence recalibration for personality fragments."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from percent.llm.client import LLMClient
from percent.models import Finding, FindingCategory, Fragment


_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

# Similarity threshold for considering two findings as corroborating
_CORROBORATION_THRESHOLD = 0.75


def _load_prompt(prompts_dir: Path | None) -> str:
    directory = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    prompt_path = directory / "deep_analyze.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""


def cross_validate_fragments(fragments: list[Fragment]) -> list[Fragment]:
    """Adjust fragment confidence based on cross-source corroboration.

    Fragments corroborated by similar findings from different sources get a
    confidence boost. Isolated findings (single source, no corroboration) get
    a slight penalty.
    """
    if len(fragments) < 2:
        return fragments

    # Group by source
    sources = set(f.source for f in fragments)
    if len(sources) < 2:
        # Only one source — can't cross-validate
        return fragments

    # Build embedding matrix
    embeddings = []
    valid_indices = []
    for i, f in enumerate(fragments):
        if f.embedding and len(f.embedding) > 0:
            embeddings.append(np.array(f.embedding))
            valid_indices.append(i)

    if len(embeddings) < 2:
        return fragments

    emb_matrix = np.stack(embeddings)
    # Normalize
    norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    emb_matrix = emb_matrix / norms

    # Cosine similarity matrix
    sim_matrix = emb_matrix @ emb_matrix.T

    updated = list(fragments)
    for idx_a, i in enumerate(valid_indices):
        frag_a = fragments[i]
        corroboration_count = 0
        max_sim = 0.0

        for idx_b, j in enumerate(valid_indices):
            if i == j:
                continue
            frag_b = fragments[j]
            # Only count cross-source corroboration
            if frag_b.source == frag_a.source:
                continue
            sim = float(sim_matrix[idx_a, idx_b])
            if sim >= _CORROBORATION_THRESHOLD:
                corroboration_count += 1
                max_sim = max(max_sim, sim)

        # Adjust confidence
        old_conf = frag_a.confidence
        if corroboration_count > 0:
            # Boost: up to +0.15 for strong cross-source corroboration
            boost = min(0.15, corroboration_count * 0.05)
            new_conf = min(1.0, old_conf + boost)
        elif len(sources) >= 2:
            # Slight penalty for uncorroborated findings when multiple sources exist
            new_conf = max(0.1, old_conf - 0.05)
        else:
            new_conf = old_conf

        if new_conf != old_conf:
            updated_frag = Fragment(
                id=frag_a.id,
                category=frag_a.category,
                content=frag_a.content,
                confidence=round(new_conf, 2),
                source=frag_a.source,
                embedding=frag_a.embedding,
                created_at=frag_a.created_at,
            )
            updated[i] = updated_frag

    return updated


class DeepAnalyzer:
    """Second-pass analysis: finds deeper patterns, contradictions, and gaps."""

    def __init__(self, client: LLMClient, prompts_dir: Path | None = None) -> None:
        self.client = client
        self._prompt_template = _load_prompt(prompts_dir)

    def analyze(self, findings: list[Finding]) -> list[Finding]:
        """Run deep analysis on existing findings and return new deep findings."""
        if not findings or not self._prompt_template:
            return []

        findings_text = self._format_findings(findings)
        prompt = self._prompt_template.format(
            finding_count=len(findings),
            findings=findings_text,
        )

        response = self.client.complete(prompt)
        return self._parse_deep_findings(response)

    @staticmethod
    def _format_findings(findings: list[Finding]) -> str:
        lines: list[str] = []
        for i, f in enumerate(findings, 1):
            lines.append(
                f"[{i}] [{f.category.value}] {f.content} "
                f"(confidence: {f.confidence:.2f}, source: {f.source})"
            )
        return "\n".join(lines)

    @staticmethod
    def _parse_deep_findings(text: str) -> list[Finding]:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []

        try:
            raw = json.loads(match.group())
        except json.JSONDecodeError:
            return []

        findings: list[Finding] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                finding_type = item.get("type", "pattern")
                content = str(item.get("content", ""))
                confidence = float(item.get("confidence", 0.6))
                reasoning = str(item.get("reasoning", ""))
                related = item.get("related_findings", [])

                # Map deep analysis types to categories
                category = FindingCategory.TRAIT
                if finding_type == "contradiction":
                    # Contradictions are still traits — they reveal complexity
                    pass
                elif finding_type == "missing":
                    category = FindingCategory.TRAIT

                finding = Finding(
                    category=category,
                    content=content,
                    confidence=min(1.0, max(0.0, confidence)),
                    source="deep_analysis",
                    evidence=f"Based on findings {related}. {reasoning}",
                )
                findings.append(finding)
            except Exception:
                continue

        return findings
