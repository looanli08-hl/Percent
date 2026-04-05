from __future__ import annotations

import litellm

litellm.suppress_debug_info = True


class LLMClient:
    PROVIDER_PREFIXES = {
        "claude": "claude",
        "openai": "openai",
        "deepseek": "deepseek",
        "ollama": "ollama",
    }

    def __init__(self, provider: str, model: str, api_key: str = "") -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        prefix = self.PROVIDER_PREFIXES.get(provider, provider)
        self.model_id = f"{prefix}/{model}"

    def complete(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = litellm.completion(
            model=self.model_id,
            messages=messages,
            api_key=self.api_key if self.api_key else None,
        )
        return response.choices[0].message.content

    def complete_chat(self, messages: list[dict], system: str = "") -> str:
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        response = litellm.completion(
            model=self.model_id,
            messages=full_messages,
            api_key=self.api_key if self.api_key else None,
        )
        return response.choices[0].message.content
