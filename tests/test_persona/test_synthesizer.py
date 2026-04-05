from __future__ import annotations

from engram.models import Finding, FindingCategory
from engram.persona.synthesizer import PersonaSynthesizer


def make_finding(content: str, category: str = "trait") -> Finding:
    return Finding(
        category=FindingCategory(category),
        content=content,
        confidence=0.8,
        source="wechat",
        evidence="some evidence",
    )


MOCK_PROFILE_MD = """\
## Personality Traits
- Values intellectual honesty over social harmony

## Values
- Prioritizes deep understanding over surface-level knowledge

## Thinking Patterns
- Systems thinker who connects disparate ideas

## Core Preferences
- Prefers hard sci-fi with physics-based worldbuilding

## Social Style
- Engages authentically; low tolerance for small talk

## Expression Characteristics
- Writes in precise, dense sentences
"""


def test_synthesize_returns_markdown(mock_llm_response):
    mock_llm_response(MOCK_PROFILE_MD)
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    synthesizer = PersonaSynthesizer(client, prompts_dir=None)

    findings = [
        make_finding("Values intellectual honesty"),
        make_finding("Hard sci-fi fan", "preference"),
    ]
    result = synthesizer.synthesize(findings)

    assert isinstance(result, str)
    assert len(result) > 0
    assert "## Personality Traits" in result


def test_synthesize_includes_all_sections(mock_llm_response):
    mock_llm_response(MOCK_PROFILE_MD)
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    synthesizer = PersonaSynthesizer(client, prompts_dir=None)

    findings = [make_finding("Curious about everything")]
    result = synthesizer.synthesize(findings)

    expected_sections = [
        "## Personality Traits",
        "## Values",
        "## Thinking Patterns",
        "## Core Preferences",
        "## Social Style",
        "## Expression Characteristics",
    ]
    for section in expected_sections:
        assert section in result, f"Missing section: {section}"


def test_synthesize_and_save_writes_file(mock_llm_response, tmp_path):
    mock_llm_response(MOCK_PROFILE_MD)
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    synthesizer = PersonaSynthesizer(client, prompts_dir=None)

    findings = [make_finding("Night owl")]
    core_path = tmp_path / "core.md"
    result = synthesizer.synthesize_and_save(findings, core_path)

    assert core_path.exists()
    content = core_path.read_text(encoding="utf-8")
    assert content == result
    assert "## Personality Traits" in content


def test_synthesize_and_save_creates_parent_dirs(mock_llm_response, tmp_path):
    mock_llm_response(MOCK_PROFILE_MD)
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    synthesizer = PersonaSynthesizer(client, prompts_dir=None)

    findings = [make_finding("Introverted")]
    nested_path = tmp_path / "deep" / "nested" / "core.md"
    synthesizer.synthesize_and_save(findings, nested_path)

    assert nested_path.exists()


def test_synthesize_formats_findings_count(mock_llm_response):
    """Verify finding_count is formatted correctly in the prompt."""
    captured_prompts = []

    def fake_completion(**kwargs):
        messages = kwargs.get("messages", [])
        for m in messages:
            if m.get("role") == "user":
                captured_prompts.append(m["content"])

        class FakeChoice:
            class FakeMessage:
                content = MOCK_PROFILE_MD

            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]

        return FakeResponse()

    import unittest.mock

    with unittest.mock.patch("litellm.completion", fake_completion):
        from engram.llm.client import LLMClient

        client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
        synthesizer = PersonaSynthesizer(client, prompts_dir=None)
        findings = [make_finding(f"finding {i}") for i in range(5)]
        synthesizer.synthesize(findings)

    assert len(captured_prompts) == 1
    assert "5" in captured_prompts[0]


def test_synthesize_empty_findings(mock_llm_response):
    """Empty findings list should still call LLM and return result."""
    mock_llm_response("## Personality Traits\n- Unknown")
    from engram.llm.client import LLMClient

    client = LLMClient(provider="openai", model="gpt-4o", api_key="test")
    synthesizer = PersonaSynthesizer(client, prompts_dir=None)

    result = synthesizer.synthesize([])
    assert isinstance(result, str)
    assert len(result) > 0
