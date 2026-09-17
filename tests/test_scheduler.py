"""
Unit tests for PipelineScheduler service and APScheduler configuration.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.scheduler.scheduler import PipelineScheduler
from app.services.pipeline_service import PipelineRunSummary, PipelineService, PipelineStatus


@pytest.fixture
def test_config():
    """Provides test Config object."""
    return Config(
        adzuna_app_id="app_id",
        adzuna_app_key="app_key",
        scheduler_enabled=True,
        scheduler_interval_minutes=30,
        run_on_startup=False,
    )


def test_scheduler_initialization(test_config):
    """Test PipelineScheduler initialization and job registration."""
    scheduler_service = PipelineScheduler(config=test_config)

    scheduler_service.register_scheduled_job()

    job = scheduler_service.scheduler.get_job(PipelineScheduler.JOB_ID)
    assert job is not None
    assert job.max_instances == 1
    assert job.coalesce is True


def test_scheduler_duplicate_registration_ignored(test_config):
    """Test that calling register_scheduled_job multiple times does not create duplicate jobs."""
    scheduler_service = PipelineScheduler(config=test_config)

    scheduler_service.register_scheduled_job()
    scheduler_service.register_scheduled_job()

    jobs = scheduler_service.scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == PipelineScheduler.JOB_ID


def test_scheduler_disabled_mode():
    """Test scheduler start when SCHEDULER_ENABLED is False."""
    config = Config(
        adzuna_app_id="app_id",
        adzuna_app_key="app_key",
        scheduler_enabled=False,
    )
    scheduler_service = PipelineScheduler(config=config)
    scheduler_service.start(block=False)

    assert scheduler_service.scheduler.running is False


def test_scheduler_graceful_shutdown(test_config):
    """Test starting and gracefully shutting down the scheduler daemon."""
    scheduler_service = PipelineScheduler(config=test_config)
    scheduler_service.start(block=False)

    assert scheduler_service.scheduler.running is True
    scheduler_service.shutdown()
    assert scheduler_service.scheduler.running is False


def test_scheduled_job_wrapper_exception_handling(test_config):
    """Test that scheduled_job_wrapper catches exceptions from pipeline execution without crashing."""
    mock_pipeline = MagicMock(spec=PipelineService)
    mock_pipeline.run_monitoring_pipeline.side_effect = Exception("Pipeline execution failed")

    scheduler_service = PipelineScheduler(
        config=test_config, pipeline_service=mock_pipeline
    )

    # Calling wrapper directly should not raise uncaught exception
    scheduler_service.scheduled_job_wrapper()
    mock_pipeline.run_monitoring_pipeline.assert_called_once()
