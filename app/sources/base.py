"""
Abstract Base Class for job source fetchers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


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
