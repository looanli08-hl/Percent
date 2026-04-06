"""PersonaBench — reproducible personality evaluation from raw data."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from percent.models import DataChunk
from percent.persona.validator import PersonaValidator


class PersonaBench:
    """Versioned wrapper around PersonaValidator for reproducible evaluation."""

    VERSION = "0.2"

    def __init__(
        self,
        validator: PersonaValidator,
        model: str = "",
        provider: str = "",
    ) -> None:
        self.validator = validator
        self.model = model
        self.provider = provider

    @classmethod
    def from_config(
        cls,
        provider: str,
        model: str,
        api_key: str,
        prompts_dir: Path | None = None,
    ) -> PersonaBench:
        from percent.llm.client import LLMClient

        client = LLMClient(
            provider=provider, model=model, api_key=api_key
        )
        validator = PersonaValidator(client, prompts_dir=prompts_dir)
        return cls(validator, model=model, provider=provider)

    def evaluate(
        self,
        core_md: str,
        test_chunks: list[DataChunk],
        num_tests: int = 10,
    ) -> dict:
        """Run evaluation on up to *num_tests* raw data chunks."""
        sample = test_chunks[:num_tests]
        result = self.validator.validate(core_md, sample)

        # Source breakdown
        source_counts = Counter(c.source for c in sample)
        source_scores: dict[str, list[float]] = {}
        for chunk, detail in zip(
            sample, result.get("details", [])
        ):
            src = chunk.source
            score = detail.get("alignment_score", 0.0)
            source_scores.setdefault(src, []).append(score)

        by_source = {}
        for src, scores in source_scores.items():
            by_source[src] = {
                "count": len(scores),
                "avg_score": sum(scores) / len(scores),
            }

        return {
            "overall_score": result["score"],
            "tests_run": result["tests_run"],
            "details": result["details"],
            "bench_version": self.VERSION,
            "model": self.model,
            "provider": self.provider,
            "seed": 42,
            "by_source": by_source,
            "source_mix": dict(source_counts),
        }

    def format_report(self, result: dict) -> str:
        score_pct = result["overall_score"] * 100
        tests_run = result["tests_run"]
        version = result.get("bench_version", self.VERSION)
        details = result.get("details", [])
        by_source = result.get("by_source", {})

        lines = [
            f"PersonaBench v{version}",
            f"Score: {score_pct:.1f}%  ({tests_run} tests)",
        ]

        if result.get("model"):
            lines.append(
                f"Model: {result.get('provider', '')}"
                f"/{result['model']}"
            )

        lines.append("")

        for i, detail in enumerate(details, start=1):
            alignment = detail.get("alignment_score", 0.0)
            reasoning = detail.get("reasoning", "")
            lines.append(f"  [{i}] {alignment:.2f}  {reasoning}")

        if by_source:
            lines.append("")
            lines.append("By source:")
            for src, info in by_source.items():
                avg = info["avg_score"] * 100
                cnt = info["count"]
                lines.append(f"  {src}: {avg:.1f}% ({cnt} tests)")

        return "\n".join(lines)
