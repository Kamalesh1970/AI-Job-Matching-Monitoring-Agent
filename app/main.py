"""
Main entry point for Phase 1 (Ingestion) & Phase 2 (Resume Matching Engine).
"""

import sys
import logging
from typing import List, Optional

from app.config import load_config, Config
from app.db.database import (
    get_all_jobs,
    initialize_database,
    insert_job,
    save_match_results,
)
from app.db.models import Job, MatchResult
from app.services.matching_service import MatchingService
from app.sources.adzuna import AdzunaJobSource


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


def run_pipeline(config: Optional[Config] = None, run_matching: bool = True):
    """Executes the Phase 1 Ingestion and Phase 2 Resume Matching pipelines."""
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
    if run_matching:
        logger.info("Executing Phase 2 Resume Matching Engine...")
        all_stored_jobs = get_all_jobs(conn)

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

    conn.close()
    logger.info("Pipeline execution completed successfully.")


if __name__ == "__main__":
    run_pipeline()
