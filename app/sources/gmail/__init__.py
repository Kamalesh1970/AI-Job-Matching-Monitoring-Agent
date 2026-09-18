"""
Gmail API Ingestion Subpackage for LinkedIn and Indeed Job Alerts.
"""

from app.sources.gmail.email_parser import IndeedEmailParser, LinkedInEmailParser
from app.sources.gmail.gmail_client import GmailAPIClient
from app.sources.gmail.gmail_source import IndeedAlertEmailSource, LinkedInAlertEmailSource
from app.sources.gmail.models import ParsedEmailData

__all__ = [
    "GmailAPIClient",
    "ParsedEmailData",
    "LinkedInEmailParser",
    "IndeedEmailParser",
    "LinkedInAlertEmailSource",
    "IndeedAlertEmailSource",
]
