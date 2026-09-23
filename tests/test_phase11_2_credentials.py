"""
Unit and integration tests for Phase 11.2 Job API Credential Configuration.
Tests environment variable loading, safe config reporting, Google Jobs,
Active Jobs DB, LinkedIn API, Indeed API defaults, Gmail sources integrity, and registry status.
"""

import os
from unittest import mock
import pytest

from app.config import Config, load_config, get_config_credential_status
from app.sources.registry import create_default_source_registry
from app.sources.serpapi import SerpApiJobSource
from app.sources.active_jobs_db import ActiveJobsDBJobSource


def test_phase11_2_env_defaults():
    """1. Test environment variable loading & defaults for Phase 11.2 config fields."""
    env = {
        "ADZUNA_APP_ID": "test_app_id",
        "ADZUNA_APP_KEY": "test_app_key",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        cfg = load_config(load_env_file=False)
        assert cfg.source_linkedin_jobs_api_enabled is False
        assert cfg.source_indeed_jobs_api_enabled is False
        assert cfg.linkedin_jobs_api_key == ""
        assert cfg.linkedin_jobs_rapidapi_host == "linkedin-jobs-api.p.rapidapi.com"
        assert cfg.indeed_jobs_api_key == ""
        assert cfg.indeed_jobs_rapidapi_host == "indeed-jobs-api.p.rapidapi.com"


def test_phase11_2_missing_credentials():
    """2. Test missing credential handling."""
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc_info:
            load_config(load_env_file=False)
        assert "ADZUNA_APP_ID" in str(exc_info.value)


def test_phase11_2_enabled_disabled_behavior():
    """3. Test enabled/disabled behavior for Phase 11.2 source flags."""
    env = {
        "ADZUNA_APP_ID": "test_id",
        "ADZUNA_APP_KEY": "test_key",
        "SOURCE_SERPAPI_ENABLED": "false",
        "SOURCE_ACTIVE_JOBS_DB_ENABLED": "true",
        "ACTIVE_JOBS_DB_API_KEY": "active_key",
        "SOURCE_LINKEDIN_JOBS_API_ENABLED": "true",
        "LINKEDIN_JOBS_API_KEY": "lk_key",
        "SOURCE_INDEED_JOBS_API_ENABLED": "false",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        cfg = load_config(load_env_file=False)
        assert cfg.source_serpapi_enabled is False
        assert cfg.source_active_jobs_db_enabled is True
        assert cfg.source_linkedin_jobs_api_enabled is True
        assert cfg.source_indeed_jobs_api_enabled is False


def test_phase11_2_secret_safe_config_reporting():
    """4. Test secret-safe configuration reporting (SET, MISSING, DISABLED)."""
    env = {
        "ADZUNA_APP_ID": "test_id",
        "ADZUNA_APP_KEY": "test_key",
        "SERPAPI_KEY": "secret_serp_key_123",
        "SOURCE_SERPAPI_ENABLED": "true",
        "ACTIVE_JOBS_DB_API_KEY": "secret_active_key_456",
        "ACTIVE_JOBS_DB_RAPIDAPI_HOST": "active-jobs-db.p.rapidapi.com",
        "SOURCE_ACTIVE_JOBS_DB_ENABLED": "true",
        "SOURCE_LINKEDIN_JOBS_API_ENABLED": "false",
        "SOURCE_INDEED_JOBS_API_ENABLED": "false",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        cfg = load_config(load_env_file=False)
        report = get_config_credential_status(cfg)

        assert report["SERPAPI_KEY"] == "SET"
        assert report["ACTIVE_JOBS_DB_API_KEY"] == "SET"
        assert report["ACTIVE_JOBS_DB_RAPIDAPI_HOST"] == "SET"

        # LinkedIn & Indeed API are disabled and missing secret values
        assert report["LINKEDIN_JOBS_API_KEY"] in ("DISABLED", "MISSING")
        assert report["LINKEDIN_JOBS_RAPIDAPI_HOST"] in ("DISABLED", "SET", "MISSING")
        assert report["INDEED_JOBS_API_KEY"] in ("DISABLED", "MISSING")
        assert report["INDEED_JOBS_RAPIDAPI_HOST"] in ("DISABLED", "SET", "MISSING")

        # Secret values must NOT be present in the report
        for val in report.values():
            assert "secret_serp_key_123" not in val
            assert "secret_active_key_456" not in val


def test_phase11_2_env_example_consistency():
    """5. Test .env and .env.example consistency."""
    from tests.test_env_consistency import parse_env_file_keys

    example_keys = parse_env_file_keys(".env.example")

    required_keys = [
        "SERPAPI_KEY",
        "SOURCE_SERPAPI_ENABLED",
        "ACTIVE_JOBS_DB_API_KEY",
        "ACTIVE_JOBS_DB_RAPIDAPI_HOST",
        "SOURCE_ACTIVE_JOBS_DB_ENABLED",
        "LINKEDIN_JOBS_API_KEY",
        "LINKEDIN_JOBS_RAPIDAPI_HOST",
        "SOURCE_LINKEDIN_JOBS_API_ENABLED",
        "INDEED_JOBS_API_KEY",
        "INDEED_JOBS_RAPIDAPI_HOST",
        "SOURCE_INDEED_JOBS_API_ENABLED",
    ]

    for key in required_keys:
        assert key in example_keys, f"Key '{key}' missing from .env.example"


def test_phase11_2_google_jobs_using_serpapi_key():
    """6. Test Google Jobs uses SERPAPI_KEY and serpapi identifier."""
    serp_source = SerpApiJobSource(api_key="my_serp_key")
    assert serp_source.source_identifier == "serpapi"
    assert serp_source.name == "SerpApi"

    cfg = Config(
        adzuna_app_id="test",
        adzuna_app_key="test",
        serpapi_key="my_serp_key",
        source_serpapi_enabled=True,
    )
    assert serp_source.is_enabled(cfg) is True


def test_phase11_2_active_jobs_db_config():
    """7. Test Active Jobs DB configuration handling."""
    active_source = ActiveJobsDBJobSource(
        api_key="test_active_key",
        rapidapi_host="active-jobs-db.p.rapidapi.com",
    )
    assert active_source.source_identifier == "active_jobs_db"

    cfg_disabled = Config(
        adzuna_app_id="test",
        adzuna_app_key="test",
        active_jobs_db_api_key="test_active_key",
        source_active_jobs_db_enabled=False,
    )
    assert active_source.is_enabled(cfg_disabled) is False

    cfg_enabled = Config(
        adzuna_app_id="test",
        adzuna_app_key="test",
        active_jobs_db_api_key="test_active_key",
        source_active_jobs_db_enabled=True,
    )
    assert active_source.is_enabled(cfg_enabled) is True


def test_phase11_2_linkedin_disabled_without_authorized_credentials():
    """8. Test LinkedIn API defaults to disabled when credentials are blank."""
    cfg = Config(adzuna_app_id="test", adzuna_app_key="test")
    assert cfg.source_linkedin_jobs_api_enabled is False
    assert cfg.linkedin_jobs_api_key == ""


def test_phase11_2_indeed_disabled_without_authorized_credentials():
    """9. Test Indeed API defaults to disabled when credentials are blank."""
    cfg = Config(adzuna_app_id="test", adzuna_app_key="test")
    assert cfg.source_indeed_jobs_api_enabled is False
    assert cfg.indeed_jobs_api_key == ""


def test_phase11_2_gmail_linkedin_source_unaffected():
    """10. Test existing Gmail LinkedIn job source remains operational."""
    cfg = Config(adzuna_app_id="test", adzuna_app_key="test")
    registry = create_default_source_registry(config=cfg)
    linkedin_email = registry.get_source("linkedin_email")
    assert linkedin_email is not None
    assert linkedin_email.source_identifier == "linkedin_email"


def test_phase11_2_gmail_indeed_source_unaffected():
    """11. Test existing Gmail Indeed job source remains operational."""
    cfg = Config(adzuna_app_id="test", adzuna_app_key="test")
    registry = create_default_source_registry(config=cfg)
    indeed_email = registry.get_source("indeed_email")
    assert indeed_email is not None
    assert indeed_email.source_identifier == "indeed_email"


def test_phase11_2_registry_consistency():
    """12. Test registry source count and presence of RapidAPI / Email sources."""
    cfg = Config(adzuna_app_id="test", adzuna_app_key="test")
    registry = create_default_source_registry(config=cfg)
    sources = registry.list_sources()
    source_ids = [s.source_identifier for s in sources]

    # Exactly 21 registered sources
    assert len(sources) == 21

    # Verify both Gmail and RapidAPI sources exist
    assert "linkedin_email" in source_ids
    assert "indeed_email" in source_ids
    assert "linkedin_jobs_api" in source_ids
    assert "indeed_jobs_api" in source_ids
    assert "serpapi" in source_ids
    assert "active_jobs_db" in source_ids
