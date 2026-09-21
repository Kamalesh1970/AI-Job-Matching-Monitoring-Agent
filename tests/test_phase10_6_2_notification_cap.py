"""
Phase 10.6.2 — Pipeline Status Semantics & Notification Cap Tests.
Verifies that notification cap limits do not falsely trigger PARTIAL_FAILURE status,
deferred notifications are tracked accurately, real failures are preserved, and zero-job semantics are maintained.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.database import (
    initialize_database,
    insert_job,
    get_last_pipeline_run,
)
from app.db.models import Job, MatchResult, SourceResult, SourceStatus
from app.services.pipeline_service import PipelineService, PipelineStatus
from app.services.telegram_notifier import TelegramNotifier


@pytest.fixture
def memory_db():
    conn = initialize_database(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def test_config():
    return Config(
        adzuna_app_id="app_id",
        adzuna_app_key="app_key",
        keywords=["AI Engineer"],
        internshala_enabled=False,
        telegram_bot_token="123:ABC",
        telegram_chat_id="456",
        telegram_enabled=True,
        telegram_max_jobs_per_digest=10,
    )


def _seed_jobs_and_matches(memory_db, count=10):
    for i in range(1, count + 1):
        job = Job(
            id=i,
            source="Adzuna",
            source_job_id=f"j-{i}",
            title=f"AI Engineer {i}",
            company="Tech Corp",
            url=f"https://example.com/job/{i}",
        )
        insert_job(memory_db, job)


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_notifications_below_cap_success(mock_adzuna_class, mock_matching_class, memory_db, test_config):
    """1. All sources successful + notifications below cap -> SUCCESS."""
    _seed_jobs_and_matches(memory_db, 5)

    mock_source = MagicMock()
    mock_source.fetch_jobs_for_keyword.return_value = ([], True)
    mock_adzuna_class.return_value = mock_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = [
        MatchResult(job_id=i, title=f"AI Role {i}", final_score=85.0, match_status="MATCH", match_category="STRONG_MATCH")
        for i in range(1, 6) # 5 eligible (below 10 cap)
    ]
    mock_matching_class.return_value = mock_matching

    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(config=test_config, conn=memory_db, notifier=mock_notifier)

    assert summary.status == PipelineStatus.SUCCESS
    assert summary.eligible_notifications == 5
    assert summary.notifications_sent == 5
    assert summary.notifications_deferred == 0
    assert summary.notifications_failed == 0


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_notifications_exactly_at_cap_success(mock_adzuna_class, mock_matching_class, memory_db, test_config):
    """2. All sources successful + notifications exactly at cap -> SUCCESS."""
    _seed_jobs_and_matches(memory_db, 10)

    mock_source = MagicMock()
    mock_source.fetch_jobs_for_keyword.return_value = ([], True)
    mock_adzuna_class.return_value = mock_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = [
        MatchResult(job_id=i, title=f"AI Role {i}", final_score=85.0, match_status="MATCH", match_category="STRONG_MATCH")
        for i in range(1, 11) # 10 eligible (exactly at cap)
    ]
    mock_matching_class.return_value = mock_matching

    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(config=test_config, conn=memory_db, notifier=mock_notifier)

    assert summary.status == PipelineStatus.SUCCESS
    assert summary.eligible_notifications == 10
    assert summary.notifications_sent == 10
    assert summary.notifications_deferred == 0
    assert summary.notifications_failed == 0


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_notifications_above_cap_success_with_deferred(mock_adzuna_class, mock_matching_class, memory_db, test_config):
    """3. All sources successful + notifications above cap -> SUCCESS + deferred notifications."""
    _seed_jobs_and_matches(memory_db, 39)

    mock_source = MagicMock()
    mock_source.fetch_jobs_for_keyword.return_value = ([], True)
    mock_adzuna_class.return_value = mock_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = [
        MatchResult(job_id=i, title=f"AI Role {i}", final_score=85.0, match_status="MATCH", match_category="STRONG_MATCH")
        for i in range(1, 40) # 39 eligible (above cap 10)
    ]
    mock_matching_class.return_value = mock_matching

    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(config=test_config, conn=memory_db, notifier=mock_notifier)

    assert summary.status == PipelineStatus.SUCCESS
    assert summary.eligible_notifications == 39
    assert summary.notifications_sent == 10
    assert summary.notifications_deferred == 29
    assert summary.notifications_failed == 0

    # DB persistence check
    last_run = get_last_pipeline_run(memory_db)
    assert last_run is not None
    assert last_run["status"] == PipelineStatus.SUCCESS
    assert last_run["notifications_deferred"] == 29


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_one_source_failed_partial_failure(mock_adzuna_class, mock_matching_class, memory_db, test_config):
    """4. One source failed -> PARTIAL_FAILURE."""
    mock_source = MagicMock()
    mock_source.fetch_jobs_for_keyword.return_value = ([], False) # Adzuna request failed
    mock_adzuna_class.return_value = mock_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = []
    mock_matching_class.return_value = mock_matching

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(config=test_config, conn=memory_db)

    assert summary.status == PipelineStatus.PARTIAL_FAILURE
    assert summary.failed_sources == 1


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_notification_delivery_failure(mock_adzuna_class, mock_matching_class, memory_db, test_config):
    """5. Notification delivery failure -> PARTIAL_FAILURE."""
    _seed_jobs_and_matches(memory_db, 1)

    mock_source = MagicMock()
    mock_source.fetch_jobs_for_keyword.return_value = ([], True)
    mock_adzuna_class.return_value = mock_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = [
        MatchResult(job_id=1, title="AI Role 1", final_score=85.0, match_status="MATCH", match_category="STRONG_MATCH")
    ]
    mock_matching_class.return_value = mock_matching

    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = False # Delivery failed

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(config=test_config, conn=memory_db, notifier=mock_notifier)

    assert summary.status == PipelineStatus.PARTIAL_FAILURE
    assert summary.notifications_failed == 1


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_zero_eligible_notifications_success(mock_adzuna_class, mock_matching_class, memory_db, test_config):
    """7. Zero eligible notifications -> SUCCESS."""
    _seed_jobs_and_matches(memory_db, 1)

    mock_source = MagicMock()
    mock_source.fetch_jobs_for_keyword.return_value = ([], True)
    mock_adzuna_class.return_value = mock_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = []
    mock_matching_class.return_value = mock_matching

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(config=test_config, conn=memory_db)

    assert summary.status == PipelineStatus.SUCCESS
    assert summary.eligible_notifications == 0
    assert summary.notifications_sent == 0
    assert summary.notifications_deferred == 0


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_zero_fetched_jobs_without_failure(mock_adzuna_class, mock_matching_class, memory_db, test_config):
    """8. Zero fetched jobs without source failure -> SUCCESS."""
    mock_source = MagicMock()
    mock_source.fetch_jobs_for_keyword.return_value = ([], True)
    mock_adzuna_class.return_value = mock_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = []
    mock_matching_class.return_value = mock_matching

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(config=test_config, conn=memory_db)

    assert summary.status == PipelineStatus.SUCCESS
    assert summary.jobs_fetched == 0
    assert summary.failed_sources == 0
