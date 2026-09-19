"""
Jooble API job source fetcher client.
"""

import logging
from typing import Any, Dict, List, Optional
import requests

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


class JoobleJobSource(BaseJobSource):
    """
    Client for fetching job postings via Jooble API.
    Endpoint: POST https://jooble.org/api/{api_key}
    """

    BASE_URL_TEMPLATE = "https://jooble.org/api/{api_key}"

    def __init__(self, api_key: str = "", timeout: int = 15):
        self.api_key = api_key.strip()
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "Jooble"

    @property
    def source_identifier(self) -> str:
        return "jooble"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_jooble_enabled") and not config.source_jooble_enabled:
                return False
            key = getattr(config, "jooble_api_key", "") or self.api_key
            return bool(key and str(key).strip())
        return bool(self.api_key)

    def fetch_jobs_raw(
        self, keyword: str = "AI Engineer", location: str = "", page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetches raw job postings from Jooble API using POST request.
        """
        if not self.api_key:
            logger.warning("Jooble API key missing; skipping request.")
            return []

        url = self.BASE_URL_TEMPLATE.format(api_key=self.api_key)
        payload = {
            "keywords": keyword,
            "location": location,
            "page": page,
        }

        try:
            logger.info("Requesting Jooble API (keyword='%s', page=%d)", keyword, page)
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                logger.error("Unexpected response format from Jooble API: expected dict")
                return []

            results = data.get("jobs")
            if not isinstance(results, list):
                logger.error("Malformed 'jobs' field from Jooble API")
                return []

            return results

        except requests.exceptions.Timeout:
            logger.error("Timeout fetching from Jooble API")
            return []
        except requests.exceptions.RequestException as e:
            logger.error("HTTP/Network error fetching from Jooble API: %s", str(e))
            return []
        except ValueError as e:
            logger.error("Invalid JSON response from Jooble API: %s", str(e))
            return []
        except Exception as e:
            logger.error("Unexpected error fetching from Jooble API: %s", str(e))
            return []

    def fetch_source_jobs(self, keywords: Optional[List[str]] = None, **kwargs: Any) -> SourceResult:
        """
        Executes fetch across keywords and returns structured SourceResult.
        """
        from app.services.normalization import normalize_jooble_job

        if not self.api_key:
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.DISABLED,
                jobs=[],
                total_fetched=0,
                error_message="Jooble API key not configured.",
            )

        search_keywords = keywords or ["AI Engineer"]
        all_jobs: List[Job] = []

        for kw in search_keywords:
            raw_jobs = self.fetch_jobs_raw(keyword=kw, page=1)
            for rj in raw_jobs:
                all_jobs.append(normalize_jooble_job(rj))

        return SourceResult(
            source_name=self.name,
            status=SourceStatus.SUCCESS,
            jobs=all_jobs,
            total_fetched=len(all_jobs),
        )
