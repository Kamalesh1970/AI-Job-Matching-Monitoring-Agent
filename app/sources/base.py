"""
Abstract Base Class for job source fetchers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.db.models import SourceResult, SourceStatus


class BaseJobSource(ABC):
    """
    Abstract interface for all job ingestion sources.
    Future sources (e.g., Jooble, Arbeitnow, RemoteOK) will inherit from this base class.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the human-readable name of the source (e.g. 'Adzuna')."""
        pass

    @property
    def source_identifier(self) -> str:
        """Returns the unique machine-readable identifier of the source (e.g. 'adzuna')."""
        return self.name.lower().replace(" ", "_")

    @property
    def source_type(self) -> str:
        """Returns the category of the source: 'api', 'scraper', 'email_alert', 'ats'."""
        return "api"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        """
        Determines whether this source is enabled in application configuration.
        """
        return True

    @abstractmethod
    def fetch_jobs_raw(
        self, keyword: str, page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetches raw job dictionaries from the underlying source for a given keyword and page.

        Args:
            keyword: The search keyword (e.g. 'Machine Learning Engineer').
            page: Page number for pagination (1-indexed).
            results_per_page: Number of items per page.

        Returns:
            List[Dict[str, Any]]: List of raw job result dictionaries.
        """
        pass

    def fetch_source_jobs(self, **kwargs: Any) -> SourceResult:
        """
        Standardized execution entry point for fetching and normalizing jobs.

        Returns:
            SourceResult containing execution status, job payload, metrics, and error info.
        """
        return SourceResult(
            source_name=self.name,
            status=SourceStatus.SUCCESS,
            jobs=[],
            total_fetched=0,
        )
