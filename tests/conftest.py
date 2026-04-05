import pytest


@pytest.fixture
def tmp_engram_dir(tmp_path):
    """Create a temporary ~/.engram/ directory for testing."""
    engram_dir = tmp_path / ".engram"
    engram_dir.mkdir()
    (engram_dir / "raw").mkdir()
    return engram_dir


@pytest.fixture
def mock_llm_response(monkeypatch):
    """Factory fixture to mock LLM responses."""
    def _mock(response_text: str):
        def fake_completion(**kwargs):
            class FakeChoice:
                class FakeMessage:
                    content = response_text
                message = FakeMessage()
            class FakeResponse:
                choices = [FakeChoice()]
            return FakeResponse()
        monkeypatch.setattr("litellm.completion", fake_completion)
    return _mock
