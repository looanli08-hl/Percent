from __future__ import annotations

import json
import re
from pathlib import Path

from percent.llm.client import LLMClient
from percent.models import DataChunk

_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

_FALLBACK_PROMPT = """\
## Personality Profile

{core_profile}

## Test Scenario

Context: {context}
Their actual response: {actual_response}

Evaluate alignment. Output ONLY valid JSON with keys:
- predicted_response
- actual_response
- alignment_score (0.0 to 1.0)
- reasoning
"""


def _load_prompt(prompts_dir: Path | None) -> str:
    directory = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    prompt_path = directory / "validate.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return _FALLBACK_PROMPT


def _parse_score(text: str) -> tuple[float, dict]:
    """Extract alignment_score from JSON response; return (score, raw_dict)."""
    # Try to find JSON object in the response
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return 0.0, {}
    try:
        data = json.loads(match.group())
        score = float(data.get("alignment_score", 0.0))
        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))
        return score, data
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0.0, {}


class PersonaValidator:
    """Validate a core.md personality profile against real data chunks."""

    def __init__(
        self,
        client: LLMClient,
        prompts_dir: Path | None = None,
    ) -> None:
        self.client = client
        self._prompt_template = _load_prompt(prompts_dir)

    def validate(self, core_md: str, test_chunks: list[DataChunk]) -> dict:
        """
        Run each test_chunk through the LLM validation prompt.

        Returns:
            {
                "score": float,       # average alignment score
                "tests_run": int,
                "details": list[dict],
            }
        """
        if not test_chunks:
            return {"score": 0.0, "tests_run": 0, "details": []}

        scores: list[float] = []
        details: list[dict] = []

        for chunk in test_chunks:
            prompt = self._prompt_template.format(
                core_profile=core_md,
                context=f"{chunk.source} / {chunk.type.value}",
                actual_response=chunk.content,
            )
            response = self.client.complete(prompt)
            score, raw = _parse_score(response)
            scores.append(score)
            details.append({**raw, "alignment_score": score})

        avg_score = sum(scores) / len(scores)
        return {
            "score": avg_score,
            "tests_run": len(test_chunks),
            "details": details,
        }
