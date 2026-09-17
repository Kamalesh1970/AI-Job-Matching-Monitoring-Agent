"""
Adzuna API job source fetcher client.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import requests

from app.db.models import Job
from app.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


class AdzunaJobSource(BaseJobSource):
    """
    Client for fetching job postings via the Adzuna API.
    """

    BASE_URL_TEMPLATE = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

    def __init__(
        self,
        app_id: str,
        app_key: str,
        country: str = "in",
        timeout: int = 15,
    ):
        self.app_id = app_id
        self.app_key = app_key
        self.country = country
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "Adzuna"

    def fetch_jobs_raw(
        self, keyword: str, page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetches a single page of raw job results from Adzuna API.

        Returns an empty list on failure without raising exceptions.
        """
        url = self.BASE_URL_TEMPLATE.format(country=self.country, page=page)
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": results_per_page,
            "what": keyword,
            "content-type": "application/json",
        }

        try:
            logger.info("Requesting Adzuna API: keyword='%s', page=%d", keyword, page)
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                logger.error(
                    "Unexpected JSON response type from Adzuna for keyword='%s': expected dict, got %s",
                    keyword,
                    type(data).__name__,
                )
                return []

            results = data.get("results")
            if not isinstance(results, list):
                logger.error(
                    "Malformed response from Adzuna for keyword='%s': 'results' field is not a list",
                    keyword,
                )
                return []

            return results

        except requests.exceptions.Timeout:
            logger.error("Timeout occurred while contacting Adzuna API for keyword='%s', page=%d", keyword, page)
            return []
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection error with Adzuna API for keyword='%s': %s", keyword, str(e))
            return []
        except requests.exceptions.HTTPError as e:
            logger.error(
                "HTTP status error %s from Adzuna API for keyword='%s'",
                response.status_code if 'response' in locals() and response else 'N/A',
                keyword,
            )
            return []
        except requests.exceptions.RequestException as e:
            logger.error("Request failed for Adzuna API with keyword='%s': %s", keyword, str(e))
            return []
        except ValueError as e:
            logger.error("Failed to parse JSON response from Adzuna for keyword='%s': %s", keyword, str(e))
            return []
        except Exception as e:
            logger.error("Unexpected error fetching from Adzuna for keyword='%s': %s", keyword, str(e))
            return []

    def fetch_jobs_for_keyword(
        self, keyword: str, max_pages: int = 2, results_per_page: int = 20
    ) -> Tuple[List[Job], bool]:
        """
        Fetches and normalizes jobs for a keyword across max_pages.

        Returns:
            Tuple[List[Job], bool]: (list of normalized Job objects, success_flag)
            success_flag is True if at least page 1 completed without network/HTTP errors.
        """
        from app.services.normalization import normalize_adzuna_job

        all_jobs: List[Job] = []
        any_success = False

        for page in range(1, max_pages + 1):
            raw_jobs = self.fetch_jobs_raw(
                keyword=keyword, page=page, results_per_page=results_per_page
            )
            if raw_jobs:
                any_success = True
                for raw_job in raw_jobs:
                    job = normalize_adzuna_job(raw_job)
                    all_jobs.append(job)
            else:
                # If page 1 fails, mark keyword attempt as having failed request
                if page == 1:
                    logger.warning("No jobs returned or request failed on page 1 for keyword '%s'", keyword)

        return all_jobs, any_success
