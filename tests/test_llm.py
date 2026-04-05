from engram.llm.client import LLMClient


def test_llm_client_completion(mock_llm_response):
    mock_llm_response("This person values creativity.")
    client = LLMClient(provider="claude", model="claude-sonnet-4-20250514", api_key="fake")
    result = client.complete("Analyze this data", system="You are an analyzer")
    assert "creativity" in result


def test_llm_client_formats_model_name():
    client = LLMClient(provider="claude", model="claude-sonnet-4-20250514", api_key="fake")
    assert client.model_id == "claude/claude-sonnet-4-20250514"


def test_llm_client_openai_provider():
    client = LLMClient(provider="openai", model="gpt-4o", api_key="fake")
    assert client.model_id == "openai/gpt-4o"


def test_llm_client_deepseek_provider():
    client = LLMClient(provider="deepseek", model="deepseek-chat", api_key="fake")
    assert client.model_id == "deepseek/deepseek-chat"
