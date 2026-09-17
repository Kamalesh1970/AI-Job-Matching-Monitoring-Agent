"""
Tests for app/config.py configuration loading and validation.
"""

import os
import pytest
from unittest import mock

from app.config import load_config, Config, DEFAULT_SEARCH_KEYWORDS


def test_config_loads_with_required_credentials():
    """Test loading configuration when valid credentials are set in environment."""
    env = {
        "ADZUNA_APP_ID": "test_id_123",
        "ADZUNA_APP_KEY": "test_key_abc",
        "ADZUNA_COUNTRY": "in",
        "ADZUNA_RESULTS_PER_PAGE": "25",
        "ADZUNA_MAX_PAGES": "3",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        cfg = load_config(load_env_file=False)
        assert isinstance(cfg, Config)
        assert cfg.adzuna_app_id == "test_id_123"
        assert cfg.adzuna_app_key == "test_key_abc"
        assert cfg.adzuna_country == "in"
        assert cfg.adzuna_results_per_page == 25
        assert cfg.adzuna_max_pages == 3
        assert cfg.keywords == DEFAULT_SEARCH_KEYWORDS


def test_config_missing_credentials_raises_value_error():
    """Test that missing required credentials raises ValueError with clear message."""
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc_info:
            load_config(load_env_file=False)
        assert "Missing required configuration parameter(s)" in str(exc_info.value)
        assert "ADZUNA_APP_ID" in str(exc_info.value)
        assert "ADZUNA_APP_KEY" in str(exc_info.value)


def test_config_missing_only_app_key_raises_value_error():
    """Test error message when only ADZUNA_APP_KEY is missing."""
    env = {"ADZUNA_APP_ID": "test_id"}
    with mock.patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError) as exc_info:
            load_config(load_env_file=False)
        assert "ADZUNA_APP_KEY" in str(exc_info.value)
        assert "ADZUNA_APP_ID" not in str(exc_info.value)


def test_config_defaults_when_optionals_omitted():
    """Test fallback defaults for optional config parameters."""
    env = {
        "ADZUNA_APP_ID": "id_val",
        "ADZUNA_APP_KEY": "key_val",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        cfg = load_config(load_env_file=False)
        assert cfg.adzuna_country == "in"
        assert cfg.adzuna_results_per_page == 20
        assert cfg.adzuna_max_pages == 2
        assert cfg.db_path == "data/jobs.db"


def test_config_loads_from_custom_env_file(tmp_path):
    """Test loading configuration from a specified .env file."""
    env_file = tmp_path / ".env.test"
    env_file.write_text(
        "ADZUNA_APP_ID=file_app_id\n"
        "ADZUNA_APP_KEY=file_app_key\n"
        "ADZUNA_COUNTRY=gb\n"
    )
    with mock.patch.dict(os.environ, {}, clear=True):
        cfg = load_config(env_path=str(env_file), load_env_file=True)
        assert cfg.adzuna_app_id == "file_app_id"
        assert cfg.adzuna_app_key == "file_app_key"
        assert cfg.adzuna_country == "gb"
