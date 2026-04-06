from pathlib import Path

from percent.config import PercentConfig, load_config, save_config


def test_default_config():
    config = PercentConfig()
    assert config.llm_provider == "claude"
    assert config.llm_model == "claude-sonnet-4-20250514"
    assert config.percent_dir == Path.home() / ".percent"


def test_save_and_load_config(tmp_percent_dir):
    config = PercentConfig(percent_dir=tmp_percent_dir, llm_api_key="sk-test-123")
    save_config(config)
    loaded = load_config(tmp_percent_dir)
    assert loaded.llm_api_key == "sk-test-123"
    assert loaded.llm_provider == "claude"


def test_config_file_excludes_sensitive_defaults(tmp_percent_dir):
    config = PercentConfig(percent_dir=tmp_percent_dir)
    save_config(config)
    content = (tmp_percent_dir / "config.yaml").read_text()
    assert "percent_dir" not in content
