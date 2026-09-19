"""
Himalayas API job source fetcher client.
"""

import logging
from typing import Any, Dict, List, Optional
import requests

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


class HimalayasJobSource(BaseJobSource):
    """
    Client for fetching remote job postings via Himalayas public jobs API.
    Endpoint: https://himalayas.app/jobs/api
    """

    BASE_URL = "https://himalayas.app/jobs/api"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "Himalayas"

    @property
    def source_identifier(self) -> str:
        return "himalayas"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None and hasattr(config, "source_himalayas_enabled"):
            return bool(config.source_himalayas_enabled)
        return True

    def fetch_jobs_raw(
        self, keyword: str = "", page: int = 1, results_per_page: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetches raw job postings from Himalayas API.
        """
        offset = (page - 1) * results_per_page
        params = {"limit": results_per_page, "offset": offset}

        try:
            logger.info("Requesting Himalayas API (limit=%d, offset=%d)", results_per_page, offset)
            response = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                logger.error("Unexpected response format from Himalayas API: expected dict")
                return []

            results = data.get("jobs")
            if not isinstance(results, list):
                logger.error("Malformed 'jobs' field from Himalayas API")
                return []

            return results

        except requests.exceptions.Timeout:
            logger.error("Timeout fetching from Himalayas API")
            return []
        except requests.exceptions.RequestException as e:
            logger.error("HTTP/Network error fetching from Himalayas API: %s", str(e))
            return []
        except ValueError as e:
            logger.error("Invalid JSON response from Himalayas API: %s", str(e))
            return []
        except Exception as e:
            logger.error("Unexpected error fetching from Himalayas API: %s", str(e))
            return []

    def fetch_source_jobs(self, **kwargs: Any) -> SourceResult:
        """
        Executes fetch and returns structured SourceResult.
        """
        from app.services.normalization import normalize_himalayas_job

        raw_jobs = self.fetch_jobs_raw(page=1)
        normalized_jobs = [normalize_himalayas_job(rj) for rj in raw_jobs]

        return SourceResult(
            source_name=self.name,
            status=SourceStatus.SUCCESS,
            jobs=normalized_jobs,
            total_fetched=len(normalized_jobs),
        )
