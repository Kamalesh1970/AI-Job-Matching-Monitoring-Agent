"""
SerpApi Google Jobs source fetcher client.
Endpoint: GET https://serpapi.com/search?engine=google_jobs
"""

import logging
import time
from typing import Any, Dict, List, Optional
import requests

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


class SerpApiJobSource(BaseJobSource):
    """
    Client for fetching Google Jobs postings via SerpApi REST endpoint.
    Uses engine=google_jobs parameter with JSON response format.
    """

    BASE_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str = "", timeout: int = 15):
        self.api_key = api_key.strip()
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "SerpApi"

    @property
    def source_identifier(self) -> str:
        return "serpapi"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_serpapi_enabled") and not config.source_serpapi_enabled:
                return False
            key = getattr(config, "serpapi_key", "") or self.api_key
            return bool(key and str(key).strip())
        return bool(self.api_key)

    def _sanitize_error(self, err_msg: str) -> str:
        """Redacts sensitive API key from error messages."""
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
        Fetches raw job results from SerpApi Google Jobs engine.
        """
        if not self.api_key:
            logger.warning("SerpApi API key missing; skipping request.")
            return []

        params = {
            "engine": "google_jobs",
            "q": keyword,
            "location": location or "India",
            "api_key": self.api_key,
            "output": "json",
        }

        try:
            logger.info("Requesting SerpApi Google Jobs (q='%s', location='%s')", keyword, location)
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                logger.error("Unexpected response format from SerpApi: expected dict")
                return []

            if "error" in data:
                sanitized = self._sanitize_error(str(data["error"]))
                logger.error("SerpApi response error: %s", sanitized)
                return []

            results = data.get("jobs_results")
            if not isinstance(results, list):
                logger.error("Malformed 'jobs_results' field from SerpApi")
                return []

            return results

        except requests.exceptions.Timeout:
            logger.error("Timeout fetching from SerpApi")
            return []
        except requests.exceptions.HTTPError as e:
            sanitized = self._sanitize_error(str(e))
            logger.error("HTTP error fetching from SerpApi: %s", sanitized)
            return []
        except requests.exceptions.RequestException as e:
            sanitized = self._sanitize_error(str(e))
            logger.error("Network error fetching from SerpApi: %s", sanitized)
            return []
        except ValueError as e:
            logger.error("Invalid JSON response from SerpApi: %s", str(e))
            return []
        except Exception as e:
            sanitized = self._sanitize_error(str(e))
            logger.error("Unexpected error fetching from SerpApi: %s", sanitized)
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
        from app.services.normalization import normalize_serpapi_job

        start_time = time.time()

        effective_key = self.api_key
        if config is not None:
            effective_key = getattr(config, "serpapi_key", "") or self.api_key

        if not effective_key:
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.DISABLED,
                jobs=[],
                total_fetched=0,
                error_message="SerpApi API key not configured.",
                duration_seconds=time.time() - start_time,
            )

        self.api_key = effective_key

        search_keywords = keywords or ["AI Engineer"]
        target_location = location or "India"
        all_jobs: List[Job] = []
        errors: List[str] = []

        for kw in search_keywords:
            try:
                raw_jobs = self.fetch_jobs_raw(keyword=kw, location=target_location, page=1)
                for rj in raw_jobs:
                    all_jobs.append(normalize_serpapi_job(rj))
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
