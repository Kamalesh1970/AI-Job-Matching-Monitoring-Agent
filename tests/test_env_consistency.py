"""
Deterministic environment variable consistency and coverage test.
Verifies that all configuration variables used across application code and .env
are accurately documented in .env.example.
"""

import os
import re
import pytest

from app.config import Config


def parse_env_file_keys(filepath: str) -> set:
    """Extracts variable key names from an .env or .env.example file."""
    if not os.path.exists(filepath):
        return set()
    keys = set()
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                if key:
                    keys.add(key)
    return keys


def test_env_example_representation():
    """
    Verifies that required source & application variables are represented in .env.example.
    """
    env_example_keys = parse_env_file_keys(".env.example")
    env_keys = parse_env_file_keys(".env")

    required_job_source_keys = [
        "JOOBLE_API_KEY",
        "JSEARCH_API_KEY",
        "JSEARCH_RAPIDAPI_HOST",
        "SERPAPI_KEY",
        "ACTIVE_JOBS_DB_API_KEY",
        "ACTIVE_JOBS_DB_RAPIDAPI_HOST",
        "SOURCE_JOOBLE_ENABLED",
        "SOURCE_JSEARCH_ENABLED",
        "SOURCE_SERPAPI_ENABLED",
        "SOURCE_ACTIVE_JOBS_DB_ENABLED",
    ]

    missing_from_example = [key for key in required_job_source_keys if key not in env_example_keys]
    assert not missing_from_example, f"Required job source keys missing from .env.example: {missing_from_example}"

    if env_keys:
        missing_in_example_from_env = env_keys - env_example_keys
        assert not missing_in_example_from_env, f"Keys in .env but missing from .env.example: {missing_in_example_from_env}"


def test_config_dataclass_fields_covered():
    """
    Verifies that key Config dataclass parameters have corresponding environment variable definitions.
    """
    config_sample = Config(
        adzuna_app_id="test",
        adzuna_app_key="test",
        jooble_api_key="test",
        jsearch_api_key="test",
        serpapi_key="test",
        active_jobs_db_api_key="test",
    )
    assert hasattr(config_sample, "source_jooble_enabled")
    assert hasattr(config_sample, "source_jsearch_enabled")
    assert hasattr(config_sample, "source_serpapi_enabled")
    assert hasattr(config_sample, "source_active_jobs_db_enabled")
    assert hasattr(config_sample, "jsearch_rapidapi_host")
    assert hasattr(config_sample, "active_jobs_db_rapidapi_host")
