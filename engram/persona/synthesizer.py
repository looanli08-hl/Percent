from __future__ import annotations

from pathlib import Path

from engram.llm.client import LLMClient
from engram.models import Finding

_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

_FALLBACK_PROMPT = """\
Synthesize the following {finding_count} personality findings into a cohesive Markdown profile.

Use sections:
## Personality Traits
## Values
## Thinking Patterns
## Core Preferences
## Social Style
## Expression Characteristics

Findings:

{findings}
"""


def _load_prompt(prompts_dir: Path | None) -> str:
    directory = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    prompt_path = directory / "synthesize.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return _FALLBACK_PROMPT


def _format_findings(findings: list[Finding]) -> str:
    lines: list[str] = []
    for i, f in enumerate(findings, 1):
        lines.append(
            f"{i}. [{f.category.value}] {f.content} (confidence: {f.confidence:.2f})\n"
            f"   Evidence: {f.evidence}"
        )
    return "\n\n".join(lines)


class PersonaSynthesizer:
    """Synthesize a list of Findings into a Markdown personality profile."""

    def __init__(
        self,
        client: LLMClient,
        prompts_dir: Path | None = None,
    ) -> None:
        self.client = client
        self._prompt_template = _load_prompt(prompts_dir)

    def synthesize(self, findings: list[Finding]) -> str:
        """Send findings to LLM and return the generated Markdown string."""
        findings_text = _format_findings(findings)
        prompt = self._prompt_template.format(
            finding_count=len(findings),
            findings=findings_text,
        )
        return self.client.complete(prompt)

    def synthesize_and_save(self, findings: list[Finding], core_path: Path) -> str:
        """Synthesize, write to *core_path*, and return the Markdown string."""
        content = self.synthesize(findings)
        core_path.parent.mkdir(parents=True, exist_ok=True)
        core_path.write_text(content, encoding="utf-8")
        return content
