from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

CORE_MD = """\
## Personality Traits
- Values intellectual honesty

## Values
- Prioritizes deep understanding
"""

CHAT_RESPONSE = "That's a great question about systems thinking."


def make_dummy_embedder():
    embedder = MagicMock()
    embedder.encode.return_value = np.ones(384, dtype=np.float32)
    return embedder


def make_dummy_fragment_store():
    store = MagicMock()
    fragment = MagicMock()
    fragment.content = "Values intellectual honesty over social harmony"
    fragment.category = MagicMock()
    fragment.category.value = "trait"
    store.search.return_value = [fragment]
    return store


class TestChatEngine:
    """Tests for ChatEngine — mocks SentenceTransformer and FragmentStore."""

    @pytest.fixture(autouse=True)
    def patch_embedder(self):
        dummy = make_dummy_embedder()
        with patch("engram.chat.engine.SentenceTransformer", return_value=dummy):
            yield dummy

    @pytest.fixture(autouse=True)
    def patch_fragment_store(self):
        dummy = make_dummy_fragment_store()
        with patch("engram.chat.engine.FragmentStore", return_value=dummy):
            yield dummy

    def test_send_builds_prompt_with_core_and_fragments_returns_response(
        self, tmp_engram_dir, mock_llm_response
    ):
        """send() uses core.md + retrieved fragments in system prompt, returns LLM reply."""
        mock_llm_response(CHAT_RESPONSE)
        (tmp_engram_dir / "core.md").write_text(CORE_MD)

        from engram.chat.engine import ChatEngine

        engine = ChatEngine(
            engram_dir=tmp_engram_dir,
            provider="openai",
            model="gpt-4o",
            api_key="test",
            prompts_dir=None,
            embedding_model="all-MiniLM-L6-v2",
            username="Alice",
        )

        response = engine.send("Tell me about systems thinking")

        assert response == CHAT_RESPONSE
        assert len(engine.history) == 2
        assert engine.history[0]["role"] == "user"
        assert engine.history[0]["content"] == "Tell me about systems thinking"
        assert engine.history[1]["role"] == "assistant"
        assert engine.history[1]["content"] == CHAT_RESPONSE

    def test_history_maintained_across_turns(self, tmp_engram_dir, mock_llm_response):
        """After 2 sends, history contains 4 entries (user+assistant each time)."""
        mock_llm_response(CHAT_RESPONSE)
        (tmp_engram_dir / "core.md").write_text(CORE_MD)

        from engram.chat.engine import ChatEngine

        engine = ChatEngine(
            engram_dir=tmp_engram_dir,
            provider="openai",
            model="gpt-4o",
            api_key="test",
            prompts_dir=None,
            embedding_model="all-MiniLM-L6-v2",
            username="Alice",
        )

        engine.send("First message")
        engine.send("Second message")

        assert len(engine.history) == 4
        assert engine.history[0]["role"] == "user"
        assert engine.history[0]["content"] == "First message"
        assert engine.history[1]["role"] == "assistant"
        assert engine.history[2]["role"] == "user"
        assert engine.history[2]["content"] == "Second message"
        assert engine.history[3]["role"] == "assistant"

    def test_reset_clears_history(self, tmp_engram_dir, mock_llm_response):
        """reset() empties history."""
        mock_llm_response(CHAT_RESPONSE)
        (tmp_engram_dir / "core.md").write_text(CORE_MD)

        from engram.chat.engine import ChatEngine

        engine = ChatEngine(
            engram_dir=tmp_engram_dir,
            provider="openai",
            model="gpt-4o",
            api_key="test",
            prompts_dir=None,
            embedding_model="all-MiniLM-L6-v2",
            username="Alice",
        )

        engine.send("Hello")
        assert len(engine.history) == 2

        engine.reset()
        assert engine.history == []
