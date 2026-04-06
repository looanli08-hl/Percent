from __future__ import annotations

from pathlib import Path

from sentence_transformers import SentenceTransformer

from percent.llm.client import LLMClient
from percent.persona.fragments import FragmentStore

_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_DEFAULT_MODEL = "all-MiniLM-L6-v2"

_FALLBACK_SYSTEM = """\
You are {username}'s AI mirror.

## Personality Profile

{core_profile}

## Relevant Memories

{fragments}
"""


def _load_template(prompts_dir: Path | None) -> str:
    directory = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    template_path = directory / "chat_system.md"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return _FALLBACK_SYSTEM


class ChatEngine:
    """
    Persona-grounded conversational chat engine.

    Retrieves relevant memory fragments for each user message, builds a
    personalised system prompt from core.md + fragments, then calls the LLM
    via complete_chat() while maintaining full conversation history.
    """

    def __init__(
        self,
        percent_dir: Path,
        provider: str,
        model: str,
        api_key: str = "",
        prompts_dir: Path | None = None,
        embedding_model: str = _DEFAULT_MODEL,
        username: str = "User",
    ) -> None:
        self.username = username
        self.history: list[dict] = []

        # Load core personality profile
        core_path = Path(percent_dir) / "core.md"
        self._core_profile = core_path.read_text(encoding="utf-8") if core_path.exists() else ""

        # Fragment store for memory retrieval
        db_path = Path(percent_dir) / "fragments.db"
        self._store = FragmentStore(db_path)

        # Sentence embedder for query encoding
        self._embedder: SentenceTransformer = SentenceTransformer(embedding_model)

        # LLM client
        self._client = LLMClient(provider=provider, model=model, api_key=api_key)

        # System prompt template
        self._template = _load_template(prompts_dir)

    # ── public API ──────────────────────────────────────────────────────────

    def send(self, message: str, top_k: int = 5) -> str:
        """
        Send a user message, retrieve relevant fragments, call the LLM, and
        return the assistant's response.  Conversation history is updated.
        """
        # 1. Embed the query and retrieve relevant fragments
        query_embedding = self._embedder.encode(message).tolist()
        fragments = self._store.search(query_embedding, top_k=top_k)
        fragments_text = "\n".join(f"- [{f.category.value}] {f.content}" for f in fragments)

        # 2. Build system prompt from template
        system_prompt = self._template.format(
            username=self.username,
            core_profile=self._core_profile,
            fragments=fragments_text,
        )

        # 3. Append user message to history
        self.history.append({"role": "user", "content": message})

        # 4. Call LLM with full history
        response = self._client.complete_chat(self.history, system=system_prompt)

        # 5. Store assistant reply in history
        self.history.append({"role": "assistant", "content": response})

        return response

    def reset(self) -> None:
        """Clear conversation history."""
        self.history = []
