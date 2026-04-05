from __future__ import annotations

from pathlib import Path

from engram.llm.client import LLMClient

_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

_FALLBACK_TEMPLATE = """\
Convert the following personality profile into an OpenClaw SOUL.md format.

## Source Personality Profile

{core_profile}
"""


def _load_template(prompts_dir: Path | None) -> str:
    directory = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    template_path = directory / "soul_export.md"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return _FALLBACK_TEMPLATE


class SoulMdExporter:
    """
    Export a core.md personality profile to OpenClaw SOUL.md format.

    Reads core.md, formats it into the soul_export.md prompt template,
    calls the LLM, and writes the result to the specified output path.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str = "",
        prompts_dir: Path | None = None,
    ) -> None:
        self._client = LLMClient(provider=provider, model=model, api_key=api_key)
        self._template = _load_template(prompts_dir)

    def export(self, core_path: Path, output_path: Path) -> str:
        """
        Read *core_path*, call LLM to generate SOUL.md content, write to
        *output_path*, and return the content as a string.

        Raises FileNotFoundError if *core_path* does not exist.
        """
        core_path = Path(core_path)
        if not core_path.exists():
            raise FileNotFoundError(f"core.md not found: {core_path}")

        core_profile = core_path.read_text(encoding="utf-8")
        prompt = self._template.format(core_profile=core_profile)

        content = self._client.complete(prompt)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        return content
