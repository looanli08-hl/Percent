"""Big Five personality scoring from core.md profile."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from percent.llm.client import LLMClient

_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_DIMENSIONS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
_LABELS = {
    "openness": "开放性",
    "conscientiousness": "尽责性",
    "extraversion": "外向性",
    "agreeableness": "宜人性",
    "neuroticism": "神经质",
}


@dataclass
class BigFiveScore:
    score: int  # 0-100
    reasoning: str


@dataclass
class BigFiveResult:
    openness: BigFiveScore
    conscientiousness: BigFiveScore
    extraversion: BigFiveScore
    agreeableness: BigFiveScore
    neuroticism: BigFiveScore

    def to_dict(self) -> dict:
        return {
            dim: {"score": getattr(self, dim).score, "reasoning": getattr(self, dim).reasoning}
            for dim in _DIMENSIONS
        }

    def format_report(self) -> str:
        lines = ["Big Five Personality Profile", "=" * 30, ""]
        for dim in _DIMENSIONS:
            s = getattr(self, dim)
            bar_len = s.score // 5
            bar = "█" * bar_len + "░" * (20 - bar_len)
            label = _LABELS[dim]
            lines.append(f"  {label:<6} ({dim[:1].upper()})  {bar}  {s.score}")
            lines.append(f"    {s.reasoning}")
            lines.append("")
        return "\n".join(lines)


def _load_prompt(prompts_dir: Path | None) -> str:
    directory = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    prompt_path = directory / "big_five.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""


def compute_big_five(
    client: LLMClient,
    core_md: str,
    prompts_dir: Path | None = None,
) -> BigFiveResult:
    """Compute Big Five scores from a core.md personality profile using LLM."""
    prompt_template = _load_prompt(prompts_dir)
    if not prompt_template:
        raise ValueError("Big Five prompt template not found")

    prompt = prompt_template.format(core_md=core_md)
    response = client.complete(prompt)

    return _parse_result(response)


def _parse_result(text: str) -> BigFiveResult:
    """Parse LLM response into BigFiveResult."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM response")

    raw = json.loads(match.group())

    scores = {}
    for dim in _DIMENSIONS:
        dim_data = raw.get(dim, {})
        scores[dim] = BigFiveScore(
            score=max(0, min(100, int(dim_data.get("score", 50)))),
            reasoning=str(dim_data.get("reasoning", "")),
        )

    return BigFiveResult(**scores)


def save_big_five(result: BigFiveResult, path: Path) -> None:
    """Save Big Five result to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_big_five(path: Path) -> BigFiveResult | None:
    """Load Big Five result from JSON file."""
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    scores = {}
    for dim in _DIMENSIONS:
        dim_data = raw.get(dim, {})
        scores[dim] = BigFiveScore(
            score=int(dim_data.get("score", 50)),
            reasoning=str(dim_data.get("reasoning", "")),
        )
    return BigFiveResult(**scores)
