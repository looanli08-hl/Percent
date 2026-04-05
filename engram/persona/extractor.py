from __future__ import annotations

import json
import re
from pathlib import Path

from engram.llm.client import LLMClient
from engram.models import DataChunk, Finding, FindingCategory

_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

_FALLBACK_PROMPT = """\
Data source: {source}
Data type: {data_type}

---

{data}

---

Output a JSON array of findings with keys: category, content, confidence, evidence.
Return ONLY valid JSON.
"""


def _load_prompt(prompts_dir: Path | None) -> str:
    """Load extract.md prompt, falling back to inline template if missing."""
    directory = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    prompt_path = directory / "extract.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return _FALLBACK_PROMPT


def _parse_findings(text: str, source: str) -> list[Finding]:
    """Extract a JSON array from LLM response text and parse into Finding objects."""
    # Find the first '[' ... ']' block (greedy from first [ to last ])
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
            category_str = item.get("category", "trait")
            # Normalise: accept unknown categories as trait
            try:
                category = FindingCategory(category_str)
            except ValueError:
                category = FindingCategory.TRAIT

            finding = Finding(
                category=category,
                content=str(item.get("content", "")),
                confidence=float(item.get("confidence", 0.5)),
                source=source,
                evidence=str(item.get("evidence", "")),
            )
            findings.append(finding)
        except Exception:
            continue

    return findings


class PersonaExtractor:
    """Extract personality findings from DataChunks using an LLM."""

    def __init__(
        self,
        client: LLMClient,
        prompts_dir: Path | None = None,
        batch_size: int = 20,
    ) -> None:
        self.client = client
        self.batch_size = batch_size
        self._prompt_template = _load_prompt(prompts_dir)

    def extract(self, chunks: list[DataChunk]) -> list[Finding]:
        """Process chunks in batches and return all findings."""
        if not chunks:
            return []

        all_findings: list[Finding] = []
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            all_findings.extend(self._extract_batch(batch))
        return all_findings

    def _extract_batch(self, chunks: list[DataChunk]) -> list[Finding]:
        # Use first chunk's metadata for the batch label; all chunks in a batch
        # come from the same source in normal usage, but we default to the first.
        source = chunks[0].source
        data_type = chunks[0].type.value
        data = "\n\n".join(f"[{c.timestamp.date()}] {c.content}" for c in chunks)

        prompt = self._prompt_template.format(
            source=source,
            data_type=data_type,
            data=data,
        )

        response = self.client.complete(prompt)
        return _parse_findings(response, source=source)
