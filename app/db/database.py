"""
SQLite database interface and operations for job storage, match results, notification tracking,
pipeline run history, and operational health alerts.
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
    Initializes the SQLite database and creates jobs, job_matches, job_notifications,
    pipeline_runs, and health_alerts tables.
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
                match_category TEXT,
                role_family TEXT,
                canonical_role TEXT,
                experience_match TEXT,
                skill_gaps TEXT,
                role_score REAL,
                experience_score REAL,
                education_score REAL,
                location_score REAL,
                seniority_score REAL,
                overall_score REAL,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                UNIQUE(job_id)
            );
            """
        )
        # Idempotent migration for existing database schema
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(job_matches)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        new_cols = [
            ("match_category", "TEXT"),
            ("role_family", "TEXT"),
            ("canonical_role", "TEXT"),
            ("experience_match", "TEXT"),
            ("skill_gaps", "TEXT"),
            ("role_score", "REAL"),
            ("experience_score", "REAL"),
            ("education_score", "REAL"),
            ("location_score", "REAL"),
            ("seniority_score", "REAL"),
            ("overall_score", "REAL"),
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE job_matches ADD COLUMN {col_name} {col_type}")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                jobs_fetched INTEGER DEFAULT 0,
                new_jobs INTEGER DEFAULT 0,
                existing_jobs INTEGER DEFAULT 0,
                matches_found INTEGER DEFAULT 0,
                eligible_notifications INTEGER DEFAULT 0,
                notifications_sent INTEGER DEFAULT 0,
                failed_sources INTEGER DEFAULT 0,
                error_message TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS health_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                resolved_at TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_health_alerts_type ON health_alerts(alert_type);
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                jobs_fetched INTEGER DEFAULT 0,
                new_jobs INTEGER DEFAULT 0,
                error_message TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_source_runs_source ON source_runs(source);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_source_runs_started ON source_runs(started_at);
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tailored_resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                match_score REAL NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                resume_content TEXT,
                changes TEXT,
                warnings TEXT,
                validation_result TEXT,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tailored_resumes_job ON tailored_resumes(job_id);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tailored_resumes_status ON tailored_resumes(status);
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

    skill_gaps_val = json.dumps(match.skill_gaps) if match.skill_gaps is not None else json.dumps(match.missing_skills)

    with conn:
        conn.execute(
            """
            INSERT INTO job_matches (
                job_id, similarity_score, skill_score, rule_score, final_score,
                match_status, matched_skills, missing_skills, reasons, calculated_at,
                match_category, role_family, canonical_role, experience_match, skill_gaps,
                role_score, experience_score, education_score, location_score, seniority_score, overall_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                similarity_score=excluded.similarity_score,
                skill_score=excluded.skill_score,
                rule_score=excluded.rule_score,
                final_score=excluded.final_score,
                match_status=excluded.match_status,
                matched_skills=excluded.matched_skills,
                missing_skills=excluded.missing_skills,
                reasons=excluded.reasons,
                calculated_at=excluded.calculated_at,
                match_category=excluded.match_category,
                role_family=excluded.role_family,
                canonical_role=excluded.canonical_role,
                experience_match=excluded.experience_match,
                skill_gaps=excluded.skill_gaps,
                role_score=excluded.role_score,
                experience_score=excluded.experience_score,
                education_score=excluded.education_score,
                location_score=excluded.location_score,
                seniority_score=excluded.seniority_score,
                overall_score=excluded.overall_score
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
                match.match_category,
                match.role_family,
                match.canonical_role,
                match.experience_match or match.experience_status,
                skill_gaps_val,
                match.role_score,
                match.experience_score,
                match.education_score,
                match.location_score,
                match.seniority_score,
                match.overall_score or match.final_score,
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
        keys = row.keys()
        matched_skills = json.loads(row["matched_skills"]) if row["matched_skills"] else []
        missing_skills = json.loads(row["missing_skills"]) if row["missing_skills"] else []
        reasons = json.loads(row["reasons"]) if row["reasons"] else []
        skill_gaps_str = row["skill_gaps"] if "skill_gaps" in keys else None
        skill_gaps = json.loads(skill_gaps_str) if skill_gaps_str else missing_skills

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
                match_category=row["match_category"] if "match_category" in keys and row["match_category"] else "NOT_RELEVANT",
                role_family=row["role_family"] if "role_family" in keys else None,
                canonical_role=row["canonical_role"] if "canonical_role" in keys else None,
                experience_match=row["experience_match"] if "experience_match" in keys and row["experience_match"] else "NOT_ELIGIBLE",
                skill_gaps=skill_gaps,
                role_score=row["role_score"] if "role_score" in keys and row["role_score"] is not None else 0.0,
                experience_score=row["experience_score"] if "experience_score" in keys and row["experience_score"] is not None else 0.0,
                education_score=row["education_score"] if "education_score" in keys and row["education_score"] is not None else 0.0,
                location_score=row["location_score"] if "location_score" in keys and row["location_score"] is not None else 0.0,
                seniority_score=row["seniority_score"] if "seniority_score" in keys and row["seniority_score"] is not None else 0.0,
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


# ---------------------------------------------------------------------
# Phase 4: Pipeline Run Tracking & Operational Health Alert DB Functions
# ---------------------------------------------------------------------


def record_pipeline_start(
    conn: sqlite3.Connection, started_at: Optional[str] = None
) -> int:
    """
    Records the start of a monitoring pipeline run with status RUNNING.

    Returns:
        int: The inserted pipeline run ID.
    """
    if not started_at:
        started_at = datetime.now(timezone.utc).isoformat()

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO pipeline_runs (started_at, status)
            VALUES (?, ?)
            """,
            (started_at, "RUNNING"),
        )
        return cursor.lastrowid


def record_pipeline_finish(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    finished_at: Optional[str] = None,
    jobs_fetched: int = 0,
    new_jobs: int = 0,
    existing_jobs: int = 0,
    matches_found: int = 0,
    eligible_notifications: int = 0,
    notifications_sent: int = 0,
    failed_sources: int = 0,
    error_message: Optional[str] = None,
) -> bool:
    """
    Updates an existing pipeline_runs record upon completion or failure.
    """
    if not finished_at:
        finished_at = datetime.now(timezone.utc).isoformat()

    with conn:
        cursor = conn.execute(
            """
            UPDATE pipeline_runs
            SET finished_at = ?,
                status = ?,
                jobs_fetched = ?,
                new_jobs = ?,
                existing_jobs = ?,
                matches_found = ?,
                eligible_notifications = ?,
                notifications_sent = ?,
                failed_sources = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                finished_at,
                status,
                jobs_fetched,
                new_jobs,
                existing_jobs,
                matches_found,
                eligible_notifications,
                notifications_sent,
                failed_sources,
                error_message,
                run_id,
            ),
        )
        return cursor.rowcount > 0


def _format_pipeline_run_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    """Formats pipeline run DB row into dictionary with deferred fields."""
    if not row:
        return None
    d = dict(row)
    eligible = d.get("eligible_notifications", 0) or 0
    sent = d.get("notifications_sent", 0) or 0
    d["notifications_eligible"] = eligible
    d["notifications_deferred"] = max(0, eligible - sent)
    d["notifications_failed"] = 0
    return d


def get_last_pipeline_run(conn: sqlite3.Connection) -> Optional[dict]:
    """
    Retrieves the most recent pipeline run record.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    return _format_pipeline_run_dict(row)


def get_last_successful_pipeline_run(conn: sqlite3.Connection) -> Optional[dict]:
    """
    Retrieves the most recent pipeline run record with status 'SUCCESS' or 'PARTIAL_FAILURE'.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM pipeline_runs
        WHERE status IN ('SUCCESS', 'PARTIAL_FAILURE')
        ORDER BY id DESC LIMIT 1
        """
    )
    row = cursor.fetchone()
    return _format_pipeline_run_dict(row)


def record_health_alert(
    conn: sqlite3.Connection,
    alert_type: str = "stale_pipeline",
    sent_at: Optional[str] = None,
) -> int:
    """
    Records an unresolved operational health alert.

    Returns:
        int: Inserted alert record ID.
    """
    if not sent_at:
        sent_at = datetime.now(timezone.utc).isoformat()

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO health_alerts (alert_type, sent_at)
            VALUES (?, ?)
            """,
            (alert_type, sent_at),
        )
        return cursor.lastrowid


def get_unresolved_health_alert(
    conn: sqlite3.Connection, alert_type: str = "stale_pipeline"
) -> Optional[dict]:
    """
    Retrieves an active unresolved health alert for a given alert type.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM health_alerts
        WHERE alert_type = ? AND resolved_at IS NULL
        ORDER BY id DESC LIMIT 1
        """,
        (alert_type,),
    )
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


def resolve_health_alerts(
    conn: sqlite3.Connection,
    alert_type: str = "stale_pipeline",
    resolved_at: Optional[str] = None,
) -> int:
    """
    Marks all unresolved health alerts of a given type as resolved.

    Returns:
        int: Number of resolved alert records.
    """
    if not resolved_at:
        resolved_at = datetime.now(timezone.utc).isoformat()

    with conn:
        cursor = conn.execute(
            """
            UPDATE health_alerts
            SET resolved_at = ?
            WHERE alert_type = ? AND resolved_at IS NULL
            """,
            (resolved_at, alert_type),
        )
        return cursor.rowcount


# ---------------------------------------------------------------------
# Phase 5: Per-Source Run Tracking DB Functions
# ---------------------------------------------------------------------


def record_source_run_start(
    conn: sqlite3.Connection, source: str, started_at: Optional[str] = None
) -> int:
    """
    Records the start of an ingestion run for a specific source.
    """
    if not started_at:
        started_at = datetime.now(timezone.utc).isoformat()

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO source_runs (source, started_at, status)
            VALUES (?, ?, ?)
            """,
            (source, started_at, "RUNNING"),
        )
        return cursor.lastrowid


def record_source_run_finish(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    finished_at: Optional[str] = None,
    jobs_fetched: int = 0,
    new_jobs: int = 0,
    error_message: Optional[str] = None,
) -> bool:
    """
    Updates a source_runs record upon source execution completion.
    """
    if not finished_at:
        finished_at = datetime.now(timezone.utc).isoformat()

    with conn:
        cursor = conn.execute(
            """
            UPDATE source_runs
            SET finished_at = ?,
                status = ?,
                jobs_fetched = ?,
                new_jobs = ?,
                error_message = ?
            WHERE id = ?
            """,
            (finished_at, status, jobs_fetched, new_jobs, error_message, run_id),
        )
        return cursor.rowcount > 0


def get_last_source_run(conn: sqlite3.Connection, source: str) -> Optional[dict]:
    """
    Retrieves the most recent completed source run record for a given source.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM source_runs
        WHERE source = ? AND finished_at IS NOT NULL
        ORDER BY id DESC LIMIT 1
        """,
        (source,),
    )
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


# ---------------------------------------------------------------------
# Phase 7: Tailored Resumes DB Functions
# ---------------------------------------------------------------------


def save_tailored_resume(
    conn: sqlite3.Connection,
    job_id: int,
    match_score: float,
    provider: str,
    model: str,
    status: str,
    resume_content: Optional[dict] = None,
    changes: Optional[list] = None,
    warnings: Optional[list] = None,
    validation_result: Optional[dict] = None,
    created_at: Optional[str] = None,
) -> int:
    """
    Saves a new tailored resume draft record in tailored_resumes table.
    """
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()

    resume_json = json.dumps(resume_content) if resume_content is not None else None
    changes_json = json.dumps(changes) if changes is not None else None
    warnings_json = json.dumps(warnings) if warnings is not None else None
    validation_json = json.dumps(validation_result) if validation_result is not None else None

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO tailored_resumes (
                job_id, match_score, provider, model, status,
                resume_content, changes, warnings, validation_result, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                match_score,
                provider,
                model,
                status,
                resume_json,
                changes_json,
                warnings_json,
                validation_json,
                created_at,
            ),
        )
        return cursor.lastrowid


def get_tailored_resume_by_id(
    conn: sqlite3.Connection, draft_id: int
) -> Optional[dict]:
    """
    Retrieves a tailored resume draft by its ID, joined with job information.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tr.*, j.title AS job_title, j.company AS job_company, j.location AS job_location,
               j.description AS job_description, j.url AS job_url
        FROM tailored_resumes tr
        LEFT JOIN jobs j ON tr.job_id = j.id
        WHERE tr.id = ?
        """,
        (draft_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["resume_content"] = json.loads(d["resume_content"]) if d["resume_content"] else None
    d["changes"] = json.loads(d["changes"]) if d["changes"] else []
    d["warnings"] = json.loads(d["warnings"]) if d["warnings"] else []
    d["validation_result"] = json.loads(d["validation_result"]) if d["validation_result"] else None
    return d


def get_tailored_resumes_by_job(
    conn: sqlite3.Connection, job_id: int
) -> List[dict]:
    """
    Retrieves all tailored resume drafts for a specific job_id.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tr.*, j.title AS job_title, j.company AS job_company
        FROM tailored_resumes tr
        LEFT JOIN jobs j ON tr.job_id = j.id
        WHERE tr.job_id = ?
        ORDER BY tr.id DESC

        """,
        (job_id,),
    )
    results = []
    for row in cursor.fetchall():
        d = dict(row)
        d["resume_content"] = json.loads(d["resume_content"]) if d["resume_content"] else None
        d["changes"] = json.loads(d["changes"]) if d["changes"] else []
        d["warnings"] = json.loads(d["warnings"]) if d["warnings"] else []
        d["validation_result"] = json.loads(d["validation_result"]) if d["validation_result"] else None
        results.append(d)
    return results


def update_tailored_resume_status(
    conn: sqlite3.Connection,
    draft_id: int,
    status: str,
    reviewed_at: Optional[str] = None,
) -> bool:
    """
    Updates the status and optional reviewed_at timestamp of a tailored resume draft.
    """
    if reviewed_at is None and status in ("APPROVED", "REJECTED"):
        reviewed_at = datetime.now(timezone.utc).isoformat()

    with conn:
        cursor = conn.execute(
            """
            UPDATE tailored_resumes
            SET status = ?, reviewed_at = ?
            WHERE id = ?
            """,
            (status, reviewed_at, draft_id),
        )
        return cursor.rowcount > 0


