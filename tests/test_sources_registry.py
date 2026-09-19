"""
Unit tests for Phase 8.1 Multi-Source Job Intelligence Architecture.
Tests BaseJobSource contract, JobSourceRegistry registration, lookup, enabled/disabled source filtering,
source status metadata, and multi-source failure isolation.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.models import Job, SourceResult, SourceStatus
from app.sources.adzuna import AdzunaJobSource
from app.sources.base import BaseJobSource
from app.sources.gmail import IndeedAlertEmailSource, LinkedInAlertEmailSource
from app.sources.internshala import InternshalaJobSource
from app.sources.registry import JobSourceRegistry, create_default_source_registry


class CustomDummySource(BaseJobSource):
    """Test double implementing BaseJobSource interface."""

    def __init__(self, source_id: str = "dummy_source", enabled: bool = True):
        self._source_id = source_id
        self._enabled = enabled

    @property
    def name(self) -> str:
        return "Dummy Source"

    @property
    def source_identifier(self) -> str:
        return self._source_id

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self, config=None) -> bool:
        return self._enabled

    def fetch_jobs_raw(self, keyword: str, page: int = 1, results_per_page: int = 20):
        return [{"title": "Software Engineer", "company": "Test Co"}]

    def fetch_source_jobs(self, **kwargs):
        return SourceResult(
            source_name=self.name,
            status=SourceStatus.SUCCESS,
            jobs=[
                Job(
                    source=self.name,
                    source_job_id="dummy_1",
                    title="Software Engineer",
                    company="Test Co",
                )
            ],
            total_fetched=1,
        )


@pytest.fixture
def mock_config():
    """Provides a sample Config instance for testing."""
    return Config(
        adzuna_app_id="test_app_id",
        adzuna_app_key="test_app_key",
        source_adzuna_enabled=True,
        source_internshala_enabled=True,
        source_gmail_enabled=False,
    )


def test_1_base_source_contract():
    """Test 1: BaseJobSource contract properties and defaults."""
    source = CustomDummySource()
    assert source.name == "Dummy Source"
    assert source.source_identifier == "dummy_source"
    assert source.source_type == "api"
    assert source.is_enabled() is True

    res = source.fetch_source_jobs()
    assert res.source_name == "Dummy Source"
    assert res.status == SourceStatus.SUCCESS
    assert len(res.jobs) == 1


def test_2_source_registration():
    """Test 2: JobSourceRegistry registers sources correctly."""
    registry = JobSourceRegistry()
    dummy = CustomDummySource("custom_1")

    registry.register(dummy)
    registered = registry.list_sources()
    assert len(registered) == 1
    assert registered[0].source_identifier == "custom_1"


def test_3_source_lookup():
    """Test 3: JobSourceRegistry lookup by identifier or name."""
    registry = JobSourceRegistry()
    dummy = CustomDummySource("custom_key")
    registry.register(dummy)

    retrieved = registry.get_source("custom_key")
    assert retrieved is not None
    assert retrieved.name == "Dummy Source"

    # Lookup by name case-insensitive
    by_name = registry.get_source("Dummy Source")
    assert by_name is not None
    assert by_name.source_identifier == "custom_key"


def test_4_enabled_disabled_source_handling(mock_config):
    """Test 4: Enabled and disabled source filtering in registry."""
    registry = JobSourceRegistry()
    s1 = CustomDummySource("source_1", enabled=True)
    s2 = CustomDummySource("source_2", enabled=False)

    registry.register(s1)
    registry.register(s2)

    enabled_sources = registry.list_enabled_sources(mock_config)
    assert len(enabled_sources) == 1
    assert enabled_sources[0].source_identifier == "source_1"

    # Explicit registry disable
    registry.disable_source("source_1")
    enabled_after_disable = registry.list_enabled_sources(mock_config)
    assert len(enabled_after_disable) == 0

    # Re-enable
    registry.enable_source("source_1")
    enabled_after_reenable = registry.list_enabled_sources(mock_config)
    assert len(enabled_after_reenable) == 1


def test_5_source_status_metadata():
    """Test 5: SourceStatus constants and SourceResult metadata support."""
    assert SourceStatus.SUCCESS == "SUCCESS"
    assert SourceStatus.PARTIAL_FAILURE == "PARTIAL_FAILURE"
    assert SourceStatus.FAILED == "FAILED"
    assert SourceStatus.BLOCKED == "BLOCKED"
    assert SourceStatus.DISABLED == "DISABLED"

    res = SourceResult(
        source_name="Test Source",
        status=SourceStatus.DISABLED,
        jobs=[],
        total_fetched=0,
        error_message="Source disabled by config",
        duration_seconds=1.25,
    )
    assert res.status == SourceStatus.DISABLED
    assert res.duration_seconds == 1.25
    assert res.timestamp is not None


def test_6_source_failure_isolation(mock_config):
    """Test 6: Failure in one source does not prevent other sources from executing."""
    registry = JobSourceRegistry()

    failing_source = CustomDummySource("failing_source")
    failing_source.fetch_source_jobs = MagicMock(
        return_value=SourceResult(
            source_name="Failing Source",
            status=SourceStatus.FAILED,
            jobs=[],
            error_message="API connection failed",
        )
    )

    working_source = CustomDummySource("working_source")

    registry.register(failing_source)
    registry.register(working_source)

    results = []
    for source in registry.list_enabled_sources(mock_config):
        try:
            res = source.fetch_source_jobs()
            results.append(res)
        except Exception:
            results.append(
                SourceResult(
                    source_name=source.name,
                    status=SourceStatus.FAILED,
                    jobs=[],
                )
            )

    assert len(results) == 2
    assert results[0].status == SourceStatus.FAILED
    assert results[1].status == SourceStatus.SUCCESS
    assert len(results[1].jobs) == 1


def test_7_default_factory_creation(mock_config):
    """Test 7: create_default_source_registry registers default sources."""
    registry = create_default_source_registry(mock_config)
    sources = registry.list_sources()

    source_ids = {s.source_identifier for s in sources}
    assert "adzuna" in source_ids
    assert "internshala" in source_ids
    assert "linkedin_email" in source_ids
    assert "indeed_email" in source_ids

    # Verify enabled source filtering based on mock_config
    enabled = registry.list_enabled_sources(mock_config)
    enabled_ids = {s.source_identifier for s in enabled}
    assert "adzuna" in enabled_ids
    assert "internshala" in enabled_ids
    assert "linkedin_email" not in enabled_ids  # source_gmail_enabled is False in mock_config
