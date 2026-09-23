"""
Active Jobs DB job source fetcher client (RapidAPI).
Endpoint: GET https://active-jobs-db.p.rapidapi.com/active-ats-promoted-jobs
"""

import logging
import time
from typing import Any, Dict, List, Optional
import requests

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


class ActiveJobsDBJobSource(BaseJobSource):
    """
    Client for fetching job postings via Active Jobs DB on RapidAPI.
    Requires X-RapidAPI-Key and X-RapidAPI-Host headers.
    """

    DEFAULT_HOST = "active-jobs-db.p.rapidapi.com"

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
        return "Active Jobs DB"

    @property
    def source_identifier(self) -> str:
        return "active_jobs_db"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_active_jobs_db_enabled") and not config.source_active_jobs_db_enabled:
                return False
            key = getattr(config, "active_jobs_db_api_key", "") or self.api_key
            return bool(key and str(key).strip())
        return bool(self.api_key)

    def _sanitize_error(self, err_msg: str) -> str:
        """Redacts sensitive API keys from error messages."""
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
        """
        Fetches raw job dictionaries from Active Jobs DB RapidAPI endpoint.
        """
        if not self.api_key:
            logger.warning("Active Jobs DB API key missing; skipping request.")
            return []

        host = self.rapidapi_host.strip()
        url = f"https://{host}/active-ats-promoted-jobs" if not host.startswith("http") else host

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": host,
        }
        params = {
            "title_filter": keyword,
            "location_filter": location or "India",
            "limit": str(results_per_page),
            "offset": str((page - 1) * results_per_page),
        }

        logger.info("Requesting Active Jobs DB URL: %s (keyword='%s', location='%s')", url, keyword, location)

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )

            # Fallback to alternate endpoint structure if primary endpoint 404s
            if response.status_code == 404:
                alt_url = f"https://{host}/active-ats-jobs"
                logger.info("Retrying Active Jobs DB with alternate endpoint: %s", alt_url)
                response = requests.get(
                    alt_url,
                    headers=headers,
                    params={"q": keyword, "location": location, "limit": str(results_per_page)},
                    timeout=self.timeout,
                )

            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                return data

            if isinstance(data, dict):
                for field in ["hits", "jobs", "data", "results"]:
                    res_list = data.get(field)
                    if isinstance(res_list, list):
                        return res_list
                logger.error("Unexpected dict structure from Active Jobs DB API")
                return []

            logger.error("Unexpected response format from Active Jobs DB API")
            return []

        except requests.exceptions.Timeout:
            logger.error("Timeout fetching from Active Jobs DB API")
            return []
        except requests.exceptions.HTTPError as e:
            sanitized = self._sanitize_error(str(e))
            logger.error("HTTP error fetching from Active Jobs DB API: %s", sanitized)
            return []
        except requests.exceptions.RequestException as e:
            sanitized = self._sanitize_error(str(e))
            logger.error("Network error fetching from Active Jobs DB API: %s", sanitized)
            return []
        except ValueError as e:
            logger.error("Invalid JSON response from Active Jobs DB API: %s", str(e))
            return []
        except Exception as e:
            sanitized = self._sanitize_error(str(e))
            logger.error("Unexpected error fetching from Active Jobs DB API: %s", sanitized)
            return []

    def fetch_source_jobs(
        self,
        keywords: Optional[List[str]] = None,
        location: Optional[str] = None,
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> SourceResult:
        """
        Executes fetch across keywords and returns structured SourceResult.
        """
        from app.services.normalization import normalize_active_jobs_db_job

        start_time = time.time()

        effective_key = self.api_key
        effective_host = self.rapidapi_host

        if config is not None:
            effective_key = getattr(config, "active_jobs_db_api_key", "") or self.api_key
            effective_host = getattr(config, "active_jobs_db_rapidapi_host", "") or self.rapidapi_host

        if not effective_key:
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.DISABLED,
                jobs=[],
                total_fetched=0,
                error_message="Active Jobs DB API key not configured.",
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
                    all_jobs.append(normalize_active_jobs_db_job(rj))
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
