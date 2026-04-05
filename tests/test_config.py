from pathlib import Path

from engram.config import EngramConfig, load_config, save_config


def test_default_config():
    config = EngramConfig()
    assert config.llm_provider == "claude"
    assert config.llm_model == "claude-sonnet-4-20250514"
    assert config.engram_dir == Path.home() / ".engram"


def test_save_and_load_config(tmp_engram_dir):
    config = EngramConfig(engram_dir=tmp_engram_dir, llm_api_key="sk-test-123")
    save_config(config)
    loaded = load_config(tmp_engram_dir)
    assert loaded.llm_api_key == "sk-test-123"
    assert loaded.llm_provider == "claude"


def test_config_file_excludes_sensitive_defaults(tmp_engram_dir):
    config = EngramConfig(engram_dir=tmp_engram_dir)
    save_config(config)
    content = (tmp_engram_dir / "config.yaml").read_text()
    assert "engram_dir" not in content
