"""
RemoteOK API job source fetcher client.
"""

import logging
from typing import Any, Dict, List, Optional
import requests

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


class RemoteOKJobSource(BaseJobSource):
    """
    Client for fetching remote job postings via RemoteOK public API.
    Endpoint: https://remoteok.com/api
    """

    BASE_URL = "https://remoteok.com/api"
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AIJobAgent/1.0"

    def __init__(self, timeout: int = 15, user_agent: Optional[str] = None):
        self.timeout = timeout
        self.headers = {
            "User-Agent": user_agent or self.DEFAULT_USER_AGENT,
            "Accept": "application/json",
        }

    @property
    def name(self) -> str:
        return "RemoteOK"

    @property
    def source_identifier(self) -> str:
        return "remoteok"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None and hasattr(config, "source_remoteok_enabled"):
            return bool(config.source_remoteok_enabled)
        return True

    def fetch_jobs_raw(
        self, keyword: str = "", page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetches raw job postings from RemoteOK API.
        Filters out legal disclaimer element.
        """
        try:
            logger.info("Requesting RemoteOK API")
            response = requests.get(self.BASE_URL, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                logger.error("Unexpected response format from RemoteOK API: expected list")
                return []

            # RemoteOK includes legal notice as first element in array
            jobs_raw = [
                item for item in data
                if isinstance(item, dict) and (item.get("id") or item.get("slug"))
            ]
            return jobs_raw

        except requests.exceptions.Timeout:
            logger.error("Timeout fetching from RemoteOK API")
            return []
        except requests.exceptions.RequestException as e:
            logger.error("HTTP/Network error fetching from RemoteOK API: %s", str(e))
            return []
        except ValueError as e:
            logger.error("Invalid JSON response from RemoteOK API: %s", str(e))
            return []
        except Exception as e:
            logger.error("Unexpected error fetching from RemoteOK API: %s", str(e))
            return []

    def fetch_source_jobs(self, **kwargs: Any) -> SourceResult:
        """
        Executes fetch and returns structured SourceResult.
        """
        from app.services.normalization import normalize_remoteok_job

        raw_jobs = self.fetch_jobs_raw()
        normalized_jobs = [normalize_remoteok_job(rj) for rj in raw_jobs]

        return SourceResult(
            source_name=self.name,
            status=SourceStatus.SUCCESS,
            jobs=normalized_jobs,
            total_fetched=len(normalized_jobs),
        )
