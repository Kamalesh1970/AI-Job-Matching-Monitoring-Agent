"""
SQLite database interface and operations for job storage, match results, and notification tracking.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from app.db.models import Job, MatchResult


def get_connection(db_path: str = "data/jobs.db") -> sqlite3.Connection:
    """Creates SQLite connection with row factory set to Row."""
    if db_path != ":memory:":
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: str = "data/jobs.db") -> sqlite3.Connection:
    """
    Initializes the SQLite database and creates jobs, job_matches, and job_notifications tables.
    """
    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_job_id TEXT NOT NULL,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                description TEXT,
                url TEXT,
                created_at TEXT,
                fetched_at TEXT NOT NULL,
                salary_min REAL,
                salary_max REAL,
                salary_currency TEXT,
                employment_type TEXT,
                category TEXT,
                fingerprint TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE(source, source_job_id)
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_source_id ON jobs(source, source_job_id);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint);
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                similarity_score REAL NOT NULL,
                skill_score REAL NOT NULL,
                rule_score REAL NOT NULL,
                final_score REAL NOT NULL,
                match_status TEXT NOT NULL,
                matched_skills TEXT,
                missing_skills TEXT,
                reasons TEXT,
                calculated_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                UNIQUE(job_id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                notification_type TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                UNIQUE(job_id, notification_type)
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_notifications_job_type ON job_notifications(job_id, notification_type);
            """
        )
    return conn


def _row_to_job(row: sqlite3.Row) -> Job:
    """Converts a SQLite Row object to a Job model instance."""
    return Job(
        id=row["id"] if "id" in row.keys() else None,
        source=row["source"],
        source_job_id=row["source_job_id"],
        title=row["title"],
        company=row["company"] or "",
        location=row["location"] or "",
        description=row["description"] or "",
        url=row["url"] or "",
        created_at=row["created_at"],
        fetched_at=row["fetched_at"],
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
        salary_currency=row["salary_currency"],
        employment_type=row["employment_type"],
        category=row["category"],
        fingerprint=row["fingerprint"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
    )


def job_exists(conn: sqlite3.Connection, source: str, source_job_id: str) -> bool:
    """Checks if a job exists by source and source_job_id."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM jobs WHERE source = ? AND source_job_id = ? LIMIT 1",
        (source, source_job_id),
    )
    return cursor.fetchone() is not None


def get_job_by_source_id(
    conn: sqlite3.Connection, source: str, source_job_id: str
) -> Optional[Job]:
    """Retrieves a job by source and source_job_id."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM jobs WHERE source = ? AND source_job_id = ? LIMIT 1",
        (source, source_job_id),
    )
    row = cursor.fetchone()
    if row:
        return _row_to_job(row)
    return None


def update_last_seen(
    conn: sqlite3.Connection,
    source: str,
    source_job_id: str,
    seen_timestamp: Optional[str] = None,
) -> bool:
    """
    Updates the last_seen_at timestamp for an existing job without modifying first_seen_at.
    """
    if seen_timestamp is None:
        seen_timestamp = datetime.now(timezone.utc).isoformat()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE jobs
            SET last_seen_at = ?
            WHERE source = ? AND source_job_id = ?
            """,
            (seen_timestamp, source, source_job_id),
        )
        return cursor.rowcount > 0


def insert_job(conn: sqlite3.Connection, job: Job) -> bool:
    """
    Inserts a new job or updates last_seen_at if the job already exists.

    Returns:
        bool: True if inserted as a new job, False if job already existed and was updated.
    """
    now = datetime.now(timezone.utc).isoformat()
    seen_time = job.fetched_at or now

    if job_exists(conn, job.source, job.source_job_id):
        update_last_seen(conn, job.source, job.source_job_id, seen_time)
        return False

    first_seen = job.first_seen_at or seen_time
    last_seen = job.last_seen_at or seen_time

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO jobs (
                source, source_job_id, title, company, location, description, url,
                created_at, fetched_at, salary_min, salary_max, salary_currency,
                employment_type, category, fingerprint, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.source,
                job.source_job_id,
                job.title,
                job.company,
                job.location,
                job.description,
                job.url,
                job.created_at,
                job.fetched_at,
                job.salary_min,
                job.salary_max,
                job.salary_currency,
                job.employment_type,
                job.category,
                job.fingerprint,
                first_seen,
                last_seen,
            ),
        )
        job.id = cursor.lastrowid
    return True


def insert_jobs(conn: sqlite3.Connection, jobs: List[Job]) -> Tuple[int, int]:
    """
    Inserts a list of jobs into the database.

    Returns:
        Tuple[int, int]: (new_jobs_count, existing_jobs_count)
    """
    new_count = 0
    existing_count = 0
    for job in jobs:
        if insert_job(conn, job):
            new_count += 1
        else:
            existing_count += 1
    return new_count, existing_count


def get_all_jobs(conn: sqlite3.Connection) -> List[Job]:
    """Retrieves all jobs stored in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY id ASC")
    return [_row_to_job(row) for row in cursor.fetchall()]


def get_jobs_map(conn: sqlite3.Connection) -> Dict[int, Job]:
    """Retrieves a dictionary mapping job_id to Job object."""
    jobs = get_all_jobs(conn)
    return {job.id: job for job in jobs if job.id is not None}


def get_new_jobs(
    conn: sqlite3.Connection, since_timestamp: Optional[str] = None
) -> List[Job]:
    """Retrieves jobs where first_seen_at >= since_timestamp."""
    cursor = conn.cursor()
    if since_timestamp:
        cursor.execute(
            "SELECT * FROM jobs WHERE first_seen_at >= ? ORDER BY first_seen_at DESC",
            (since_timestamp,),
        )
    else:
        cursor.execute("SELECT * FROM jobs ORDER BY first_seen_at DESC")
    return [_row_to_job(row) for row in cursor.fetchall()]


def get_recent_jobs(conn: sqlite3.Connection, limit: int = 50) -> List[Job]:
    """Retrieves the most recently observed jobs ordered by last_seen_at DESC."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM jobs ORDER BY last_seen_at DESC LIMIT ?", (limit,)
    )
    return [_row_to_job(row) for row in cursor.fetchall()]


def save_match_result(conn: sqlite3.Connection, match: MatchResult) -> bool:
    """
    Saves or replaces a MatchResult record in the job_matches table.
    """
    if not match.job_id:
        return False

    with conn:
        conn.execute(
            """
            INSERT INTO job_matches (
                job_id, similarity_score, skill_score, rule_score, final_score,
                match_status, matched_skills, missing_skills, reasons, calculated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                similarity_score=excluded.similarity_score,
                skill_score=excluded.skill_score,
                rule_score=excluded.rule_score,
                final_score=excluded.final_score,
                match_status=excluded.match_status,
                matched_skills=excluded.matched_skills,
                missing_skills=excluded.missing_skills,
                reasons=excluded.reasons,
                calculated_at=excluded.calculated_at
            """,
            (
                match.job_id,
                match.similarity_score,
                match.skill_score,
                match.rule_score,
                match.final_score,
                match.match_status,
                json.dumps(match.matched_skills),
                json.dumps(match.missing_skills),
                json.dumps(match.reasons),
                match.calculated_at,
            ),
        )
    return True


def save_match_results(conn: sqlite3.Connection, matches: List[MatchResult]) -> int:
    """Saves multiple MatchResult records to the database."""
    count = 0
    for match in matches:
        if save_match_result(conn, match):
            count += 1
    return count


def get_stored_matches(conn: sqlite3.Connection) -> List[MatchResult]:
    """
    Retrieves stored match results joined with job details.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT m.*, j.source_job_id, j.title, j.company, j.location
        FROM job_matches m
        JOIN jobs j ON m.job_id = j.id
        ORDER BY m.final_score DESC
        """
    )
    results = []
    for row in cursor.fetchall():
        matched_skills = json.loads(row["matched_skills"]) if row["matched_skills"] else []
        missing_skills = json.loads(row["missing_skills"]) if row["missing_skills"] else []
        reasons = json.loads(row["reasons"]) if row["reasons"] else []
        results.append(
            MatchResult(
                job_id=row["job_id"],
                source_job_id=row["source_job_id"],
                title=row["title"],
                company=row["company"] or "",
                location=row["location"] or "",
                similarity_score=row["similarity_score"],
                skill_score=row["skill_score"],
                rule_score=row["rule_score"],
                final_score=row["final_score"],
                match_status=row["match_status"],
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                reasons=reasons,
                calculated_at=row["calculated_at"],
            )
        )
    return results


def get_notified_job_ids(
    conn: sqlite3.Connection, notification_type: str = "telegram_digest"
) -> Set[int]:
    """
    Retrieves the set of job_ids that have already been notified for a given notification type.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT job_id FROM job_notifications WHERE notification_type = ?",
        (notification_type,),
    )
    return {row["job_id"] for row in cursor.fetchall()}


def record_notifications(
    conn: sqlite3.Connection,
    job_ids: List[int],
    notification_type: str = "telegram_digest",
) -> int:
    """
    Records successful notification delivery for a list of job IDs.
    """
    if not job_ids:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted_count = 0
    with conn:
        for job_id in job_ids:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO job_notifications (job_id, notification_type, sent_at)
                VALUES (?, ?, ?)
                """,
                (job_id, notification_type, now),
            )
            if cursor.rowcount > 0:
                inserted_count += 1
    return inserted_count
