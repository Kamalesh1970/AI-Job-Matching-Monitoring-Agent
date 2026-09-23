"""
Unit tests for JobSourceRegistry with 18 multi-source job intelligence architecture (including Jooble, JSearch, SerpApi).
"""

from unittest.mock import MagicMock
import pytest

from app.config import Config
from app.db.models import SourceResult, SourceStatus
from app.sources.jooble import JoobleJobSource
from app.sources.jsearch import JSearchJobSource
from app.sources.registry import JobSourceRegistry, create_default_source_registry
from app.sources.serpapi import SerpApiJobSource


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        jooble_api_key="test_jooble_key",
        jsearch_api_key="test_jsearch_key",
        jsearch_rapidapi_host="jsearch.p.rapidapi.com",
        serpapi_key="test_serpapi_key",
        source_adzuna_enabled=True,
        source_internshala_enabled=True,
        source_gmail_enabled=False,
        source_jooble_enabled=True,
        source_jsearch_enabled=True,
        source_serpapi_enabled=True,
    )


def test_registry_registers_all_21_sources(mock_config):
    registry = create_default_source_registry(mock_config)
    sources = registry.list_sources()
    assert len(sources) == 21

    source_ids = {s.source_identifier for s in sources}
    expected_ids = {
        "adzuna",
        "internshala",
        "linkedin_email",
        "indeed_email",
        "linkedin_jobs_api",
        "indeed_jobs_api",
        "naukri_email",
        "glassdoor_email",
        "unstop_email",
        "foundit_email",
        "cutshort_email",
        "hirist_email",
        "wellfound_email",
        "arbeitnow",
        "remoteok",
        "jobicy",
        "himalayas",
        "jooble",
        "jsearch",
        "serpapi",
        "active_jobs_db",
    }
    assert expected_ids.issubset(source_ids)
    assert "google_jobs" not in source_ids


def test_registry_lookup_jooble_jsearch_serpapi(mock_config):
    registry = create_default_source_registry(mock_config)

    jooble = registry.get_source("jooble")
    assert jooble is not None
    assert jooble.name == "Jooble"
    assert isinstance(jooble, JoobleJobSource)

    jsearch = registry.get_source("jsearch")
    assert jsearch is not None
    assert jsearch.name == "JSearch"
    assert isinstance(jsearch, JSearchJobSource)

    serpapi = registry.get_source("serpapi")
    assert serpapi is not None
    assert serpapi.name == "SerpApi"
    assert isinstance(serpapi, SerpApiJobSource)


def test_registry_enabled_sources_filtering(mock_config):
    registry = create_default_source_registry(mock_config)
    enabled = registry.list_enabled_sources(mock_config)
    enabled_ids = {s.source_identifier for s in enabled}

    assert "jooble" in enabled_ids
    assert "jsearch" in enabled_ids
    assert "serpapi" in enabled_ids

    # Test turning off JSearch
    disabled_config = Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        jooble_api_key="test_jooble_key",
        jsearch_api_key="test_jsearch_key",
        serpapi_key="test_serpapi_key",
        source_jsearch_enabled=False,
    )
    enabled_after = registry.list_enabled_sources(disabled_config)
    enabled_after_ids = {s.source_identifier for s in enabled_after}

    assert "jsearch" not in enabled_after_ids
    assert "jooble" in enabled_after_ids
    assert "serpapi" in enabled_after_ids


def test_registry_fault_isolation(mock_config):
    registry = JobSourceRegistry()

    failing_serpapi = SerpApiJobSource(api_key="invalid_key")
    failing_serpapi.fetch_source_jobs = MagicMock(
        return_value=SourceResult(
            source_name="SerpApi",
            status=SourceStatus.FAILED,
            jobs=[],
            error_message="Quota Exceeded",
        )
    )

    working_jooble = JoobleJobSource(api_key="test_key")
    working_jooble.fetch_source_jobs = MagicMock(
        return_value=SourceResult(
            source_name="Jooble",
            status=SourceStatus.SUCCESS,
            jobs=[],
            total_fetched=5,
        )
    )

    registry.register(failing_serpapi)
    registry.register(working_jooble)

    results = []
    for source in registry.list_enabled_sources(mock_config):
        results.append(source.fetch_source_jobs())

    assert len(results) == 2
    serp_res = next(r for r in results if r.source_name == "SerpApi")
    joob_res = next(r for r in results if r.source_name == "Jooble")

    assert serp_res.status == SourceStatus.FAILED
    assert joob_res.status == SourceStatus.SUCCESS
    assert joob_res.total_fetched == 5
