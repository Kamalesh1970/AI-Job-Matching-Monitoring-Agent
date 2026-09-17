"""
Integration tests for PipelineService orchestration, metrics recording, and fault isolation.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.database import (
    get_all_jobs,
    get_last_pipeline_run,
    initialize_database,
    insert_job,
)
from app.db.models import Job, MatchResult
from app.services.pipeline_service import PipelineService, PipelineStatus
from app.services.telegram_notifier import TelegramNotifier


@pytest.fixture
def memory_db():
    """Provides an initialized in-memory SQLite database connection."""
    conn = initialize_database(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def test_config():
    """Provides test Config object."""
    return Config(
        adzuna_app_id="app_id",
        adzuna_app_key="app_key",
        telegram_bot_token="123:ABC",
        telegram_chat_id="456",
        telegram_enabled=True,
    )


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_pipeline_service_successful_run(
    mock_adzuna_class, mock_matching_class, memory_db, test_config
):
    """Test full successful pipeline execution."""
    # Mock Adzuna source
    mock_source = MagicMock()
    sample_job = Job(
        source="Adzuna",
        source_job_id="J1",
        title="AI Engineer",
        company="Tech Corp",
    )
    mock_source.fetch_jobs_for_keyword.return_value = ([sample_job], True)
    mock_adzuna_class.return_value = mock_source

    # Mock Matching service
    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = [
        MatchResult(
            job_id=1,
            title="AI Engineer",
            final_score=85.0,
            match_status="MATCH",
        )
    ]
    mock_matching_class.return_value = mock_matching

    # Mock Telegram Notifier
    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(
        config=test_config, conn=memory_db, notifier=mock_notifier
    )

    assert summary.status == PipelineStatus.SUCCESS
    assert summary.jobs_fetched > 0
    assert summary.new_jobs == 1
    assert summary.matches_found == 1
    assert summary.failed_sources == 0

    # Verify run record in DB
    last_run = get_last_pipeline_run(memory_db)
    assert last_run is not None
    assert last_run["status"] == PipelineStatus.SUCCESS
    assert last_run["new_jobs"] == 1


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_pipeline_service_partial_failure_source_error(
    mock_adzuna_class, mock_matching_class, memory_db, test_config
):
    """Test partial failure when one search keyword request fails."""
    mock_source = MagicMock()
    # First keyword fails, second succeeds
    mock_source.fetch_jobs_for_keyword.side_effect = [
        ([], False),
        (
            [
                Job(
                    source="Adzuna",
                    source_job_id="J2",
                    title="ML Engineer",
                )
            ],
            True,
        ),
    ]
    mock_adzuna_class.return_value = mock_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = []
    mock_matching_class.return_value = mock_matching

    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    # Use 2 keywords
    test_config.keywords = ["Keyword1", "Keyword2"]

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(
        config=test_config, conn=memory_db, notifier=mock_notifier
    )

    assert summary.status == PipelineStatus.PARTIAL_FAILURE
    assert summary.failed_sources == 1
    assert summary.jobs_fetched == 1


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_pipeline_service_critical_failure_missing_resume(
    mock_adzuna_class, mock_matching_class, memory_db, test_config
):
    """Test critical failure when base resume file is missing."""
    mock_source = MagicMock()
    j1 = Job(source="Adzuna", source_job_id="J3", title="Data Scientist")
    insert_job(memory_db, j1)
    mock_source.fetch_jobs_for_keyword.return_value = ([], True)
    mock_adzuna_class.return_value = mock_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.side_effect = FileNotFoundError("Resume file missing")
    mock_matching_class.return_value = mock_matching

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(
        config=test_config, conn=memory_db
    )

    assert summary.status == PipelineStatus.FAILED
    assert "Resume missing" in summary.error_message
