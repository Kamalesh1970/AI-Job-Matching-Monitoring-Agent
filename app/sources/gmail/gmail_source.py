"""
BaseJobSource implementations for LinkedIn and Indeed Gmail Alert email sources.
Executes read-only Gmail API searches, decodes email payloads, and parses job cards cleanly.
"""

import logging
from typing import Any, Dict, List, Optional

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource
from app.sources.gmail.email_parser import (
    GlassdoorEmailParser,
    IndeedEmailParser,
    LinkedInEmailParser,
    NaukriEmailParser,
)
from app.sources.gmail.gmail_client import GmailAPIClient

logger = logging.getLogger(__name__)


class LinkedInAlertEmailSource(BaseJobSource):
    """
    Job source fetcher that ingests LinkedIn job alert emails via Gmail API read-only access.
    Does NOT scrape LinkedIn directly.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailAPIClient] = None,
        query: str = "from:(linkedin.com) newer_than:2d",
        query_limit: int = 50,
    ):
        self.gmail_client = gmail_client or GmailAPIClient()
        self.query = query
        self.query_limit = query_limit

    @property
    def name(self) -> str:
        return "LinkedIn Email Alert"

    @property
    def source_identifier(self) -> str:
        return "linkedin_email"

    @property
    def source_type(self) -> str:
        return "email_alert"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_gmail_enabled"):
                return bool(config.source_gmail_enabled)
            if hasattr(config, "gmail_enabled"):
                return bool(config.gmail_enabled)
        return True

    def fetch_jobs_raw(
        self, keyword: str = "", page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Required by BaseJobSource interface. Returns raw Gmail message summaries.
        """
        try:
            messages = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
            return messages
        except Exception as e:
            logger.error("Failed to fetch raw LinkedIn alert emails: %s", str(e))
            return []

    def fetch_source_jobs(self) -> SourceResult:
        """
        Fetches, decodes, and parses LinkedIn job alert emails from Gmail.

        Returns:
            SourceResult: Container with status, parsed jobs list, and metrics.
        """
        logger.info("Starting LinkedIn email alert ingestion (query='%s')...", self.query)
        all_jobs: List[Job] = []
        failed_emails = 0
        successful_emails = 0

        try:
            message_refs = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
        except Exception as e:
            logger.error("Failed to execute Gmail API query for LinkedIn: %s", str(e))
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.FAILED,
                jobs=[],
                total_fetched=0,
                error_message=f"Gmail API error: {str(e)}",
            )

        if not message_refs:
            logger.info("No matching LinkedIn alert emails found in Gmail.")
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.SUCCESS,
                jobs=[],
                total_fetched=0,
            )

        for msg_ref in message_refs:
            msg_id = msg_ref.get("id")
            if not msg_id:
                continue

            try:
                msg_detail = self.gmail_client.get_message_detail(msg_id)
                parsed_email = self.gmail_client.decode_message_payload(msg_detail)
                email_jobs = LinkedInEmailParser.parse(parsed_email)
                all_jobs.extend(email_jobs)
                successful_emails += 1
            except Exception as e:
                logger.warning("Error processing LinkedIn email message ID '%s': %s", msg_id, str(e))
                failed_emails += 1

        status = SourceStatus.SUCCESS
        if failed_emails > 0 and successful_emails > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_emails > 0 and successful_emails == 0:
            status = SourceStatus.FAILED

        logger.info(
            "LinkedIn email ingestion completed: status=%s, %d jobs parsed from %d email(s).",
            status,
            len(all_jobs),
            successful_emails,
        )

        return SourceResult(
            source_name=self.name,
            status=status,
            jobs=all_jobs,
            total_fetched=len(all_jobs),
        )


class IndeedAlertEmailSource(BaseJobSource):
    """
    Job source fetcher that ingests Indeed job alert emails via Gmail API read-only access.
    Does NOT scrape Indeed directly.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailAPIClient] = None,
        query: str = "from:(indeed.com) newer_than:2d",
        query_limit: int = 50,
    ):
        self.gmail_client = gmail_client or GmailAPIClient()
        self.query = query
        self.query_limit = query_limit

    @property
    def name(self) -> str:
        return "Indeed Email Alert"

    @property
    def source_identifier(self) -> str:
        return "indeed_email"

    @property
    def source_type(self) -> str:
        return "email_alert"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_gmail_enabled"):
                return bool(config.source_gmail_enabled)
            if hasattr(config, "gmail_enabled"):
                return bool(config.gmail_enabled)
        return True

    def fetch_jobs_raw(
        self, keyword: str = "", page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Required by BaseJobSource interface. Returns raw Gmail message summaries.
        """
        try:
            messages = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
            return messages
        except Exception as e:
            logger.error("Failed to fetch raw Indeed alert emails: %s", str(e))
            return []

    def fetch_source_jobs(self) -> SourceResult:
        """
        Fetches, decodes, and parses Indeed job alert emails from Gmail.

        Returns:
            SourceResult: Container with status, parsed jobs list, and metrics.
        """
        logger.info("Starting Indeed email alert ingestion (query='%s')...", self.query)
        all_jobs: List[Job] = []
        failed_emails = 0
        successful_emails = 0

        try:
            message_refs = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
        except Exception as e:
            logger.error("Failed to execute Gmail API query for Indeed: %s", str(e))
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.FAILED,
                jobs=[],
                total_fetched=0,
                error_message=f"Gmail API error: {str(e)}",
            )

        if not message_refs:
            logger.info("No matching Indeed alert emails found in Gmail.")
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.SUCCESS,
                jobs=[],
                total_fetched=0,
            )

        for msg_ref in message_refs:
            msg_id = msg_ref.get("id")
            if not msg_id:
                continue

            try:
                msg_detail = self.gmail_client.get_message_detail(msg_id)
                parsed_email = self.gmail_client.decode_message_payload(msg_detail)
                email_jobs = IndeedEmailParser.parse(parsed_email)
                all_jobs.extend(email_jobs)
                successful_emails += 1
            except Exception as e:
                logger.warning("Error processing Indeed email message ID '%s': %s", msg_id, str(e))
                failed_emails += 1

        status = SourceStatus.SUCCESS
        if failed_emails > 0 and successful_emails > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_emails > 0 and successful_emails == 0:
            status = SourceStatus.FAILED

        logger.info(
            "Indeed email ingestion completed: status=%s, %d jobs parsed from %d email(s).",
            status,
            len(all_jobs),
            successful_emails,
        )

        return SourceResult(
            source_name=self.name,
            status=status,
            jobs=all_jobs,
            total_fetched=len(all_jobs),
        )


class NaukriAlertEmailSource(BaseJobSource):
    """
    Job source fetcher that ingests Naukri job alert emails via Gmail API read-only access.
    Does NOT scrape Naukri directly.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailAPIClient] = None,
        query: str = "from:(naukri.com) newer_than:2d",
        query_limit: int = 50,
    ):
        self.gmail_client = gmail_client or GmailAPIClient()
        self.query = query
        self.query_limit = query_limit

    @property
    def name(self) -> str:
        return "Naukri Email Alert"

    @property
    def source_identifier(self) -> str:
        return "naukri_email"

    @property
    def source_type(self) -> str:
        return "email_alert"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_naukri_enabled") and not config.source_naukri_enabled:
                return False
            if hasattr(config, "source_gmail_enabled"):
                return bool(config.source_gmail_enabled)
            if hasattr(config, "gmail_enabled"):
                return bool(config.gmail_enabled)
        return True

    def fetch_jobs_raw(
        self, keyword: str = "", page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Required by BaseJobSource interface. Returns raw Gmail message summaries.
        """
        try:
            messages = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
            return messages
        except Exception as e:
            logger.error("Failed to fetch raw Naukri alert emails: %s", str(e))
            return []

    def fetch_source_jobs(self) -> SourceResult:
        """
        Fetches, decodes, and parses Naukri job alert emails from Gmail.
        """
        logger.info("Starting Naukri email alert ingestion (query='%s')...", self.query)
        all_jobs: List[Job] = []
        failed_emails = 0
        successful_emails = 0

        try:
            message_refs = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
        except Exception as e:
            logger.error("Failed to execute Gmail API query for Naukri: %s", str(e))
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.FAILED,
                jobs=[],
                total_fetched=0,
                error_message=f"Gmail API error: {str(e)}",
            )

        if not message_refs:
            logger.info("No matching Naukri alert emails found in Gmail.")
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.SUCCESS,
                jobs=[],
                total_fetched=0,
            )

        for msg_ref in message_refs:
            msg_id = msg_ref.get("id")
            if not msg_id:
                continue

            try:
                msg_detail = self.gmail_client.get_message_detail(msg_id)
                parsed_email = self.gmail_client.decode_message_payload(msg_detail)
                email_jobs = NaukriEmailParser.parse(parsed_email)
                all_jobs.extend(email_jobs)
                successful_emails += 1
            except Exception as e:
                logger.warning("Error processing Naukri email message ID '%s': %s", msg_id, str(e))
                failed_emails += 1

        status = SourceStatus.SUCCESS
        if failed_emails > 0 and successful_emails > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_emails > 0 and successful_emails == 0:
            status = SourceStatus.FAILED

        logger.info(
            "Naukri email ingestion completed: status=%s, %d jobs parsed from %d email(s).",
            status,
            len(all_jobs),
            successful_emails,
        )

        return SourceResult(
            source_name=self.name,
            status=status,
            jobs=all_jobs,
            total_fetched=len(all_jobs),
        )


class GlassdoorAlertEmailSource(BaseJobSource):
    """
    Job source fetcher that ingests Glassdoor job alert emails via Gmail API read-only access.
    Does NOT scrape Glassdoor directly.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailAPIClient] = None,
        query: str = "from:(glassdoor.com) newer_than:2d",
        query_limit: int = 50,
    ):
        self.gmail_client = gmail_client or GmailAPIClient()
        self.query = query
        self.query_limit = query_limit

    @property
    def name(self) -> str:
        return "Glassdoor Email Alert"

    @property
    def source_identifier(self) -> str:
        return "glassdoor_email"

    @property
    def source_type(self) -> str:
        return "email_alert"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_glassdoor_enabled") and not config.source_glassdoor_enabled:
                return False
            if hasattr(config, "source_gmail_enabled"):
                return bool(config.source_gmail_enabled)
            if hasattr(config, "gmail_enabled"):
                return bool(config.gmail_enabled)
        return True

    def fetch_jobs_raw(
        self, keyword: str = "", page: int = 1, results_per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Required by BaseJobSource interface. Returns raw Gmail message summaries.
        """
        try:
            messages = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
            return messages
        except Exception as e:
            logger.error("Failed to fetch raw Glassdoor alert emails: %s", str(e))
            return []

    def fetch_source_jobs(self) -> SourceResult:
        """
        Fetches, decodes, and parses Glassdoor job alert emails from Gmail.
        """
        logger.info("Starting Glassdoor email alert ingestion (query='%s')...", self.query)
        all_jobs: List[Job] = []
        failed_emails = 0
        successful_emails = 0

        try:
            message_refs = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
        except Exception as e:
            logger.error("Failed to execute Gmail API query for Glassdoor: %s", str(e))
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.FAILED,
                jobs=[],
                total_fetched=0,
                error_message=f"Gmail API error: {str(e)}",
            )

        if not message_refs:
            logger.info("No matching Glassdoor alert emails found in Gmail.")
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.SUCCESS,
                jobs=[],
                total_fetched=0,
            )

        for msg_ref in message_refs:
            msg_id = msg_ref.get("id")
            if not msg_id:
                continue

            try:
                msg_detail = self.gmail_client.get_message_detail(msg_id)
                parsed_email = self.gmail_client.decode_message_payload(msg_detail)
                email_jobs = GlassdoorEmailParser.parse(parsed_email)
                all_jobs.extend(email_jobs)
                successful_emails += 1
            except Exception as e:
                logger.warning("Error processing Glassdoor email message ID '%s': %s", msg_id, str(e))
                failed_emails += 1

        status = SourceStatus.SUCCESS
        if failed_emails > 0 and successful_emails > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_emails > 0 and successful_emails == 0:
            status = SourceStatus.FAILED

        logger.info(
            "Glassdoor email ingestion completed: status=%s, %d jobs parsed from %d email(s).",
            status,
            len(all_jobs),
            successful_emails,
        )

        return SourceResult(
            source_name=self.name,
            status=status,
            jobs=all_jobs,
            total_fetched=len(all_jobs),
        )
