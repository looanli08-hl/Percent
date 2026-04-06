import pytest


@pytest.fixture
def tmp_percent_dir(tmp_path):
    """Create a temporary ~/.percent/ directory for testing."""
    percent_dir = tmp_path / ".percent"
    percent_dir.mkdir()
    (percent_dir / "raw").mkdir()
    return percent_dir


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
