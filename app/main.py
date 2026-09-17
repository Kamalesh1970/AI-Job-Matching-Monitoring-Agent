"""
Main entry point for Phase 1 of the AI Job-Matching & Monitoring Agent pipeline.
"""

import sys
import logging
from typing import List, Optional

from app.config import load_config, Config
from app.db.database import initialize_database, insert_job
from app.db.models import Job
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


def print_summary(
    total_keywords: int,
    jobs_fetched: int,
    new_jobs_count: int,
    existing_jobs_count: int,
    failed_requests_count: int,
):
    """Prints execution summary table."""
    print("\nFetch summary")
    print("-" * 30)
    print(f"Search keywords: {total_keywords}")
    print(f"Jobs fetched: {jobs_fetched}")
    print(f"New jobs: {new_jobs_count}")
    print(f"Existing jobs: {existing_jobs_count}")
    print(f"Failed requests: {failed_requests_count}")
    print("-" * 30 + "\n")


def run_pipeline(config: Optional[Config] = None):
    """Executes the Phase 1 job ingestion pipeline."""
    setup_logging()
    logger = logging.getLogger("app.main")
    logger.info("Starting Phase 1 AI Job-Matching & Monitoring Agent pipeline...")

    if config is None:
        try:
            config = load_config()
        except ValueError as e:
            logger.error("Configuration error: %s", str(e))
            sys.exit(1)

    logger.info("Initializing SQLite database at: %s", config.db_path)
    conn = initialize_database(config.db_path)

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

    conn.close()

    print_new_jobs(new_jobs_list)
    print_summary(
        total_keywords=total_keywords,
        jobs_fetched=jobs_fetched_count,
        new_jobs_count=len(new_jobs_list),
        existing_jobs_count=existing_jobs_count,
        failed_requests_count=failed_requests_count,
    )

    logger.info("Pipeline execution completed successfully.")


if __name__ == "__main__":
    run_pipeline()
