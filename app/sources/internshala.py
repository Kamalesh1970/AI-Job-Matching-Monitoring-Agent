"""
Internshala job and internship source fetcher client using BeautifulSoup4.
"""

import hashlib
import logging
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


def normalize_internshala_url(url: str) -> str:
    """
    Normalizes Internshala URLs by stripping query tracking parameters
    and ensuring absolute URL format.
    """
    if not url:
        return ""

    url_str = url.strip()
    if url_str.startswith("/"):
        url_str = urljoin("https://internshala.com", url_str)

    parsed = urlparse(url_str)
    # Strip query parameters and fragment to leave clean canonical URL
    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return clean_url


class InternshalaJobSource(BaseJobSource):
    """
    Client for fetching job and internship postings from Internshala via HTML parsing.
    Does NOT attempt anti-bot bypass, proxy rotation, or CAPTCHA solving.
    """

    BASE_URL_TEMPLATE = "https://internshala.com/internships/keywords-{slug}/page-{page}/"

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
        "(Personal Job Agent; Conservative Ingestion)"
    )

    BLOCK_SIGNATURES = [
        "cloudflare",
        "attention required!",
        "security check",
        "cf-browser-verification",
        "ddos protection",
        "captcha",
        "blocked",
        "access denied",
        "please solve the captcha",
    ]

    def __init__(
        self,
        request_delay_min: float = 2.0,
        request_delay_max: float = 5.0,
        timeout: int = 15,
        user_agent: Optional[str] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ):
        self.request_delay_min = request_delay_min
        self.request_delay_max = request_delay_max
        self.timeout = timeout
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.sleep_fn = sleep_fn or time.sleep

    @property
    def name(self) -> str:
        return "Internshala"

    def _slugify_keyword(self, keyword: str) -> str:
        """Converts keyword phrase to URL slug (e.g. 'machine learning' -> 'machine-learning')."""
        cleaned = re.sub(r"[^\w\s-]", "", keyword.lower().strip())
        slug = re.sub(r"[\s_]+", "-", cleaned)
        return slug

    def _apply_rate_limit(self):
        """Applies randomized delay jitter between requests."""
        if self.request_delay_max > 0:
            delay = random.uniform(self.request_delay_min, self.request_delay_max)
            logger.debug("Applying Internshala rate-limit delay: %.2fs", delay)
            self.sleep_fn(delay)

    def _check_if_blocked(self, response_text: str, status_code: int) -> bool:
        """Determines whether response indicates automated access blocking or CAPTCHA challenge."""
        if status_code in (403, 429, 503):
            return True

        lowered_html = response_text.lower()
        for signature in self.BLOCK_SIGNATURES:
            if signature in lowered_html:
                return True

        return False

    def fetch_jobs_raw(
        self, keyword: str, page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetches raw job dictionaries from Internshala for a given keyword and page.
        Returns empty list on failure or block without crashing.
        """
        slug = self._slugify_keyword(keyword)
        url = self.BASE_URL_TEMPLATE.format(slug=slug, page=page)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        try:
            logger.info("Requesting Internshala page: keyword='%s', page=%d, url='%s'", keyword, page, url)
            response = requests.get(url, headers=headers, timeout=self.timeout)

            if self._check_if_blocked(response.text, response.status_code):
                logger.warning(
                    "Internshala request received HTTP status %d or challenge/block page for keyword='%s', page=%d.",
                    response.status_code,
                    keyword,
                    page,
                )
                return []

            response.raise_for_status()
            parsed_cards = self.parse_html_listings(response.text)
            return parsed_cards

        except requests.exceptions.Timeout:
            logger.error("Timeout connecting to Internshala for keyword='%s', page=%d", keyword, page)
            return []
        except requests.exceptions.HTTPError as e:
            logger.error("HTTP status error from Internshala for keyword='%s': %s", keyword, str(e))
            return []
        except requests.exceptions.RequestException as e:
            logger.error("Request failed for Internshala with keyword='%s': %s", keyword, str(e))
            return []
        except Exception as e:
            logger.error("Unexpected error fetching Internshala listings for keyword='%s': %s", keyword, str(e))
            return []

    def parse_html_listings(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parses Internshala HTML listing page and extracts structured dictionaries for each card.
        Robust fallback selectors isolate missing elements so no single malformed card crashes parsing.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        results: List[Dict[str, Any]] = []

        # Card container selectors (primary & fallback)
        cards = soup.select(".individual_internship")
        if not cards:
            cards = soup.select(".internship_list_container")
        if not cards:
            cards = soup.select("[data-href]")

        if not cards:
            logger.debug("No Internshala job/internship cards matched in HTML.")
            return []

        for card in cards:
            try:
                # 1. URL & Profile Title
                title_elem = (
                    card.select_one(".heading_4_5.profile a")
                    or card.select_one(".profile a")
                    or card.select_one(".job-title a")
                    or card.select_one("a.view_detail_button")
                    or card.select_one("a[href*='/internship/']")
                    or card.select_one("a[href*='/job/']")
                )

                raw_url = ""
                title = ""
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    raw_url = title_elem.get("href", "").strip()

                if not raw_url and card.has_attr("data-href"):
                    raw_url = card.get("data-href", "").strip()

                if not title:
                    # Fallback to card heading text if title element not found
                    heading = card.select_one(".heading_4_5") or card.select_one(".profile")
                    if heading:
                        title = heading.get_text(strip=True)

                if not title:
                    continue  # Skip card if no title could be extracted

                canonical_url = normalize_internshala_url(raw_url)

                # 2. Source Job ID
                source_job_id = (
                    card.get("data-id")
                    or card.get("data-internship-id")
                    or card.get("data-job-id")
                    or card.get("id")
                    or ""
                )

                if isinstance(source_job_id, str) and source_job_id.startswith("internship_list_container_"):
                    source_job_id = source_job_id.replace("internship_list_container_", "")

                if not source_job_id and canonical_url:
                    # Derive deterministic SHA256 snippet from canonical URL if explicit ID missing
                    source_job_id = "ish_" + hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]

                # 3. Company Name
                company_elem = (
                    card.select_one(".heading_6.company_name a")
                    or card.select_one(".company_name a")
                    or card.select_one(".company_name")
                    or card.select_one(".company-name")
                )
                company = company_elem.get_text(strip=True) if company_elem else ""

                # 4. Location
                location_elem = (
                    card.select_one("#location_names")
                    or card.select_one(".location_link")
                    or card.select_one(".locations")
                    or card.select_one(".location")
                )
                location = location_elem.get_text(strip=True) if location_elem else ""

                # 5. Salary / Stipend
                stipend_elem = (
                    card.select_one(".stipend")
                    or card.select_one(".salary")
                    or card.select_one(".stipend_container")
                )
                salary_text = stipend_elem.get_text(strip=True) if stipend_elem else ""

                # 6. Employment Type
                type_elem = (
                    card.select_one(".label_container")
                    or card.select_one(".status-container")
                    or card.select_one(".employment_type")
                )
                employment_type = type_elem.get_text(strip=True) if type_elem else "Internship"

                # 7. Posted Date / Status
                posted_elem = (
                    card.select_one(".status-container .status-success")
                    or card.select_one(".posted_by_container")
                    or card.select_one(".status-inactive")
                )
                posted_at = posted_elem.get_text(strip=True) if posted_elem else None

                # 8. Description summary
                desc_elem = card.select_one(".internship_other_details_container") or card.select_one(".detail-row")
                description = desc_elem.get_text(" ", strip=True) if desc_elem else title

                results.append(
                    {
                        "source_job_id": str(source_job_id),
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": canonical_url,
                        "salary_text": salary_text,
                        "employment_type": employment_type,
                        "created_at": posted_at,
                        "description": description,
                        "raw_url": raw_url,
                    }
                )

            except Exception as e:
                logger.warning("Error parsing individual Internshala card: %s", str(e))
                continue

        return results

    def fetch_jobs_for_keyword(
        self, keyword: str, max_pages: int = 3
    ) -> Tuple[List[Job], bool]:
        """
        Fetches and normalizes jobs for a single keyword across max_pages.

        Returns:
            Tuple[List[Job], bool]: (list of normalized Job objects, success_flag)
        """
        from app.services.normalization import normalize_internshala_job

        jobs: List[Job] = []
        success = True

        for page in range(1, max_pages + 1):
            if page > 1:
                self._apply_rate_limit()

            raw_cards = self.fetch_jobs_raw(keyword=keyword, page=page)
            if not raw_cards:
                if page == 1:
                    success = False
                break

            for card in raw_cards:
                jobs.append(normalize_internshala_job(card))

        return jobs, success

    def fetch_source_jobs(

        self, keywords: List[str], max_pages: int = 3
    ) -> SourceResult:
        """
        Executes job fetching across multiple search keywords and pages.

        Returns structured SourceResult indicating SUCCESS, PARTIAL_FAILURE, FAILED, or BLOCKED.
        """
        from app.services.normalization import normalize_internshala_job

        all_jobs: List[Job] = []
        total_keywords = len(keywords)
        successful_keywords = 0
        failed_keywords = 0
        blocked = False
        error_msg = None

        logger.info("Starting Internshala fetch across %d keywords (max_pages=%d)...", total_keywords, max_pages)

        for kw_idx, keyword in enumerate(keywords):
            if blocked:
                logger.info("Skipping keyword '%s' due to previous blocking response.", keyword)
                break

            kw_jobs_count = 0
            kw_failed = False

            for page in range(1, max_pages + 1):
                if kw_idx > 0 or page > 1:
                    self._apply_rate_limit()

                slug = self._slugify_keyword(keyword)
                url = self.BASE_URL_TEMPLATE.format(slug=slug, page=page)

                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }

                try:
                    response = requests.get(url, headers=headers, timeout=self.timeout)

                    if self._check_if_blocked(response.text, response.status_code):
                        logger.warning("Internshala blocked request on keyword '%s', page %d (Status %d)", keyword, page, response.status_code)
                        blocked = True
                        error_msg = f"Request blocked or CAPTCHA returned (HTTP {response.status_code})"
                        break

                    response.raise_for_status()
                    cards = self.parse_html_listings(response.text)

                    if not cards:
                        # Page returned no listings, stop paginating for this keyword
                        break

                    for card_dict in cards:
                        job = normalize_internshala_job(card_dict)
                        all_jobs.append(job)
                        kw_jobs_count += 1

                except requests.exceptions.RequestException as e:
                    logger.error("Network error on Internshala keyword '%s' page %d: %s", keyword, page, str(e))
                    kw_failed = True
                    error_msg = f"Network error: {str(e)}"
                    break
                except Exception as e:
                    logger.error("Parsing error on Internshala keyword '%s' page %d: %s", keyword, page, str(e))
                    kw_failed = True
                    error_msg = f"Parsing error: {str(e)}"
                    break

            if blocked:
                break

            if kw_failed:
                failed_keywords += 1
            else:
                successful_keywords += 1

        # Status determination
        if blocked and not all_jobs:
            status = SourceStatus.BLOCKED
        elif blocked and all_jobs:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_keywords > 0 and successful_keywords > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_keywords > 0 and successful_keywords == 0:
            status = SourceStatus.FAILED
        else:
            status = SourceStatus.SUCCESS

        logger.info(
            "Internshala fetch finished with status=%s: %d jobs fetched across %d/%d keywords.",
            status,
            len(all_jobs),
            successful_keywords,
            total_keywords,
        )

        return SourceResult(
            source_name=self.name,
            status=status,
            jobs=all_jobs,
            total_fetched=len(all_jobs),
            error_message=error_msg,
        )
