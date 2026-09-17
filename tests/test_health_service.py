"""
Unit tests for HealthService, heartbeat status evaluation, and operational alert deduplication.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.database import (
    get_unresolved_health_alert,
    initialize_database,
    record_pipeline_finish,
    record_pipeline_start,
)
from app.services.health_service import HealthEvaluationResult, HealthService, HealthStatus
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
        heartbeat_timeout_minutes=180,
        scheduler_interval_minutes=60,
    )


def test_health_evaluation_no_history(memory_db, test_config):
    """Test health evaluation when no pipeline runs exist in database."""
    health_service = HealthService(config=test_config)
    ref_time = datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc)

    result = health_service.evaluate_health(
        conn=memory_db, config=test_config, reference_time=ref_time
    )

    assert result.status == HealthStatus.STALE
    assert result.last_successful_run_time is None
    assert "No successful pipeline run recorded" in result.message


def test_health_evaluation_healthy(memory_db, test_config):
    """Test health evaluation when last successful run was 30 minutes ago (timeout=180m)."""
    health_service = HealthService(config=test_config)

    now = datetime(2026, 9, 17, 14, 0, 0, tzinfo=timezone.utc)
    success_time = (now - timedelta(minutes=30)).isoformat()

    run_id = record_pipeline_start(memory_db, started_at=success_time)
    record_pipeline_finish(
        memory_db, run_id=run_id, status="SUCCESS", finished_at=success_time
    )

    result = health_service.evaluate_health(
        conn=memory_db, config=test_config, reference_time=now
    )

    assert result.status == HealthStatus.HEALTHY
    assert pytest.approx(result.minutes_since_last_success, abs=0.1) == 30.0


def test_health_evaluation_stale(memory_db, test_config):
    """Test health evaluation when last successful run was 200 minutes ago (timeout=180m)."""
    health_service = HealthService(config=test_config)

    now = datetime(2026, 9, 17, 18, 0, 0, tzinfo=timezone.utc)
    old_success_time = (now - timedelta(minutes=200)).isoformat()

    run_id = record_pipeline_start(memory_db, started_at=old_success_time)
    record_pipeline_finish(
        memory_db, run_id=run_id, status="SUCCESS", finished_at=old_success_time
    )

    result = health_service.evaluate_health(
        conn=memory_db, config=test_config, reference_time=now
    )

    assert result.status == HealthStatus.STALE
    assert pytest.approx(result.minutes_since_last_success, abs=0.1) == 200.0


def test_check_and_alert_health_stale_alert_deduplication(memory_db, test_config):
    """Test that stale condition dispatches Telegram alert and suppresses duplicate alerts on repeat checks."""
    health_service = HealthService(config=test_config)
    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    now = datetime(2026, 9, 17, 18, 0, 0, tzinfo=timezone.utc)

    # First check: stale condition sends alert
    res1 = health_service.check_and_alert_health(
        conn=memory_db, config=test_config, notifier=mock_notifier, reference_time=now
    )
    assert res1.status == HealthStatus.STALE
    mock_notifier.send_message.assert_called_once()
    assert "PIPELINE HEALTH ALERT" in mock_notifier.send_message.call_args[0][0]

    # Verify unresolved alert in DB
    unresolved = get_unresolved_health_alert(memory_db, "stale_pipeline")
    assert unresolved is not None

    # Second check: repeat stale check should NOT resend alert
    mock_notifier.reset_mock()
    res2 = health_service.check_and_alert_health(
        conn=memory_db, config=test_config, notifier=mock_notifier, reference_time=now
    )
    assert res2.status == HealthStatus.STALE
    mock_notifier.send_message.assert_not_called()


def test_health_recovery_resolves_stale_alert(memory_db, test_config):
    """Test that a new successful run transitions status to HEALTHY and resolves active stale alerts."""
    health_service = HealthService(config=test_config)
    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    t1 = datetime(2026, 9, 17, 18, 0, 0, tzinfo=timezone.utc)

    # 1. Trigger stale alert
    health_service.check_and_alert_health(
        conn=memory_db, config=test_config, notifier=mock_notifier, reference_time=t1
    )
    assert get_unresolved_health_alert(memory_db, "stale_pipeline") is not None

    # 2. Simulate pipeline recovery at t2
    t2 = t1 + timedelta(minutes=10)
    success_time = t2.isoformat()
    run_id = record_pipeline_start(memory_db, started_at=success_time)
    record_pipeline_finish(
        memory_db, run_id=run_id, status="SUCCESS", finished_at=success_time
    )

    # 3. Check health at t2
    res2 = health_service.check_and_alert_health(
        conn=memory_db, config=test_config, notifier=mock_notifier, reference_time=t2
    )

    assert res2.status == HealthStatus.HEALTHY
    # Verify alert is resolved
    assert get_unresolved_health_alert(memory_db, "stale_pipeline") is None
