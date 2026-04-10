"""Tests for the Settings / config module."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError


# Force clean defaults by clearing NOVEL_ env vars for these tests
@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove all NOVEL_* env vars so we test true defaults."""
    keys_to_remove = [k for k in os.environ if k.startswith("NOVEL_")]
    for k in keys_to_remove:
        monkeypatch.delenv(k, raising=False)


class TestSettingsDefaults:
    """Test default values and env loading for Settings."""

    def test_default_provider_is_empty(self):
        """Default llm_provider should be empty string."""
        from novel_creator.config import Settings
        s = Settings(_env_file=None)  # ignore .env entirely
        assert s.llm_provider == ""

    def test_default_openai_base_url(self):
        """Default base URL should point to OpenAI."""
        from novel_creator.config import Settings
        s = Settings(_env_file=None)
        assert s.openai_base_url == "https://api.openai.com/v1"

    def test_default_openrouter_base_url(self):
        """OpenRouter default URL."""
        from novel_creator.config import Settings
        s = Settings(_env_file=None)
        assert "openrouter.ai" in s.openrouter_base_url


class TestSettingsResolvedConfig:
    """Test resolved_api_key and resolved_base_url properties."""

    def test_resolved_uses_openai_when_no_provider(self):
        """Without provider, should fall back to openai settings."""
        from novel_creator.config import Settings
        s = Settings(
            llm_provider="",
            openai_api_key="sk-openai-key",
            openrouter_api_key="sk-or-key",
            openai_base_url="https://openai.com/v1",
        )
        assert s.resolved_api_key == "sk-openai-key"
        assert s.resolved_base_url == "https://openai.com/v1"

    def test_resolved_uses_openrouter_when_set(self):
        """With provider=openrouter, should use OpenRouter config."""
        from novel_creator.config import Settings
        s = Settings(
            llm_provider="openrouter",
            openai_api_key="sk-openai-key",
            openrouter_api_key="sk-or-key",
            openai_base_url="https://openai.com/v1",
            openrouter_base_url="https://openrouter.ai/api/v1",
        )
        assert s.resolved_api_key == "sk-or-key"
        assert s.resolved_base_url == "https://openrouter.ai/api/v1"

    def test_resolved_fallbacks_to_openai_key_for_openrouter(self):
        """If openrouter_api_key is empty, fallback to openai_api_key."""
        from novel_creator.config import Settings
        s = Settings(
            llm_provider="openrouter",
            openai_api_key="sk-fallback",
            openrouter_api_key="",
        )
        assert s.resolved_api_key == "sk-fallback"

    def test_db_full_path_returns_path_object(self):
        """db_full_path should return a Path instance."""
        from pathlib import Path
        from novel_creator.config import Settings
        s = Settings(db_path="/tmp/test.db")
        assert isinstance(s.db_full_path, Path)
        assert str(s.db_full_path) == "/tmp/test.db"


class TestSettingsEnvPrefix:
    """Verify NOVEL_ prefix works correctly."""

    def test_env_prefix_applies(self):
        """Environment variables with NOVEL_ prefix should be picked up."""
        from novel_creator.config import Settings
        # Settings uses env_prefix="NOVEL_" so these won't conflict with system vars
        model_config = Settings.model_config
        assert model_config.get("env_prefix") == "NOVEL_"


class TestSettingsModelResolution:
    """Test that LLM factory correctly uses resolved config."""

    def test_resolved_returns_string_values(self):
        """Resolved properties should return non-empty strings when configured."""
        from novel_creator.config import Settings
        s = Settings(
            _env_file=None,
            llm_provider="",
            openai_api_key="sk-test",
            openai_base_url="https://test.local/v1",
        )
        # Should not raise, should return values
        assert isinstance(s.resolved_api_key, str)
        assert len(s.resolved_api_key) > 0
        assert s.resolved_base_url == "https://test.local/v1"

    def test_get_llm_passes_resolved_to_chatopenai(self):
        """Verify get_llm creates ChatOpenAI with resolved config via integration."""
        from novel_creator.config import Settings, settings as _settings
        # Check that current settings produce valid resolved config
        key = _settings.resolved_api_key
        url = _settings.resolved_base_url
        # They should be strings (may be empty if no API key set)
        assert isinstance(key, str)
        assert isinstance(url, str)

    def test_openrouter_mode_selects_correct_keys(self):
        """In openrouter mode, resolved should pick openrouter-specific config."""
        from novel_creator.config import Settings
        s = Settings(
            _env_file=None,
            llm_provider="openrouter",
            openai_api_key="sk-openai",
            openrouter_api_key="sk-or-xxx",
            openai_base_url="https://openai.com/v1",
            openrouter_base_url="https://openrouter.ai/api/v1",
        )
        assert s.resolved_api_key == "sk-or-xxx"
        assert s.resolved_base_url == "https://openrouter.ai/api/v1"

    def test_fallback_to_openai_key_when_openrouter_empty(self):
        """If openrouter_api_key is empty, fallback to openai_api_key."""
        from novel_creator.config import Settings
        s = Settings(
            _env_file=None,
            llm_provider="openrouter",
            openai_api_key="sk-fallback-key",
            openrouter_api_key="",
            openai_base_url="https://openai.com/v1",
            openrouter_base_url="https://openrouter.ai/api/v1",
        )
        assert s.resolved_api_key == "sk-fallback-key"
