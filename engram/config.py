from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class EngramConfig(BaseModel):
    engram_dir: Path = Field(default_factory=lambda: Path.home() / ".engram")
    llm_provider: str = "claude"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_api_key: str = ""
    embedding_model: str = "all-MiniLM-L6-v2"
    core_rebuild_threshold: int = 10

    @property
    def core_path(self) -> Path:
        return self.engram_dir / "core.md"

    @property
    def fragments_db_path(self) -> Path:
        return self.engram_dir / "fragments.db"

    @property
    def raw_dir(self) -> Path:
        return self.engram_dir / "raw"


_SAVED_FIELDS = {
    "llm_provider",
    "llm_model",
    "llm_api_key",
    "embedding_model",
    "core_rebuild_threshold",
}


def save_config(config: EngramConfig) -> None:
    config.engram_dir.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in config.model_dump().items() if k in _SAVED_FIELDS}
    data = {k: str(v) if isinstance(v, Path) else v for k, v in data.items()}
    (config.engram_dir / "config.yaml").write_text(yaml.dump(data, default_flow_style=False))


def load_config(engram_dir: Path | None = None) -> EngramConfig:
    if engram_dir is None:
        engram_dir = Path.home() / ".engram"
    config_path = engram_dir / "config.yaml"
    if not config_path.exists():
        return EngramConfig(engram_dir=engram_dir)
    data = yaml.safe_load(config_path.read_text()) or {}
    return EngramConfig(engram_dir=engram_dir, **data)
