"""PersonaBench — standardized personality consistency benchmark."""

from __future__ import annotations

from pathlib import Path

from engram.models import DataChunk
from engram.persona.validator import PersonaValidator


class PersonaBench:
    """Named, versioned wrapper around PersonaValidator for reproducible benchmarking."""

    VERSION = "0.1"

    def __init__(
        self,
        validator: PersonaValidator,
    ) -> None:
        self.validator = validator

    @classmethod
    def from_config(
        cls,
        provider: str,
        model: str,
        api_key: str,
        prompts_dir: Path | None = None,
    ) -> PersonaBench:
        """Convenience constructor — creates an LLMClient + validator internally."""
        from engram.llm.client import LLMClient

        client = LLMClient(provider=provider, model=model, api_key=api_key)
        validator = PersonaValidator(client, prompts_dir=prompts_dir)
        return cls(validator)

    def evaluate(
        self,
        core_md: str,
        test_chunks: list[DataChunk],
        num_tests: int = 10,
    ) -> dict:
        """
        Run PersonaBench evaluation.

        Uses up to *num_tests* chunks from *test_chunks*.

        Returns:
            {
                "overall_score": float,   # 0.0 – 1.0
                "tests_run": int,
                "details": list[dict],
                "bench_version": str,
            }
        """
        sample = test_chunks[:num_tests]
        result = self.validator.validate(core_md, sample)
        return {
            "overall_score": result["score"],
            "tests_run": result["tests_run"],
            "details": result["details"],
            "bench_version": self.VERSION,
        }

    def format_report(self, result: dict) -> str:
        """Return a human-readable benchmark report string."""
        score_pct = result["overall_score"] * 100
        tests_run = result["tests_run"]
        version = result.get("bench_version", self.VERSION)
        details = result.get("details", [])

        lines = [
            f"PersonaBench v{version}",
            f"Score: {score_pct:.1f}%  ({tests_run} tests)",
            "",
        ]

        for i, detail in enumerate(details, start=1):
            alignment = detail.get("alignment_score", 0.0)
            reasoning = detail.get("reasoning", "")
            lines.append(f"  [{i}] {alignment:.2f}  {reasoning}")

        return "\n".join(lines)
