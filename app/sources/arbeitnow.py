"""
Arbeitnow API job source fetcher client.
"""

import logging
from typing import Any, Dict, List, Optional
import requests

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


class ArbeitnowJobSource(BaseJobSource):
    """
    Client for fetching job postings via Arbeitnow public job board API.
    Endpoint: https://www.arbeitnow.com/api/job-board-api
    """

    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "Arbeitnow"

    @property
    def source_identifier(self) -> str:
        return "arbeitnow"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None and hasattr(config, "source_arbeitnow_enabled"):
            return bool(config.source_arbeitnow_enabled)
        return True

    def fetch_jobs_raw(
        self, keyword: str = "", page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetches a page of raw job postings from Arbeitnow API.
        """
        params = {}
        if page > 1:
            params["page"] = page

        try:
            logger.info("Requesting Arbeitnow API (page=%d)", page)
            response = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                logger.error("Unexpected response format from Arbeitnow API: expected dict")
                return []

            results = data.get("data")
            if not isinstance(results, list):
                logger.error("Malformed 'data' field from Arbeitnow API")
                return []

            return results

        except requests.exceptions.Timeout:
            logger.error("Timeout fetching from Arbeitnow API")
            return []
        except requests.exceptions.RequestException as e:
            logger.error("HTTP/Network error fetching from Arbeitnow API: %s", str(e))
            return []
        except ValueError as e:
            logger.error("Invalid JSON response from Arbeitnow API: %s", str(e))
            return []
        except Exception as e:
            logger.error("Unexpected error fetching from Arbeitnow API: %s", str(e))
            return []

    def fetch_source_jobs(self, **kwargs: Any) -> SourceResult:
        """
        Executes fetch and returns structured SourceResult.
        """
        from app.services.normalization import normalize_arbeitnow_job

        raw_jobs = self.fetch_jobs_raw(page=1)
        normalized_jobs = [normalize_arbeitnow_job(rj) for rj in raw_jobs]

        return SourceResult(
            source_name=self.name,
            status=SourceStatus.SUCCESS,
            jobs=normalized_jobs,
            total_fetched=len(normalized_jobs),
        )
