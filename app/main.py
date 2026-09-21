"""
Main entry point for AI Job-Matching & Monitoring Agent.
Supports Phase 1 Ingestion, Phase 2 Resume Matching, Phase 3 Telegram Digest,
and Phase 4 Scheduled Monitoring & Heartbeat Service.
"""

import argparse
import logging
import os
import sqlite3
import sys
from typing import Dict, List, Optional


from app.config import Config, load_config
from app.db.database import (
    get_all_jobs,
    get_jobs_map,
    get_notified_job_ids,
    get_stored_matches,
    get_tailored_resume_by_id,
    initialize_database,
    insert_job,
    record_notifications,
    save_match_results,
    update_tailored_resume_status,
)
from app.db.models import Job, MatchResult
from app.llm.tailoring_service import ResumeTailoringService
from app.scheduler.scheduler import PipelineScheduler
from app.services.digest_service import DigestService
from app.services.matching_service import MatchingService
from app.services.pipeline_service import PipelineService
from app.services.telegram_notifier import TelegramNotifier
from app.sources.adzuna import AdzunaJobSource
from app.sources.gmail import GmailAPIClient, IndeedAlertEmailSource, LinkedInAlertEmailSource
from app.sources.internshala import InternshalaJobSource





def setup_logging():
    """Configures application-wide logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def format_salary(job: Job) -> str:
    """Formats salary range or returns N/A."""
    currency_symbol = "₹" if job.salary_currency == "INR" else (job.salary_currency or "")
    if job.salary_min is not None and job.salary_max is not None:
        if job.salary_min == job.salary_max:
            return f"{currency_symbol}{job.salary_min:,.0f}"
        return f"{currency_symbol}{job.salary_min:,.0f} - {currency_symbol}{job.salary_max:,.0f}"
    elif job.salary_min is not None:
        return f"From {currency_symbol}{job.salary_min:,.0f}"
    elif job.salary_max is not None:
        return f"Up to {currency_symbol}{job.salary_max:,.0f}"
    return "N/A"


def print_new_jobs(new_jobs: List[Job]):
    """Prints newly discovered jobs to console in a clean format."""
    print("\n" + "=" * 50)
    print("NEW JOBS DISCOVERED")
    print("=" * 50)

    if not new_jobs:
        print("No new jobs discovered during this execution.\n")
        return

    for idx, job in enumerate(new_jobs, start=1):
        salary_str = format_salary(job)
        print(f"\n[{idx}]")
        print(f"Title: {job.title}")
        print(f"Company: {job.company or 'Not specified'}")
        print(f"Location: {job.location or 'Not specified'}")
        print(f"Salary: {salary_str}")
        print(f"Source: {job.source}")
        print(f"URL: {job.url}")
        print("-" * 50)


def print_ingestion_summary(
    total_keywords: int,
    jobs_fetched: int,
    new_jobs_count: int,
    existing_jobs_count: int,
    failed_requests_count: int,
):
    """Prints job ingestion fetch summary table."""
    print("\nFetch summary")
    print("-" * 30)
    print(f"Search keywords: {total_keywords}")
    print(f"Jobs fetched: {jobs_fetched}")
    print(f"New jobs: {new_jobs_count}")
    print(f"Existing jobs: {existing_jobs_count}")
    print(f"Failed requests: {failed_requests_count}")
    print("-" * 30 + "\n")


def print_match_results(matches: List[MatchResult], limit: int = 10):
    """Prints formatted job match cards to console."""
    print("\n" + "=" * 50)
    print("JOB MATCH RESULTS")
    print("=" * 50)

    if not matches:
        print("No jobs found for match evaluation.\n")
        return

    display_matches = matches[:limit]
    for idx, match in enumerate(display_matches, start=1):
        matched_str = ", ".join(match.matched_skills) if match.matched_skills else "None"
        missing_str = ", ".join(match.missing_skills) if match.missing_skills else "None"
        skill_pct = int(match.skill_score * 100)

        print(f"\n{idx}. {match.title}")
        print(f"   Company: {match.company or 'Not specified'}")
        print(f"   Location: {match.location or 'Not specified'}")
        print()
        print(f"   Match Score: {match.final_score:.1f}/100")
        print(f"   Semantic Similarity: {match.similarity_score:.2f}")
        print(f"   Skill Match: {skill_pct}%")
        print()
        print(f"   Matched Skills:\n   {matched_str}")
        print()
        print(f"   Missing Skills:\n   {missing_str}")
        print()
        print(f"   Experience: {match.experience_status}")
        print(f"   Location: {match.location_status}")
        print()
        print(f"   Status: {match.match_status}")
        if match.reasons:
            print(f"   Reasons: {'; '.join(match.reasons)}")
        print("-" * 50)

    matches_count = sum(1 for m in matches if m.match_status == "MATCH")
    partial_count = sum(1 for m in matches if m.match_status == "PARTIAL_MATCH")
    filtered_count = sum(1 for m in matches if m.match_status == "FILTERED")

    print("\nMatching summary")
    print("-" * 30)
    print(f"Total jobs analyzed: {len(matches)}")
    print(f"Matches: {matches_count}")
    print(f"Partial matches: {partial_count}")
    print(f"Filtered: {filtered_count}")
    print("-" * 30 + "\n")


def print_digest_summary(
    jobs_analyzed: int,
    eligible_matches: int,
    already_notified: int,
    new_notifications: int,
    messages_sent: int,
    failed_messages: int,
):
    """Prints Telegram Digest summary block as required by Phase 3 spec."""
    print("\n" + "=" * 50)
    print("TELEGRAM DIGEST")
    print("=" * 50)
    print(f"\nJobs analyzed: {jobs_analyzed}")
    print(f"Eligible matches: {eligible_matches}")
    print(f"Already notified: {already_notified}")
    print(f"New notifications: {new_notifications}")
    print(f"Messages sent: {messages_sent}")
    print(f"Failed messages: {failed_messages}")
    print("\n" + "=" * 50 + "\n")


def run_telegram_digest_step(
    config: Config,
    conn,
    matches: List[MatchResult],
    jobs_map: Dict[int, Job],
    notifier: Optional[TelegramNotifier] = None,
):
    """
    Executes Phase 3 Telegram digest formatting, sending, and notification recording.
    """
    logger = logging.getLogger("app.main")
    logger.info("Executing Phase 3 Telegram Daily Job Digest...")

    if notifier is None:
        notifier = TelegramNotifier(config=config)

    digest_service = DigestService(config=config)
    jobs_analyzed = len(matches)

    eligible = [
        m
        for m in matches
        if m.final_score >= config.telegram_min_match_score
        and m.match_status != "FILTERED"
    ]
    eligible_matches_count = len(eligible)

    notified_set = get_notified_job_ids(conn, notification_type="telegram_digest")
    already_notified_count = sum(1 for m in eligible if m.job_id in notified_set)
    unnotified_matches = [m for m in eligible if m.job_id not in notified_set]
    new_notifications_count = len(unnotified_matches)

    chunks = digest_service.build_digest_chunks(
        matches=unnotified_matches, jobs_map=jobs_map
    )

    messages_sent = 0
    failed_messages = 0

    for chunk in chunks:
        success = notifier.send_message(chunk.text)
        if success:
            messages_sent += 1
            record_notifications(
                conn, chunk.job_ids, notification_type="telegram_digest"
            )
        else:
            failed_messages += 1

    print_digest_summary(
        jobs_analyzed=jobs_analyzed,
        eligible_matches=eligible_matches_count,
        already_notified=already_notified_count,
        new_notifications=new_notifications_count,
        messages_sent=messages_sent,
        failed_messages=failed_messages,
    )


def run_pipeline(
    config: Optional[Config] = None,
    run_ingestion: bool = True,
    run_matching: bool = True,
    run_digest: bool = False,
    notifier: Optional[TelegramNotifier] = None,
):
    """
    Executes the pipeline (Ingestion, Resume Matching, and Telegram Digest).
    """
    setup_logging()
    logger = logging.getLogger("app.main")
    logger.info("Starting AI Job-Matching & Monitoring Agent pipeline...")

    if config is None:
        try:
            config = load_config()
        except ValueError as e:
            logger.error("Configuration error: %s", str(e))
            sys.exit(1)

    logger.info("Initializing SQLite database at: %s", config.db_path)
    conn = initialize_database(config.db_path)

    # ----------------------------------------------------
    # Phase 1: Ingestion
    # ----------------------------------------------------
    if run_ingestion:
        adzuna_source = AdzunaJobSource(
            app_id=config.adzuna_app_id,
            app_key=config.adzuna_app_key,
            country=config.adzuna_country,
        )

        total_keywords = len(config.keywords)
        jobs_fetched_count = 0
        new_jobs_list: List[Job] = []
        existing_jobs_count = 0
        failed_requests_count = 0

        for idx, keyword in enumerate(config.keywords, start=1):
            logger.info(
                "[%d/%d] Processing search keyword: '%s'", idx, total_keywords, keyword
            )
            try:
                jobs, success = adzuna_source.fetch_jobs_for_keyword(
                    keyword=keyword,
                    max_pages=config.adzuna_max_pages,
                    results_per_page=config.adzuna_results_per_page,
                )

                if not success:
                    failed_requests_count += 1

                jobs_fetched_count += len(jobs)

                for job in jobs:
                    is_new = insert_job(conn, job)
                    if is_new:
                        new_jobs_list.append(job)
                    else:
                        existing_jobs_count += 1

            except Exception as e:
                logger.error("Error processing keyword '%s': %s", keyword, str(e))
                failed_requests_count += 1

        if config.internshala_enabled:
            logger.info("Processing Internshala ingestion...")
            try:
                ish_source = InternshalaJobSource(
                    request_delay_min=config.internshala_request_delay_min,
                    request_delay_max=config.internshala_request_delay_max,
                )
                source_res = ish_source.fetch_source_jobs(
                    keywords=config.internshala_keywords,
                    max_pages=config.internshala_max_pages,
                )
                jobs_fetched_count += source_res.total_fetched
                for job in source_res.jobs:
                    is_new = insert_job(conn, job)
                    if is_new:
                        new_jobs_list.append(job)
                    else:
                        existing_jobs_count += 1
            except Exception as e:
                logger.error("Error processing Internshala ingestion: %s", str(e))
                failed_requests_count += 1

        print_new_jobs(new_jobs_list)
        print_ingestion_summary(
            total_keywords=total_keywords,
            jobs_fetched=jobs_fetched_count,
            new_jobs_count=len(new_jobs_list),
            existing_jobs_count=existing_jobs_count,
            failed_requests_count=failed_requests_count,
        )


    # ----------------------------------------------------
    # Phase 2: Resume Matching Engine
    # ----------------------------------------------------
    match_results: List[MatchResult] = []
    all_stored_jobs = get_all_jobs(conn)

    if run_matching:
        logger.info("Executing Phase 2 Resume Matching Engine...")
        if not all_stored_jobs:
            logger.warning("No jobs stored in database to match against.")
        else:
            try:
                matching_service = MatchingService(config=config)
                resume = matching_service.prepare_resume()
                match_results = matching_service.match_all_jobs(
                    resume=resume, jobs=all_stored_jobs
                )
                save_match_results(conn, match_results)
                print_match_results(match_results)

            except FileNotFoundError as e:
                logger.warning("Skipping matching: %s", str(e))
            except Exception as e:
                logger.error("Error during match evaluation: %s", str(e), exc_info=True)
    else:
        match_results = get_stored_matches(conn)

    # ----------------------------------------------------
    # Phase 3: Telegram Digest
    # ----------------------------------------------------
    if run_digest:
        jobs_map = get_jobs_map(conn)
        run_telegram_digest_step(
            config=config,
            conn=conn,
            matches=match_results,
            jobs_map=jobs_map,
            notifier=notifier,
        )

    conn.close()
    logger.info("Pipeline execution completed successfully.")


def run_gmail_test(config: Config):
    """
    Executes a safe manual test of Gmail API job-alert ingestion.
    Does NOT modify emails, delete emails, or send Telegram notifications.
    """
    logger = logging.getLogger("app.main")
    logger.info("Executing safe manual test of Gmail job alert email sources...")

    auth_status = "SUCCESS"
    try:
        gmail_client = GmailAPIClient(
            credentials_path=config.gmail_credentials_path,
            token_path=config.gmail_token_path,
        )
        gmail_client.authenticate()
    except Exception as e:
        auth_status = f"FAILED ({str(e)})"
        logger.error("Gmail authentication failed: %s", str(e))

    li_jobs_count = 0
    ind_jobs_count = 0
    total_parsed = 0
    duplicates_removed = 0

    if auth_status == "SUCCESS":
        # 1. LinkedIn Alerts
        li_source = LinkedInAlertEmailSource(
            gmail_client=gmail_client,
            query=config.gmail_linkedin_query,
            query_limit=config.gmail_query_limit,
        )
        li_res = li_source.fetch_source_jobs()
        li_jobs_count = len(li_res.jobs)

        # 2. Indeed Alerts
        ind_source = IndeedAlertEmailSource(
            gmail_client=gmail_client,
            query=config.gmail_indeed_query,
            query_limit=config.gmail_query_limit,
        )
        ind_res = ind_source.fetch_source_jobs()
        ind_jobs_count = len(ind_res.jobs)

        all_jobs = li_res.jobs + ind_res.jobs
        total_parsed = len(all_jobs)
        unique_fingerprints = {j.fingerprint for j in all_jobs if j.fingerprint}
        duplicates_removed = total_parsed - len(unique_fingerprints) if total_parsed else 0

    print("\nGMAIL INGESTION SUMMARY")
    print("=======================")
    print(f"LinkedIn jobs parsed: {li_jobs_count}")
    print(f"Indeed jobs parsed: {ind_jobs_count}")
    print(f"Total jobs parsed: {total_parsed}")
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Authentication: {auth_status}")
    print("\nNo emails modified.")
    print("=======================\n")


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses command-line flags."""
    parser = argparse.ArgumentParser(
        description="AI Job-Matching & Monitoring Agent"
    )
    parser.add_argument(
        "--scheduler",
        action="store_true",
        help="Run Phase 4 long-running scheduled monitoring daemon",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run one complete monitoring pipeline cycle and exit",
    )
    parser.add_argument(
        "--digest",
        action="store_true",
        help="Run Phase 3 Telegram daily job digest",
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip Phase 1 job fetching from Adzuna",
    )
    parser.add_argument(
        "--skip-matching",
        action="store_true",
        help="Skip Phase 2 job matching computation",
    )
    parser.add_argument(
        "--gmail-test",
        action="store_true",
        help="Run safe manual test for Gmail API job-alert ingestion",
    )
    parser.add_argument(
        "--tailor-resume",
        type=int,
        metavar="JOB_ID",
        help="Trigger LLM resume tailoring for a specific job ID",
    )
    parser.add_argument(
        "--review-resume",
        type=int,
        metavar="DRAFT_ID",
        help="Interactively review and approve/reject a tailored resume draft",
    )
    parser.add_argument(
        "--export-resume",
        type=int,
        metavar="DRAFT_ID",
        help="Export an APPROVED tailored resume draft as Markdown",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Run Phase 11 FastAPI Web UI backend server",
    )
    return parser.parse_args(args)



def handle_tailor_resume(config: Config, job_id: int):
    """
    Triggers LLM resume tailoring for a specific job_id.
    """
    logger = logging.getLogger("app.main")
    logger.info("Executing LLM resume tailoring for job ID: %d", job_id)
    conn = initialize_database(config.db_path)

    # Fetch job and match result
    all_jobs = get_jobs_map(conn)
    job = all_jobs.get(job_id)
    if not job:
        print(f"Error: Job ID {job_id} not found in database.")
        conn.close()
        return

    matches = get_stored_matches(conn)
    match = next((m for m in matches if m.job_id == job_id), None)
    if not match:
        print(f"Warning: No Phase 2 match calculation found for Job ID {job_id}. Running match evaluation...")
        matching_service = MatchingService(config=config)
        resume = matching_service.prepare_resume()
        match = matching_service.evaluate_match(resume=resume, job=job)
        save_match_results(conn, [match])

    service = ResumeTailoringService(config=config)
    result = service.tailor_resume_for_job(conn, job, match)
    conn.close()

    print("\nTAILORING RESULT SUMMARY")
    print("========================")
    print(f"Draft ID: {result.get('id')}")
    print(f"Job: {job.title} at {job.company}")
    print(f"Match Score: {match.final_score:.1f}%")
    print(f"Status: {result.get('status')}")
    if result.get("error"):
        print(f"Error: {result.get('error')}")
    print("========================\n")


def handle_review_resume(config: Config, draft_id: int, input_func=input, conn: Optional[sqlite3.Connection] = None):
    """
    CLI interface for human review and approval/rejection of a tailored resume draft.
    """
    close_conn = False
    if conn is None:
        conn = initialize_database(config.db_path)
        close_conn = True

    try:
        draft = get_tailored_resume_by_id(conn, draft_id)

        if not draft:
            print(f"Error: Tailored resume draft #{draft_id} not found.")
            return

        job_title = draft.get("job_title", "Unknown Position")
        job_company = draft.get("job_company", "Not specified")
        match_score = draft.get("match_score", 0.0)
        status = draft.get("status", "UNKNOWN")
        content = draft.get("resume_content") or {}
        changes = draft.get("changes") or []
        warnings = draft.get("warnings") or []
        val_res = draft.get("validation_result") or {}

        print("\n" + "=" * 50)
        print("TAILORED RESUME REVIEW")
        print("=" * 50)
        print(f"\nJob: {job_title}")
        print(f"Company: {job_company}")
        print(f"Match Score: {match_score:.1f}%\n")

        print("SUMMARY")
        print("-" * 30)
        print(content.get("summary", "No summary provided."))
        print()

        print("SKILLS")
        print("-" * 30)
        skills = content.get("skills") or []
        if skills:
            print(", ".join(skills))
        else:
            print("None")
        print()

        print("EXPERIENCE")
        print("-" * 30)
        exp_list = content.get("experience") or []
        if exp_list:
            for exp in exp_list:
                if isinstance(exp, dict):
                    print(f"• {exp.get('title', '')} at {exp.get('company', '')}")
                    for b in exp.get("bullets", []):
                        print(f"  - {b}")
                else:
                    print(f"• {exp}")
        else:
            print("None")
        print()

        print("PROJECTS")
        print("-" * 30)
        proj_list = content.get("projects") or []
        if proj_list:
            for proj in proj_list:
                if isinstance(proj, dict):
                    print(f"• {proj.get('name', '')}")
                    for b in proj.get("bullets", []):
                        print(f"  - {b}")
                else:
                    print(f"• {proj}")
        else:
            print("None")
        print()

        print("WARNINGS")
        print("-" * 30)
        if warnings:
            for w in warnings:
                print(f"- {w}")
        else:
            print("None")
        print()

        print("CHANGES")
        print("-" * 30)
        if changes:
            for c in changes:
                print(f"- {c}")
        else:
            print("None")
        print()

        print("VALIDATION")
        print("-" * 30)
        print(f"Status: {status}")
        print(f"Valid: {val_res.get('valid', True)}")
        violations = val_res.get("violations") or []
        if violations:
            print("Violations:")
            for v in violations:
                print(f"  ❌ {v}")
        print()

        print("Options:")
        print(" [A] Approve")
        print(" [R] Reject")
        print(" [V] View validation details")
        print(" [C] Cancel")

        choice = input_func("\nSelect option [A/R/V/C]: ").strip().upper()

        if choice == "A":
            if status == "INVALID" or not val_res.get("valid", True):
                print("\nError: Cannot approve an INVALID draft containing truth violations.")
            else:
                update_tailored_resume_status(conn, draft_id, "APPROVED")
                print(f"\nDraft #{draft_id} APPROVED successfully.")
        elif choice == "R":
            update_tailored_resume_status(conn, draft_id, "REJECTED")
            print(f"\nDraft #{draft_id} REJECTED.")
        elif choice == "V":
            print("\n--- DETAILED VALIDATION REPORT ---")
            print(f"Valid: {val_res.get('valid', True)}")
            print("Violations:")
            for v in violations:
                print(f"  - {v}")
            print("Warnings:")
            for w in val_res.get("warnings", []):
                print(f"  - {w}")
            print("-----------------------------------")
        else:
            print("\nReview cancelled. Status remains unchanged.")

    finally:
        if close_conn:
            conn.close()


def handle_export_resume(config: Config, draft_id: int, output_path: Optional[str] = None, conn: Optional[sqlite3.Connection] = None):
    """
    Exports an APPROVED tailored resume draft as Markdown.
    Rejects exporting non-approved drafts.
    """
    close_conn = False
    if conn is None:
        conn = initialize_database(config.db_path)
        close_conn = True

    try:
        draft = get_tailored_resume_by_id(conn, draft_id)

        if not draft:
            print(f"Error: Draft ID #{draft_id} not found.")
            sys.exit(1)

        status = draft.get("status")
        if status != "APPROVED":
            print(f"Export rejected: Only APPROVED tailored resume drafts can be exported (current status: {status}).")
            return False

        content = draft.get("resume_content") or {}
        job_title = draft.get("job_title", "Position")

        lines = [
            f"# Tailored Resume - {job_title}",
            "",
            "## Professional Summary",
            content.get("summary", ""),
            "",
            "## Technical Skills",
        ]
        for skill in content.get("skills", []):
            lines.append(f"- {skill}")

        lines.extend(["", "## Experience"])
        for exp in content.get("experience", []):
            if isinstance(exp, dict):
                lines.append(f"### {exp.get('title', '')} | {exp.get('company', '')}")
                for b in exp.get("bullets", []):
                    lines.append(f"- {b}")
            else:
                lines.append(f"- {exp}")

        lines.extend(["", "## Projects"])
        for proj in content.get("projects", []):
            if isinstance(proj, dict):
                lines.append(f"### {proj.get('name', '')}")
                for b in proj.get("bullets", []):
                    lines.append(f"- {b}")
            else:
                lines.append(f"- {proj}")

        lines.extend(["", "## Education"])
        for edu in content.get("education", []):
            if isinstance(edu, dict):
                lines.append(f"- {edu.get('degree', '')} from {edu.get('institution', '')}")
            else:
                lines.append(f"- {edu}")

        lines.extend(["", "## Certifications"])
        for cert in content.get("certifications", []):
            lines.append(f"- {cert}")

        markdown_text = "\n".join(lines)

        if not output_path:
            os.makedirs("data/resume", exist_ok=True)
            output_path = f"data/resume/tailored_resume_{draft_id}.md"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        print(f"Successfully exported approved tailored resume draft #{draft_id} to: {output_path}")
        return True

    finally:
        if close_conn:
            conn.close()



def main():
    """CLI entry point."""
    setup_logging()
    parsed = parse_args()

    try:
        config = load_config()
    except ValueError as e:
        logging.error("Configuration error: %s", str(e))
        sys.exit(1)

    if parsed.server:
        import uvicorn
        logger = logging.getLogger("app.main")
        logger.info("Launching Phase 11 FastAPI Web UI backend server on http://localhost:8000 ...")
        uvicorn.run("app.api.app:app", host="0.0.0.0", port=8000, reload=False)

    elif parsed.gmail_test:
        run_gmail_test(config=config)

    elif parsed.tailor_resume:
        handle_tailor_resume(config=config, job_id=parsed.tailor_resume)

    elif parsed.review_resume:
        handle_review_resume(config=config, draft_id=parsed.review_resume)

    elif parsed.export_resume:
        handle_export_resume(config=config, draft_id=parsed.export_resume)

    elif parsed.scheduler:
        logger = logging.getLogger("app.main")
        logger.info("Launching Phase 4 Scheduled Monitoring Service daemon...")
        pipeline_scheduler = PipelineScheduler(config=config)
        pipeline_scheduler.start(block=True)

    elif parsed.run_once:
        pipeline_service = PipelineService(config=config)
        pipeline_service.run_monitoring_pipeline(config=config)

    elif parsed.digest or parsed.skip_ingestion or parsed.skip_matching:
        run_pipeline(
            config=config,
            run_ingestion=not parsed.skip_ingestion,
            run_matching=not parsed.skip_matching,
            run_digest=parsed.digest,
        )

    else:
        # Default behavior: run one complete monitoring pipeline cycle
        pipeline_service = PipelineService(config=config)
        pipeline_service.run_monitoring_pipeline(config=config)


if __name__ == "__main__":
    main()


