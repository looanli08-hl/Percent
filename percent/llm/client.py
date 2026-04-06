from __future__ import annotations

from dataclasses import dataclass, field

import litellm

litellm.suppress_debug_info = True

# Approximate pricing per 1M tokens (USD) — input / output
_PRICING: dict[str, tuple[float, float]] = {
    "deepseek-chat": (0.27, 1.10),
    "deepseek-coder": (0.27, 1.10),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-haiku-3-5-20241022": (0.80, 4.00),
    "claude-opus-4-20250514": (15.00, 75.00),
}


@dataclass
class UsageStats:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_calls: int = 0
    calls: list[dict] = field(default_factory=list)

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_calls += 1
        self.calls.append({"input": input_tokens, "output": output_tokens})

    def estimate_cost(self, model: str) -> float:
        """Estimate total cost in USD based on model pricing."""
        pricing = _PRICING.get(model)
        if pricing is None:
            # Try partial match
            for key, val in _PRICING.items():
                if key in model or model in key:
                    pricing = val
                    break
        if pricing is None:
            return 0.0

        input_price, output_price = pricing
        input_cost = (self.total_input_tokens / 1_000_000) * input_price
        output_cost = (self.total_output_tokens / 1_000_000) * output_price
        return input_cost + output_cost

    def format_report(self, model: str) -> str:
        cost = self.estimate_cost(model)
        lines = [
            f"API calls: {self.total_calls}",
            f"Input tokens: {self.total_input_tokens:,}",
            f"Output tokens: {self.total_output_tokens:,}",
            f"Estimated cost: ${cost:.4f}",
        ]
        return "\n".join(lines)


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
        self.usage = UsageStats()

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
        self._track_usage(response)
        return str(response.choices[0].message.content)

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
        self._track_usage(response)
        return str(response.choices[0].message.content)

    def _track_usage(self, response: object) -> None:
        usage = getattr(response, "usage", None)
        if usage:
            self.usage.add(
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            )
