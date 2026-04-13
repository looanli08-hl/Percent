from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PercentConfig(BaseModel):
    percent_dir: Path = Field(default_factory=lambda: Path.home() / ".percent")
    llm_provider: str = "claude"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_api_key: str = ""
    embedding_model: str = "all-MiniLM-L6-v2"
    core_rebuild_threshold: int = 10

    @property
    def core_path(self) -> Path:
        return self.percent_dir / "core.md"

    @property
    def fragments_db_path(self) -> Path:
        return self.percent_dir / "fragments.db"

    @property
    def raw_dir(self) -> Path:
        return self.percent_dir / "raw"

    @property
    def cache_dir(self) -> Path:
        return self.percent_dir / "cache"


_SAVED_FIELDS = {
    "llm_provider",
    "llm_model",
    "llm_api_key",
    "embedding_model",
    "core_rebuild_threshold",
}


def save_config(config: PercentConfig) -> None:
    config.percent_dir.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in config.model_dump().items() if k in _SAVED_FIELDS}
    data = {k: str(v) if isinstance(v, Path) else v for k, v in data.items()}
    (config.percent_dir / "config.yaml").write_text(yaml.dump(data, default_flow_style=False))


def make_llm_client(config: PercentConfig):
    """Create an LLMClient with caching enabled from config."""
    from percent.llm.client import LLMClient

    return LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
        cache_dir=config.cache_dir,
    )


def load_config(percent_dir: Path | None = None) -> PercentConfig:
    if percent_dir is None:
        percent_dir = Path.home() / ".percent"
    config_path = percent_dir / "config.yaml"
    if not config_path.exists():
        return PercentConfig(percent_dir=percent_dir)
    data = yaml.safe_load(config_path.read_text()) or {}
    return PercentConfig(percent_dir=percent_dir, **data)
