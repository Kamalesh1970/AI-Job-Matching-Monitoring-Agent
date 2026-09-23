"""
Indeed Jobs API (RapidAPI) job source fetcher client.
Endpoint: GET https://<rapidapi_host>/search
Headers: X-RapidAPI-Key, X-RapidAPI-Host
"""

import logging
import time
from typing import Any, Dict, List, Optional
import requests

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


class IndeedJobsApiSource(BaseJobSource):
    """
    Client for fetching job postings via Indeed Jobs API on RapidAPI.
    Requires X-RapidAPI-Key and X-RapidAPI-Host headers.
    """

    DEFAULT_HOST = "indeed-jobs-api.p.rapidapi.com"

    def __init__(
        self,
        api_key: str = "",
        rapidapi_host: str = DEFAULT_HOST,
        timeout: int = 15,
    ):
        self.api_key = api_key.strip()
        self.rapidapi_host = rapidapi_host.strip() or self.DEFAULT_HOST
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "Indeed Jobs API"

    @property
    def source_identifier(self) -> str:
        return "indeed_jobs_api"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_indeed_jobs_api_enabled") and not config.source_indeed_jobs_api_enabled:
                return False
            key = getattr(config, "indeed_jobs_api_key", "") or self.api_key
            return bool(key and str(key).strip())
        return bool(self.api_key)

    def _sanitize_error(self, err_msg: str) -> str:
        if not self.api_key:
            return err_msg
        return err_msg.replace(self.api_key, "[REDACTED]")

    def fetch_jobs_raw(
        self,
        keyword: str = "AI Engineer",
        location: str = "India",
        page: int = 1,
        results_per_page: int = 20,
    ) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("Indeed Jobs RapidAPI key missing; skipping request.")
            return []

        search_query = f"{keyword} in {location}".strip() if location else keyword
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.rapidapi_host,
        }
        params = {
            "query": search_query,
            "page": str(page),
        }

        host = self.rapidapi_host.strip()
        url = f"https://{host}/search" if not host.startswith("http") else host

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict):
                results = data.get("data") or data.get("jobs") or data.get("results") or []
                if isinstance(results, list):
                    return results
            elif isinstance(data, list):
                return data
            return []
        except Exception as e:
            sanitized = self._sanitize_error(str(e))
            logger.error("Error fetching from Indeed Jobs RapidAPI: %s", sanitized)
            return []

    def fetch_source_jobs(
        self,
        keywords: Optional[List[str]] = None,
        location: Optional[str] = None,
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> SourceResult:
        from app.services.normalization import normalize_active_jobs_db_job

        start_time = time.time()
        effective_key = self.api_key
        effective_host = self.rapidapi_host

        if config is not None:
            effective_key = getattr(config, "indeed_jobs_api_key", "") or self.api_key
            effective_host = getattr(config, "indeed_jobs_rapidapi_host", "") or self.rapidapi_host

        if not effective_key:
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.DISABLED,
                jobs=[],
                total_fetched=0,
                error_message="Indeed Jobs RapidAPI key not configured.",
                duration_seconds=time.time() - start_time,
            )

        self.api_key = effective_key
        self.rapidapi_host = effective_host or self.DEFAULT_HOST

        search_keywords = keywords or ["AI Engineer"]
        target_location = location or "India"
        all_jobs: List[Job] = []
        errors: List[str] = []

        for kw in search_keywords:
            try:
                raw_jobs = self.fetch_jobs_raw(keyword=kw, location=target_location, page=1)
                for rj in raw_jobs:
                    job = normalize_active_jobs_db_job(rj)
                    job.source = "Indeed"
                    all_jobs.append(job)
            except Exception as e:
                sanitized = self._sanitize_error(str(e))
                errors.append(f"Keyword '{kw}': {sanitized}")

        duration = time.time() - start_time
        status = SourceStatus.SUCCESS
        if errors and not all_jobs:
            status = SourceStatus.FAILED
        elif errors:
            status = SourceStatus.PARTIAL_FAILURE

        err_msg = "; ".join(errors) if errors else None

        return SourceResult(
            source_name=self.name,
            status=status,
            jobs=all_jobs,
            total_fetched=len(all_jobs),
            error_message=err_msg,
            duration_seconds=duration,
        )
