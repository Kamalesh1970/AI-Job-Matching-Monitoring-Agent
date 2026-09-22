"""
Orchestrated Pipeline Service for Phase 4 scheduled job monitoring.
Coordinates Ingestion (Phase 1), Matching (Phase 2), and Digest (Phase 3)
with fault isolation, metrics tracking, and health updates.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
import sqlite3

from app.config import Config
from app.db.database import (
    get_all_jobs,
    get_jobs_map,
    get_last_source_run,
    get_notified_job_ids,
    get_stored_matches,
    initialize_database,
    insert_job,
    record_notifications,
    record_pipeline_finish,
    record_pipeline_start,
    record_source_run_finish,
    record_source_run_start,
    save_match_results,
)
from app.db.models import Job, MatchResult, SourceStatus
from app.services.digest_service import DigestService
from app.services.health_service import HealthService
from app.services.matching_service import MatchingService
from app.services.telegram_notifier import TelegramNotifier
from app.sources.adzuna import AdzunaJobSource
from app.sources.gmail import GmailAPIClient, IndeedAlertEmailSource, LinkedInAlertEmailSource
from app.sources.internshala import InternshalaJobSource
from app.sources.jooble import JoobleJobSource
from app.sources.jsearch import JSearchJobSource
from app.sources.serpapi import SerpApiJobSource
from app.llm.tailoring_service import ResumeTailoringService



logger = logging.getLogger("app.services.pipeline_service")



class PipelineStatus:
    """Pipeline execution status constants."""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    FAILED = "FAILED"


@dataclass
class PipelineRunSummary:
    """Structured summary of a pipeline execution run."""

    status: str
    started_at: str
    finished_at: str
    duration_seconds: float
    jobs_fetched: int = 0
    new_jobs: int = 0
    existing_jobs: int = 0
    matches_found: int = 0
    eligible_notifications: int = 0
    notifications_sent: int = 0
    notifications_deferred: int = 0
    notifications_failed: int = 0
    failed_sources: int = 0
    error_message: Optional[str] = None

    @property
    def notifications_eligible(self) -> int:
        """Alias for eligible_notifications for API / consumer compatibility."""
        return self.eligible_notifications


class PipelineService:
    """
    Orchestration service for executing the end-to-end job monitoring pipeline cleanly and resiliently.
    """

    def __init__(self, config: Optional[Config] = None):
        """Initializes PipelineService."""
        self.config = config

    def print_pipeline_summary(self, summary: PipelineRunSummary):
        """Prints formatted pipeline run summary block."""
        print("\n" + "=" * 50)
        print("PIPELINE RUN SUMMARY")
        print("=" * 50)
        print(f"\nStatus: {summary.status}")
        print(f"Duration: {summary.duration_seconds:.1f}s\n")
        print(f"Jobs fetched: {summary.jobs_fetched}")
        print(f"New jobs: {summary.new_jobs}")
        print(f"Existing jobs: {summary.existing_jobs}\n")
        print(f"Matches found: {summary.matches_found}")
        print(f"Eligible notifications: {summary.eligible_notifications}")
        print(f"Notifications sent: {summary.notifications_sent}")
        print(f"Notifications deferred: {summary.notifications_deferred}")
        print(f"Notifications failed: {summary.notifications_failed}\n")
        print(f"Failed sources: {summary.failed_sources}")
        if summary.error_message:
            print(f"Error message: {summary.error_message}")
        print("\n" + "=" * 50 + "\n")

    def run_monitoring_pipeline(
        self,
        config: Optional[Config] = None,
        conn: Optional[sqlite3.Connection] = None,
        notifier: Optional[TelegramNotifier] = None,
    ) -> PipelineRunSummary:
        """
        Executes one full monitoring cycle (Ingestion -> Matching -> Digest -> Health check).

        Fault Isolation: Component or network errors are caught, logged, and isolated
        to ensure the scheduler daemon remains alive and health status is updated accurately.
        """
        cfg = config or self.config
        if not cfg:
            raise ValueError("Configuration object is required to run monitoring pipeline.")

        close_conn = False
        if conn is None:
            conn = initialize_database(cfg.db_path)
            close_conn = True

        start_dt = datetime.now(timezone.utc)
        started_at = start_dt.isoformat()
        run_id = record_pipeline_start(conn, started_at=started_at)

        logger.info("Starting monitoring pipeline run #%d...", run_id)

        jobs_fetched = 0
        new_jobs = 0
        existing_jobs = 0
        matches_found = 0
        eligible_notifications = 0
        notifications_sent = 0
        failed_sources = 0
        error_message = None

        critical_failure = False

        # ----------------------------------------------------
        # Phase 1: Ingestion - Adzuna
        # ----------------------------------------------------
        try:
            adzuna_source = AdzunaJobSource(
                app_id=cfg.adzuna_app_id,
                app_key=cfg.adzuna_app_key,
                country=cfg.adzuna_country,
            )

            for keyword in cfg.keywords:
                try:
                    jobs, success = adzuna_source.fetch_jobs_for_keyword(
                        keyword=keyword,
                        max_pages=cfg.adzuna_max_pages,
                        results_per_page=cfg.adzuna_results_per_page,
                    )
                    if not success:
                        failed_sources += 1

                    jobs_fetched += len(jobs)
                    for job in jobs:
                        is_new = insert_job(conn, job)
                        if is_new:
                            new_jobs += 1
                        else:
                            existing_jobs += 1

                except Exception as e:
                    logger.error(
                        "Ingestion failure for keyword '%s': %s", keyword, str(e)
                    )
                    failed_sources += 1

        except Exception as e:
            logger.error("Critical failure during Adzuna Ingestion setup: %s", str(e))
            failed_sources += 1
            error_message = f"Adzuna Ingestion error: {str(e)}"

        # ----------------------------------------------------
        # Phase 5: Ingestion - Internshala (Yellow-tier)
        # ----------------------------------------------------
        if cfg.internshala_enabled:
            ish_due = True
            last_ish_run = get_last_source_run(conn, "Internshala")
            if last_ish_run and last_ish_run.get("finished_at"):
                try:
                    last_finished_raw = last_ish_run["finished_at"]
                    last_finished = datetime.fromisoformat(last_finished_raw)
                    if last_finished.tzinfo is None:
                        last_finished = last_finished.replace(tzinfo=timezone.utc)
                    hours_since = (start_dt - last_finished).total_seconds() / 3600.0
                    if hours_since < cfg.internshala_interval_hours:
                        ish_due = False
                        logger.info(
                            "Internshala fetch skipped: last run was %.1f hours ago (interval: %dh)",
                            hours_since,
                            cfg.internshala_interval_hours,
                        )
                except Exception as e:
                    logger.warning("Error parsing last Internshala run timestamp: %s", str(e))

            if ish_due:
                ish_run_id = record_source_run_start(conn, "Internshala", started_at=started_at)
                try:
                    ish_source = InternshalaJobSource(
                        request_delay_min=cfg.internshala_request_delay_min,
                        request_delay_max=cfg.internshala_request_delay_max,
                        timeout=15,
                    )
                    source_res = ish_source.fetch_source_jobs(
                        keywords=cfg.internshala_keywords,
                        max_pages=cfg.internshala_max_pages,
                    )

                    ish_new_jobs = 0
                    for job in source_res.jobs:
                        jobs_fetched += 1
                        is_new = insert_job(conn, job)
                        if is_new:
                            new_jobs += 1
                            ish_new_jobs += 1
                        else:
                            existing_jobs += 1

                    record_source_run_finish(
                        conn,
                        run_id=ish_run_id,
                        status=source_res.status,
                        jobs_fetched=source_res.total_fetched,
                        new_jobs=ish_new_jobs,
                        error_message=source_res.error_message,
                    )

                    if source_res.status in (SourceStatus.FAILED, SourceStatus.BLOCKED, SourceStatus.PARTIAL_FAILURE):
                        failed_sources += 1
                        logger.warning(
                            "Internshala execution finished with status '%s' (error: %s)",
                            source_res.status,
                            source_res.error_message,
                        )

                except Exception as e:
                    logger.error("Failure during Internshala execution: %s", str(e))
                    failed_sources += 1
                    record_source_run_finish(
                        conn,
                        run_id=ish_run_id,
                        status=SourceStatus.FAILED,
                        jobs_fetched=0,
                        new_jobs=0,
                        error_message=str(e),
                    )


        # ----------------------------------------------------
        # Phase 6: Ingestion - Gmail Alert Emails (LinkedIn & Indeed)
        # ----------------------------------------------------
        if cfg.gmail_enabled:
            logger.info("Gmail API ingestion is enabled. Initializing Gmail client...")
            try:
                gmail_client = GmailAPIClient(
                    credentials_path=cfg.gmail_credentials_path,
                    token_path=cfg.gmail_token_path,
                )

                # 1. LinkedIn Email Alerts
                li_source = LinkedInAlertEmailSource(
                    gmail_client=gmail_client,
                    query=cfg.gmail_linkedin_query,
                    query_limit=cfg.gmail_query_limit,
                )
                li_run_id = record_source_run_start(conn, "LinkedIn Email Alert", started_at=started_at)
                try:
                    li_res = li_source.fetch_source_jobs()
                    li_new_count = 0
                    for job in li_res.jobs:
                        jobs_fetched += 1
                        if insert_job(conn, job):
                            new_jobs += 1
                            li_new_count += 1
                        else:
                            existing_jobs += 1

                    record_source_run_finish(
                        conn,
                        run_id=li_run_id,
                        status=li_res.status,
                        jobs_fetched=li_res.total_fetched,
                        new_jobs=li_new_count,
                        error_message=li_res.error_message,
                    )
                    if li_res.status in (SourceStatus.FAILED, SourceStatus.BLOCKED, SourceStatus.PARTIAL_FAILURE):
                        failed_sources += 1
                except Exception as e:
                    logger.error("Failure during LinkedIn email alert ingestion: %s", str(e))
                    failed_sources += 1
                    record_source_run_finish(
                        conn,
                        run_id=li_run_id,
                        status=SourceStatus.FAILED,
                        jobs_fetched=0,
                        new_jobs=0,
                        error_message=str(e),
                    )

                # 2. Indeed Email Alerts
                ind_source = IndeedAlertEmailSource(
                    gmail_client=gmail_client,
                    query=cfg.gmail_indeed_query,
                    query_limit=cfg.gmail_query_limit,
                )
                ind_run_id = record_source_run_start(conn, "Indeed Email Alert", started_at=started_at)
                try:
                    ind_res = ind_source.fetch_source_jobs()
                    ind_new_count = 0
                    for job in ind_res.jobs:
                        jobs_fetched += 1
                        if insert_job(conn, job):
                            new_jobs += 1
                            ind_new_count += 1
                        else:
                            existing_jobs += 1

                    record_source_run_finish(
                        conn,
                        run_id=ind_run_id,
                        status=ind_res.status,
                        jobs_fetched=ind_res.total_fetched,
                        new_jobs=ind_new_count,
                        error_message=ind_res.error_message,
                    )
                    if ind_res.status in (SourceStatus.FAILED, SourceStatus.BLOCKED, SourceStatus.PARTIAL_FAILURE):
                        failed_sources += 1
                except Exception as e:
                    logger.error("Failure during Indeed email alert ingestion: %s", str(e))
                    failed_sources += 1
                    record_source_run_finish(
                        conn,
                        run_id=ind_run_id,
                        status=SourceStatus.FAILED,
                        jobs_fetched=0,
                        new_jobs=0,
                        error_message=str(e),
                    )

            except Exception as e:
                logger.error("Gmail API client initialization error: %s", str(e))
                failed_sources += 1

        # ----------------------------------------------------
        # Phase 8: Ingestion - Jooble
        # ----------------------------------------------------
        if cfg.source_jooble_enabled and cfg.jooble_api_key:
            jooble_run_id = record_source_run_start(conn, "Jooble", started_at=started_at)
            try:
                jooble_source = JoobleJobSource(api_key=cfg.jooble_api_key, timeout=15)
                jooble_res = jooble_source.fetch_source_jobs(keywords=cfg.keywords, config=cfg)
                jooble_new_count = 0
                for job in jooble_res.jobs:
                    jobs_fetched += 1
                    if insert_job(conn, job):
                        new_jobs += 1
                        jooble_new_count += 1
                    else:
                        existing_jobs += 1

                record_source_run_finish(
                    conn,
                    run_id=jooble_run_id,
                    status=jooble_res.status,
                    jobs_fetched=jooble_res.total_fetched,
                    new_jobs=jooble_new_count,
                    error_message=jooble_res.error_message,
                )
                if jooble_res.status in (SourceStatus.FAILED, SourceStatus.BLOCKED, SourceStatus.PARTIAL_FAILURE):
                    failed_sources += 1
            except Exception as e:
                logger.error("Failure during Jooble job ingestion: %s", str(e))
                failed_sources += 1
                record_source_run_finish(
                    conn,
                    run_id=jooble_run_id,
                    status=SourceStatus.FAILED,
                    jobs_fetched=0,
                    new_jobs=0,
                    error_message=str(e),
                )

        # ----------------------------------------------------
        # Phase 9: Ingestion - JSearch (RapidAPI)
        # ----------------------------------------------------
        if cfg.source_jsearch_enabled and cfg.jsearch_api_key:
            jsearch_run_id = record_source_run_start(conn, "JSearch", started_at=started_at)
            try:
                jsearch_source = JSearchJobSource(
                    api_key=cfg.jsearch_api_key,
                    rapidapi_host=cfg.jsearch_rapidapi_host,
                    timeout=15,
                )
                jsearch_res = jsearch_source.fetch_source_jobs(keywords=cfg.keywords, config=cfg)
                jsearch_new_count = 0
                for job in jsearch_res.jobs:
                    jobs_fetched += 1
                    if insert_job(conn, job):
                        new_jobs += 1
                        jsearch_new_count += 1
                    else:
                        existing_jobs += 1

                record_source_run_finish(
                    conn,
                    run_id=jsearch_run_id,
                    status=jsearch_res.status,
                    jobs_fetched=jsearch_res.total_fetched,
                    new_jobs=jsearch_new_count,
                    error_message=jsearch_res.error_message,
                )
                if jsearch_res.status in (SourceStatus.FAILED, SourceStatus.BLOCKED, SourceStatus.PARTIAL_FAILURE):
                    failed_sources += 1
            except Exception as e:
                logger.error("Failure during JSearch job ingestion: %s", str(e))
                failed_sources += 1
                record_source_run_finish(
                    conn,
                    run_id=jsearch_run_id,
                    status=SourceStatus.FAILED,
                    jobs_fetched=0,
                    new_jobs=0,
                    error_message=str(e),
                )

        # ----------------------------------------------------
        # Phase 10: Ingestion - SerpApi (Google Jobs)
        # ----------------------------------------------------
        if cfg.source_serpapi_enabled and cfg.serpapi_key:
            serpapi_run_id = record_source_run_start(conn, "SerpApi", started_at=started_at)
            try:
                serpapi_source = SerpApiJobSource(api_key=cfg.serpapi_key, timeout=15)
                serpapi_res = serpapi_source.fetch_source_jobs(keywords=cfg.keywords, config=cfg)
                serpapi_new_count = 0
                for job in serpapi_res.jobs:
                    jobs_fetched += 1
                    if insert_job(conn, job):
                        new_jobs += 1
                        serpapi_new_count += 1
                    else:
                        existing_jobs += 1

                record_source_run_finish(
                    conn,
                    run_id=serpapi_run_id,
                    status=serpapi_res.status,
                    jobs_fetched=serpapi_res.total_fetched,
                    new_jobs=serpapi_new_count,
                    error_message=serpapi_res.error_message,
                )
                if serpapi_res.status in (SourceStatus.FAILED, SourceStatus.BLOCKED, SourceStatus.PARTIAL_FAILURE):
                    failed_sources += 1
            except Exception as e:
                logger.error("Failure during SerpApi job ingestion: %s", str(e))
                failed_sources += 1
                record_source_run_finish(
                    conn,
                    run_id=serpapi_run_id,
                    status=SourceStatus.FAILED,
                    jobs_fetched=0,
                    new_jobs=0,
                    error_message=str(e),
                )

        # ----------------------------------------------------
        # Phase 2: Resume Matching Engine
        # ----------------------------------------------------

        match_results: List[MatchResult] = []
        try:
            all_stored_jobs = get_all_jobs(conn)
            if all_stored_jobs:
                matching_service = MatchingService(config=cfg)
                resume = matching_service.prepare_resume()
                match_results = matching_service.match_all_jobs(
                    resume=resume, jobs=all_stored_jobs
                )
                save_match_results(conn, match_results)
                matches_found = len(match_results)
            else:
                logger.warning("No jobs in database to execute Phase 2 matching.")

        except FileNotFoundError as e:
            logger.error("Resume file missing: %s", str(e))
            error_message = f"Resume missing: {str(e)}"
            critical_failure = True
        except Exception as e:
            logger.error("Critical failure during Phase 2 matching: %s", str(e), exc_info=True)
            error_message = f"Matching error: {str(e)}"
            critical_failure = True

        # ----------------------------------------------------
        # Phase 7: Gemini API LLM Resume Tailoring
        # ----------------------------------------------------
        if cfg.llm_enabled and match_results:
            logger.info("LLM Resume Tailoring is enabled. Processing strong matches...")
            try:
                tailoring_service = ResumeTailoringService(config=cfg)
                all_jobs = get_jobs_map(conn)
                raw_thresh = cfg.llm_match_threshold
                eff_thresh = raw_thresh * 100.0 if raw_thresh <= 1.0 else raw_thresh

                for match in match_results:
                    if match.final_score >= eff_thresh and match.job_id:
                        job = all_jobs.get(match.job_id)
                        if job:
                            tail_res = tailoring_service.tailor_resume_for_job(conn, job, match)
                            if tail_res and tail_res.get("id"):
                                match.draft_id = tail_res.get("id")
            except Exception as e:
                logger.error("Error during Phase 7 LLM Resume Tailoring: %s", str(e))

        # ----------------------------------------------------
        # Phase 3: Telegram Digest
        # ----------------------------------------------------

        notifications_sent = 0
        notifications_failed = 0
        digest_failed = False
        try:
            if not match_results:
                match_results = get_stored_matches(conn)

            eligible = [
                m
                for m in match_results
                if getattr(m, "match_category", None) != "NOT_RELEVANT"
                and m.match_status != "FILTERED"
                and m.final_score >= cfg.telegram_min_match_score
            ]

            notified_set = get_notified_job_ids(conn, notification_type="telegram_digest")
            unnotified = [m for m in eligible if m.job_id not in notified_set]
            eligible_notifications = len(unnotified)

            if unnotified:
                jobs_map = get_jobs_map(conn)
                digest_service = DigestService(config=cfg)
                chunks = digest_service.build_digest_chunks(
                    matches=unnotified, jobs_map=jobs_map
                )

                if notifier is None:
                    notifier = TelegramNotifier(config=cfg)

                for chunk in chunks:
                    delivered = notifier.send_message(chunk.text)
                    if delivered:
                        notifications_sent += len(chunk.job_ids)
                        record_notifications(
                            conn, chunk.job_ids, notification_type="telegram_digest"
                        )
                    else:
                        notifications_failed += len(chunk.job_ids)
                        digest_failed = True

        except Exception as e:
            logger.error("Error during Phase 3 Telegram digest: %s", str(e))
            digest_failed = True

        notifications_deferred = max(
            0, eligible_notifications - notifications_sent - notifications_failed
        )

        # ----------------------------------------------------
        # Overall Status Determination
        # ----------------------------------------------------
        if critical_failure:
            overall_status = PipelineStatus.FAILED
        elif (
            failed_sources > 0
            or digest_failed
            or notifications_failed > 0
        ):
            overall_status = PipelineStatus.PARTIAL_FAILURE
        else:
            overall_status = PipelineStatus.SUCCESS

        finish_dt = datetime.now(timezone.utc)
        finished_at = finish_dt.isoformat()
        duration_seconds = (finish_dt - start_dt).total_seconds()

        record_pipeline_finish(
            conn=conn,
            run_id=run_id,
            status=overall_status,
            finished_at=finished_at,
            jobs_fetched=jobs_fetched,
            new_jobs=new_jobs,
            existing_jobs=existing_jobs,
            matches_found=matches_found,
            eligible_notifications=eligible_notifications,
            notifications_sent=notifications_sent,
            failed_sources=failed_sources,
            error_message=error_message,
        )

        summary = PipelineRunSummary(
            status=overall_status,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            jobs_fetched=jobs_fetched,
            new_jobs=new_jobs,
            existing_jobs=existing_jobs,
            matches_found=matches_found,
            eligible_notifications=eligible_notifications,
            notifications_sent=notifications_sent,
            notifications_deferred=notifications_deferred,
            notifications_failed=notifications_failed,
            failed_sources=failed_sources,
            error_message=error_message,
        )

        # ----------------------------------------------------
        # Operational Health Check & Alerting
        # ----------------------------------------------------
        try:
            health_service = HealthService(config=cfg)
            health_service.check_and_alert_health(
                conn=conn, config=cfg, notifier=notifier, reference_time=finish_dt
            )
        except Exception as e:
            logger.error("Error during operational health evaluation: %s", str(e))

        self.print_pipeline_summary(summary)

        if close_conn:
            conn.close()

        return summary
