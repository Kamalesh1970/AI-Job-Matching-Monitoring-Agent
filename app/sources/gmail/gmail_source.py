"""
BaseJobSource implementations for LinkedIn and Indeed Gmail Alert email sources.
Executes read-only Gmail API searches, decodes email payloads, and parses job cards cleanly.
"""

import logging
from typing import Any, Dict, List, Optional

from app.db.models import Job, SourceResult, SourceStatus
from app.sources.base import BaseJobSource
from app.sources.gmail.email_parser import (
    CutshortEmailParser,
    GlassdoorEmailParser,
    HiristEmailParser,
    IndeedEmailParser,
    LinkedInEmailParser,
    NaukriEmailParser,
    UnstopEmailParser,
    WellfoundEmailParser,
    founditEmailParser,
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


class UnstopAlertEmailSource(BaseJobSource):
    """
    Job source fetcher that ingests Unstop job alert emails via Gmail API read-only access.
    Does NOT scrape Unstop directly.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailAPIClient] = None,
        query: str = "from:(unstop.com OR d2c.in) newer_than:2d",
        query_limit: int = 50,
    ):
        self.gmail_client = gmail_client or GmailAPIClient()
        self.query = query
        self.query_limit = query_limit

    @property
    def name(self) -> str:
        return "Unstop Email Alert"

    @property
    def source_identifier(self) -> str:
        return "unstop_email"

    @property
    def source_type(self) -> str:
        return "email_alert"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_unstop_enabled") and not config.source_unstop_enabled:
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
            logger.error("Failed to fetch raw Unstop alert emails: %s", str(e))
            return []

    def fetch_source_jobs(self) -> SourceResult:
        """
        Fetches, decodes, and parses Unstop job alert emails from Gmail.
        """
        logger.info("Starting Unstop email alert ingestion (query='%s')...", self.query)
        all_jobs: List[Job] = []
        failed_emails = 0
        successful_emails = 0

        try:
            message_refs = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
        except Exception as e:
            logger.error("Failed to execute Gmail API query for Unstop: %s", str(e))
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.FAILED,
                jobs=[],
                total_fetched=0,
                error_message=f"Gmail API error: {str(e)}",
            )

        if not message_refs:
            logger.info("No matching Unstop alert emails found in Gmail.")
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
                email_jobs = UnstopEmailParser.parse(parsed_email)
                all_jobs.extend(email_jobs)
                successful_emails += 1
            except Exception as e:
                logger.warning("Error processing Unstop email message ID '%s': %s", msg_id, str(e))
                failed_emails += 1

        status = SourceStatus.SUCCESS
        if failed_emails > 0 and successful_emails > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_emails > 0 and successful_emails == 0:
            status = SourceStatus.FAILED

        logger.info(
            "Unstop email ingestion completed: status=%s, %d jobs parsed from %d email(s).",
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


class founditAlertEmailSource(BaseJobSource):
    """
    Job source fetcher that ingests foundit job alert emails via Gmail API read-only access.
    Does NOT scrape foundit directly.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailAPIClient] = None,
        query: str = "from:(foundit.in OR monsterindia.com) newer_than:2d",
        query_limit: int = 50,
    ):
        self.gmail_client = gmail_client or GmailAPIClient()
        self.query = query
        self.query_limit = query_limit

    @property
    def name(self) -> str:
        return "foundit Email Alert"

    @property
    def source_identifier(self) -> str:
        return "foundit_email"

    @property
    def source_type(self) -> str:
        return "email_alert"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_foundit_enabled") and not config.source_foundit_enabled:
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
            logger.error("Failed to fetch raw foundit alert emails: %s", str(e))
            return []

    def fetch_source_jobs(self) -> SourceResult:
        """
        Fetches, decodes, and parses foundit job alert emails from Gmail.
        """
        logger.info("Starting foundit email alert ingestion (query='%s')...", self.query)
        all_jobs: List[Job] = []
        failed_emails = 0
        successful_emails = 0

        try:
            message_refs = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
        except Exception as e:
            logger.error("Failed to execute Gmail API query for foundit: %s", str(e))
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.FAILED,
                jobs=[],
                total_fetched=0,
                error_message=f"Gmail API error: {str(e)}",
            )

        if not message_refs:
            logger.info("No matching foundit alert emails found in Gmail.")
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
                email_jobs = founditEmailParser.parse(parsed_email)
                all_jobs.extend(email_jobs)
                successful_emails += 1
            except Exception as e:
                logger.warning("Error processing foundit email message ID '%s': %s", msg_id, str(e))
                failed_emails += 1

        status = SourceStatus.SUCCESS
        if failed_emails > 0 and successful_emails > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_emails > 0 and successful_emails == 0:
            status = SourceStatus.FAILED

        logger.info(
            "foundit email ingestion completed: status=%s, %d jobs parsed from %d email(s).",
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


class CutshortAlertEmailSource(BaseJobSource):
    """
    Job source fetcher that ingests Cutshort job alert emails via Gmail API read-only access.
    Does NOT scrape Cutshort directly.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailAPIClient] = None,
        query: str = "from:(cutshort.io OR cutshort.com) newer_than:2d",
        query_limit: int = 50,
    ):
        self.gmail_client = gmail_client or GmailAPIClient()
        self.query = query
        self.query_limit = query_limit

    @property
    def name(self) -> str:
        return "Cutshort Email Alert"

    @property
    def source_identifier(self) -> str:
        return "cutshort_email"

    @property
    def source_type(self) -> str:
        return "email_alert"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_cutshort_enabled") and not config.source_cutshort_enabled:
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
            logger.error("Failed to fetch raw Cutshort alert emails: %s", str(e))
            return []

    def fetch_source_jobs(self) -> SourceResult:
        """
        Fetches, decodes, and parses Cutshort job alert emails from Gmail.
        """
        logger.info("Starting Cutshort email alert ingestion (query='%s')...", self.query)
        all_jobs: List[Job] = []
        failed_emails = 0
        successful_emails = 0

        try:
            message_refs = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
        except Exception as e:
            logger.error("Failed to execute Gmail API query for Cutshort: %s", str(e))
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.FAILED,
                jobs=[],
                total_fetched=0,
                error_message=f"Gmail API error: {str(e)}",
            )

        if not message_refs:
            logger.info("No matching Cutshort alert emails found in Gmail.")
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
                email_jobs = CutshortEmailParser.parse(parsed_email)
                all_jobs.extend(email_jobs)
                successful_emails += 1
            except Exception as e:
                logger.warning("Error processing Cutshort email message ID '%s': %s", msg_id, str(e))
                failed_emails += 1

        status = SourceStatus.SUCCESS
        if failed_emails > 0 and successful_emails > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_emails > 0 and successful_emails == 0:
            status = SourceStatus.FAILED

        logger.info(
            "Cutshort email ingestion completed: status=%s, %d jobs parsed from %d email(s).",
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


class HiristAlertEmailSource(BaseJobSource):
    """
    Job source fetcher that ingests Hirist job alert emails via Gmail API read-only access.
    Does NOT scrape Hirist directly.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailAPIClient] = None,
        query: str = "from:(hirist.com OR hirist.tech) newer_than:2d",
        query_limit: int = 50,
    ):
        self.gmail_client = gmail_client or GmailAPIClient()
        self.query = query
        self.query_limit = query_limit

    @property
    def name(self) -> str:
        return "Hirist Email Alert"

    @property
    def source_identifier(self) -> str:
        return "hirist_email"

    @property
    def source_type(self) -> str:
        return "email_alert"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_hirist_enabled") and not config.source_hirist_enabled:
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
            logger.error("Failed to fetch raw Hirist alert emails: %s", str(e))
            return []

    def fetch_source_jobs(self) -> SourceResult:
        """
        Fetches, decodes, and parses Hirist job alert emails from Gmail.
        """
        logger.info("Starting Hirist email alert ingestion (query='%s')...", self.query)
        all_jobs: List[Job] = []
        failed_emails = 0
        successful_emails = 0

        try:
            message_refs = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
        except Exception as e:
            logger.error("Failed to execute Gmail API query for Hirist: %s", str(e))
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.FAILED,
                jobs=[],
                total_fetched=0,
                error_message=f"Gmail API error: {str(e)}",
            )

        if not message_refs:
            logger.info("No matching Hirist alert emails found in Gmail.")
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
                email_jobs = HiristEmailParser.parse(parsed_email)
                all_jobs.extend(email_jobs)
                successful_emails += 1
            except Exception as e:
                logger.warning("Error processing Hirist email message ID '%s': %s", msg_id, str(e))
                failed_emails += 1

        status = SourceStatus.SUCCESS
        if failed_emails > 0 and successful_emails > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_emails > 0 and successful_emails == 0:
            status = SourceStatus.FAILED

        logger.info(
            "Hirist email ingestion completed: status=%s, %d jobs parsed from %d email(s).",
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


class WellfoundAlertEmailSource(BaseJobSource):
    """
    Job source fetcher that ingests Wellfound job alert emails via Gmail API read-only access.
    Does NOT scrape Wellfound directly.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailAPIClient] = None,
        query: str = "from:(wellfound.com OR angel.co) newer_than:2d",
        query_limit: int = 50,
    ):
        self.gmail_client = gmail_client or GmailAPIClient()
        self.query = query
        self.query_limit = query_limit

    @property
    def name(self) -> str:
        return "Wellfound Email Alert"

    @property
    def source_identifier(self) -> str:
        return "wellfound_email"

    @property
    def source_type(self) -> str:
        return "email_alert"

    def is_enabled(self, config: Optional[Any] = None) -> bool:
        if config is not None:
            if hasattr(config, "source_wellfound_enabled") and not config.source_wellfound_enabled:
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
            logger.error("Failed to fetch raw Wellfound alert emails: %s", str(e))
            return []

    def fetch_source_jobs(self) -> SourceResult:
        """
        Fetches, decodes, and parses Wellfound job alert emails from Gmail.
        """
        logger.info("Starting Wellfound email alert ingestion (query='%s')...", self.query)
        all_jobs: List[Job] = []
        failed_emails = 0
        successful_emails = 0

        try:
            message_refs = self.gmail_client.search_messages(query=self.query, max_results=self.query_limit)
        except Exception as e:
            logger.error("Failed to execute Gmail API query for Wellfound: %s", str(e))
            return SourceResult(
                source_name=self.name,
                status=SourceStatus.FAILED,
                jobs=[],
                total_fetched=0,
                error_message=f"Gmail API error: {str(e)}",
            )

        if not message_refs:
            logger.info("No matching Wellfound alert emails found in Gmail.")
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
                email_jobs = WellfoundEmailParser.parse(parsed_email)
                all_jobs.extend(email_jobs)
                successful_emails += 1
            except Exception as e:
                logger.warning("Error processing Wellfound email message ID '%s': %s", msg_id, str(e))
                failed_emails += 1

        status = SourceStatus.SUCCESS
        if failed_emails > 0 and successful_emails > 0:
            status = SourceStatus.PARTIAL_FAILURE
        elif failed_emails > 0 and successful_emails == 0:
            status = SourceStatus.FAILED

        logger.info(
            "Wellfound email ingestion completed: status=%s, %d jobs parsed from %d email(s).",
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
