from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.database import (
    get_all_jobs,
    get_last_pipeline_run,
    get_last_source_run,
    initialize_database,
    insert_job,
    record_source_run_finish,
    record_source_run_start,
)
from app.db.models import Job, MatchResult, SourceResult, SourceStatus
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
    """Provides test Config object with single keyword lists."""
    return Config(
        adzuna_app_id="app_id",
        adzuna_app_key="app_key",
        keywords=["AI Engineer"],
        internshala_keywords=["machine learning"],
        telegram_bot_token="123:ABC",
        telegram_chat_id="456",
        telegram_enabled=True,
    )



@patch("app.services.pipeline_service.InternshalaJobSource")
@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_pipeline_service_successful_run(
    mock_adzuna_class, mock_matching_class, mock_ish_class, memory_db, test_config
):
    """Test full successful dual-source pipeline execution."""
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

    # Mock Internshala source
    mock_ish_source = MagicMock()
    ish_job = Job(
        source="Internshala",
        source_job_id="101",
        title="ML Intern",
        company="AI Labs",
    )
    mock_ish_source.fetch_source_jobs.return_value = SourceResult(
        source_name="Internshala",
        status=SourceStatus.SUCCESS,
        jobs=[ish_job],
        total_fetched=1,
    )
    mock_ish_class.return_value = mock_ish_source

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
    assert summary.jobs_fetched == 2  # 1 Adzuna + 1 Internshala
    assert summary.new_jobs == 2
    assert summary.matches_found == 1
    assert summary.failed_sources == 0

    # Verify run record in DB
    last_run = get_last_pipeline_run(memory_db)
    assert last_run is not None
    assert last_run["status"] == PipelineStatus.SUCCESS
    assert last_run["new_jobs"] == 2


@patch("app.services.pipeline_service.InternshalaJobSource")
@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_pipeline_service_internshala_blocked_isolation(
    mock_adzuna_class, mock_matching_class, mock_ish_class, memory_db, test_config
):
    """Test that Internshala BLOCKED status causes PARTIAL_FAILURE without stopping Adzuna or pipeline."""
    mock_source = MagicMock()
    sample_job = Job(source="Adzuna", source_job_id="J10", title="Python Dev")
    mock_source.fetch_jobs_for_keyword.return_value = ([sample_job], True)
    mock_adzuna_class.return_value = mock_source

    # Mock Internshala returning BLOCKED
    mock_ish_source = MagicMock()
    mock_ish_source.fetch_source_jobs.return_value = SourceResult(
        source_name="Internshala",
        status=SourceStatus.BLOCKED,
        jobs=[],
        total_fetched=0,
        error_message="CAPTCHA challenge",
    )
    mock_ish_class.return_value = mock_ish_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = []
    mock_matching_class.return_value = mock_matching

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(
        config=test_config, conn=memory_db
    )

    assert summary.status == PipelineStatus.PARTIAL_FAILURE
    assert summary.failed_sources == 1
    assert summary.jobs_fetched == 1  # Adzuna job was fetched and saved!

    # Verify per-source run recorded in source_runs table
    last_ish_run = get_last_source_run(memory_db, "Internshala")
    assert last_ish_run is not None
    assert last_ish_run["status"] == SourceStatus.BLOCKED


@patch("app.services.pipeline_service.InternshalaJobSource")
@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_pipeline_service_internshala_interval_skipping(
    mock_adzuna_class, mock_matching_class, mock_ish_class, memory_db, test_config
):
    """Test that Internshala execution is skipped if last run was within internshala_interval_hours."""
    # Pre-record recent Internshala run (e.g. 1 hour ago)
    now_iso = datetime.now(timezone.utc).isoformat()
    run_id = record_source_run_start(memory_db, "Internshala", started_at=now_iso)
    record_source_run_finish(
        memory_db,
        run_id=run_id,
        status=SourceStatus.SUCCESS,
        finished_at=now_iso,
        jobs_fetched=5,
        new_jobs=2,
    )

    mock_source = MagicMock()
    mock_source.fetch_jobs_for_keyword.return_value = ([], True)
    mock_adzuna_class.return_value = mock_source

    mock_ish_source = MagicMock()
    mock_ish_class.return_value = mock_ish_source

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = []
    mock_matching_class.return_value = mock_matching

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(
        config=test_config, conn=memory_db
    )

    # Internshala fetch_source_jobs should NOT be called because interval has not elapsed (12 hours)
    assert not mock_ish_source.fetch_source_jobs.called
    assert summary.status == PipelineStatus.SUCCESS


@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_pipeline_service_critical_failure_missing_resume(
    mock_adzuna_class, mock_matching_class, memory_db, test_config
):
    """Test critical failure when base resume file is missing."""
    test_config.internshala_enabled = False

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

