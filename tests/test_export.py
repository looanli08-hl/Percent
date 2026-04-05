from __future__ import annotations

import pytest

CORE_MD = """\
## Personality Traits
- Values intellectual honesty

## Values
- Prioritizes deep understanding
"""

SOUL_RESPONSE = """\
# SOUL.md

## Identity
A deeply personalised assistant for Alice — an intellectually honest systems thinker.

## Understanding
Alice values deep understanding over surface-level knowledge. Challenges incorrect claims directly.

## Communication Style
Direct, concise, no filler. Dense and precise prose. Responds better to structured information.

## Decision Framework
Prioritise depth over breadth. Prefer hard evidence and first-principles reasoning.

## Boundaries
Avoid: small talk, hedging, oversimplification, social platitudes.
"""


class TestSoulMdExporter:
    def test_export_produces_soul_md_with_expected_sections(self, tmp_path, mock_llm_response):
        """export() writes SOUL.md and returns content with required sections."""
        mock_llm_response(SOUL_RESPONSE)

        core_path = tmp_path / "core.md"
        core_path.write_text(CORE_MD)
        output_path = tmp_path / "SOUL.md"

        from engram.export.soul_md import SoulMdExporter

        exporter = SoulMdExporter(
            provider="openai",
            model="gpt-4o",
            api_key="test",
            prompts_dir=None,
        )
        content = exporter.export(core_path=core_path, output_path=output_path)

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == content
        assert "## Identity" in content
        assert "## Communication Style" in content

    def test_export_raises_file_not_found_when_core_missing(self, tmp_path):
        """export() raises FileNotFoundError when core.md doesn't exist."""
        from engram.export.soul_md import SoulMdExporter

        exporter = SoulMdExporter(
            provider="openai",
            model="gpt-4o",
            api_key="test",
            prompts_dir=None,
        )

        missing_core = tmp_path / "nonexistent_core.md"
        output_path = tmp_path / "SOUL.md"

        with pytest.raises(FileNotFoundError):
            exporter.export(core_path=missing_core, output_path=output_path)
