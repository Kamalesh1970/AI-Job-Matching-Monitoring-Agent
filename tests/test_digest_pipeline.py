"""
Integration tests for Phase 3 Telegram Digest pipeline and database notification tracking.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.database import (
    get_notified_job_ids,
    initialize_database,
    insert_job,
    record_notifications,
    save_match_results,
)
from app.db.models import Job, MatchResult
from app.main import run_telegram_digest_step
from app.services.telegram_notifier import TelegramNotifier


@pytest.fixture
def memory_db():
    """Provides an initialized in-memory SQLite database connection."""
    conn = initialize_database(":memory:")
    yield conn
    conn.close()


def test_notification_database_operations(memory_db):
    """Test recording notifications and retrieving notified job IDs."""
    job1 = Job(
        source="Adzuna",
        source_job_id="J1",
        title="ML Engineer",
        company="A Co",
        location="Bengaluru",
    )
    job2 = Job(
        source="Adzuna",
        source_job_id="J2",
        title="Data Scientist",
        company="B Co",
        location="Chennai",
    )
    insert_job(memory_db, job1)
    insert_job(memory_db, job2)

    assert get_notified_job_ids(memory_db, "telegram_digest") == set()

    # Record notification for job 1
    inserted = record_notifications(memory_db, [job1.id], "telegram_digest")
    assert inserted == 1
    assert get_notified_job_ids(memory_db, "telegram_digest") == {job1.id}

    # Duplicate recording ignored
    inserted_dup = record_notifications(memory_db, [job1.id], "telegram_digest")
    assert inserted_dup == 0


def test_digest_pipeline_deduplication_and_delivery(memory_db, capsys):
    """Test end-to-end digest pipeline: eligible matches delivered via Telegram and recorded in DB."""
    config = Config(
        adzuna_app_id="app_id",
        adzuna_app_key="app_key",
        telegram_bot_token="123:ABC",
        telegram_chat_id="456",
        telegram_min_match_score=70.0,
        telegram_max_jobs_per_digest=10,
        telegram_enabled=True,
    )

    # Insert two jobs
    j1 = Job(
        source="Adzuna",
        source_job_id="J101",
        title="Senior AI Engineer",
        company="Alpha AI",
        location="Bengaluru",
    )
    j2 = Job(
        source="Adzuna",
        source_job_id="J102",
        title="Machine Learning Lead",
        company="Beta AI",
        location="Remote",
    )
    insert_job(memory_db, j1)
    insert_job(memory_db, j2)

    matches = [
        MatchResult(
            job_id=j1.id,
            source_job_id="J101",
            title="Senior AI Engineer",
            company="Alpha AI",
            location="Bengaluru",
            final_score=88.0,
            match_status="MATCH",
        ),
        MatchResult(
            job_id=j2.id,
            source_job_id="J102",
            title="Machine Learning Lead",
            company="Beta AI",
            location="Remote",
            final_score=82.0,
            match_status="MATCH",
        ),
    ]

    save_match_results(memory_db, matches)

    jobs_map = {j1.id: j1, j2.id: j2}

    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    # Run digest first time
    run_telegram_digest_step(
        config=config,
        conn=memory_db,
        matches=matches,
        jobs_map=jobs_map,
        notifier=mock_notifier,
    )

    mock_notifier.send_message.assert_called_once()
    assert get_notified_job_ids(memory_db, "telegram_digest") == {j1.id, j2.id}

    captured = capsys.readouterr().out
    assert "Jobs analyzed: 2" in captured
    assert "Eligible matches: 2" in captured
    assert "Already notified: 0" in captured
    assert "New notifications: 2" in captured
    assert "Messages sent: 1" in captured
    assert "Failed messages: 0" in captured

    # Second run: should recognize already notified jobs and send 0 new notifications
    mock_notifier.reset_mock()
    run_telegram_digest_step(
        config=config,
        conn=memory_db,
        matches=matches,
        jobs_map=jobs_map,
        notifier=mock_notifier,
    )

    mock_notifier.send_message.assert_not_called()
    captured_second = capsys.readouterr().out
    assert "Eligible matches: 2" in captured_second
    assert "Already notified: 2" in captured_second
    assert "New notifications: 0" in captured_second


def test_digest_pipeline_failed_delivery_retryable(memory_db):
    """Test that when Telegram API fails to deliver, jobs remain unnotified and retryable."""
    config = Config(
        adzuna_app_id="app_id",
        adzuna_app_key="app_key",
        telegram_bot_token="123:ABC",
        telegram_chat_id="456",
        telegram_min_match_score=70.0,
        telegram_enabled=True,
    )

    j1 = Job(
        source="Adzuna",
        source_job_id="J201",
        title="NLP Scientist",
        company="Gamma AI",
    )
    insert_job(memory_db, j1)

    match = MatchResult(
        job_id=j1.id,
        source_job_id="J201",
        title="NLP Scientist",
        company="Gamma AI",
        final_score=85.0,
        match_status="MATCH",
    )

    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = False  # Telegram fails

    run_telegram_digest_step(
        config=config,
        conn=memory_db,
        matches=[match],
        jobs_map={j1.id: j1},
        notifier=mock_notifier,
    )

    # Database must NOT record failure as sent
    assert get_notified_job_ids(memory_db, "telegram_digest") == set()
