"""
Tests for app/db/database.py SQLite operations.
"""

from app.db.database import (
    get_job_by_source_id,
    get_new_jobs,
    get_recent_jobs,
    initialize_database,
    insert_job,
    insert_jobs,
    job_exists,
    update_last_seen,
)
from app.db.models import Job


def test_database_initialization():
    """Test initializing an in-memory SQLite database and creating schema."""
    conn = initialize_database(":memory:")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
    table = cursor.fetchone()
    assert table is not None
    assert table["name"] == "jobs"
    conn.close()


def test_insert_job_new():
    """Test inserting a new job into database."""
    conn = initialize_database(":memory:")
    job = Job(
        source="Adzuna",
        source_job_id="job_001",
        title="ML Engineer",
        company="AI Inc",
        location="Remote",
        fetched_at="2026-09-17T10:00:00Z",
    )

    is_new = insert_job(conn, job)
    assert is_new is True

    stored_job = get_job_by_source_id(conn, "Adzuna", "job_001")
    assert stored_job is not None
    assert stored_job.title == "ML Engineer"
    assert stored_job.first_seen_at == "2026-09-17T10:00:00Z"
    assert stored_job.last_seen_at == "2026-09-17T10:00:00Z"

    conn.close()


def test_insert_job_duplicate_prevents_duplicate_row_and_preserves_first_seen():
    """
    Test calling insert_job twice with the same source_job_id results in one database row,
    preserves first_seen_at, and updates last_seen_at.
    """
    conn = initialize_database(":memory:")

    # Initial observation
    job1 = Job(
        source="Adzuna",
        source_job_id="job_001",
        title="ML Engineer",
        company="AI Inc",
        fetched_at="2026-09-17T10:00:00Z",
    )
    is_new1 = insert_job(conn, job1)
    assert is_new1 is True

    # Second observation 2 hours later
    job2 = Job(
        source="Adzuna",
        source_job_id="job_001",
        title="ML Engineer",
        company="AI Inc",
        fetched_at="2026-09-17T12:00:00Z",
    )
    is_new2 = insert_job(conn, job2)
    assert is_new2 is False

    # Check database row count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM jobs")
    count = cursor.fetchone()["count"]
    assert count == 1

    # Check timestamps
    stored_job = get_job_by_source_id(conn, "Adzuna", "job_001")
    assert stored_job.first_seen_at == "2026-09-17T10:00:00Z"
    assert stored_job.last_seen_at == "2026-09-17T12:00:00Z"

    conn.close()


def test_insert_jobs_batch():
    """Test batch inserting jobs with mixed new and existing jobs."""
    conn = initialize_database(":memory:")
    jobs = [
        Job(source="Adzuna", source_job_id="j1", title="Job 1", fetched_at="2026-09-17T10:00:00Z"),
        Job(source="Adzuna", source_job_id="j2", title="Job 2", fetched_at="2026-09-17T10:00:00Z"),
    ]

    new_count, existing_count = insert_jobs(conn, jobs)
    assert new_count == 2
    assert existing_count == 0

    # Repeat batch insertion
    new_count2, existing_count2 = insert_jobs(conn, jobs)
    assert new_count2 == 0
    assert existing_count2 == 2

    conn.close()


def test_job_exists_and_queries():
    """Test job_exists, get_new_jobs, and get_recent_jobs functions."""
    conn = initialize_database(":memory:")
    assert job_exists(conn, "Adzuna", "non_existent") is False

    job = Job(
        source="Adzuna",
        source_job_id="j100",
        title="Data Scientist",
        fetched_at="2026-09-17T10:00:00Z",
    )
    insert_job(conn, job)

    assert job_exists(conn, "Adzuna", "j100") is True

    new_jobs = get_new_jobs(conn)
    assert len(new_jobs) == 1
    assert new_jobs[0].source_job_id == "j100"

    recent_jobs = get_recent_jobs(conn, limit=10)
    assert len(recent_jobs) == 1
    assert recent_jobs[0].source_job_id == "j100"

    conn.close()
