"""
Gmail API Ingestion Subpackage for LinkedIn and Indeed Job Alerts.
"""

from app.sources.gmail.email_parser import (
    GlassdoorEmailParser,
    IndeedEmailParser,
    LinkedInEmailParser,
    NaukriEmailParser,
)
from app.sources.gmail.gmail_client import GmailAPIClient
from app.sources.gmail.gmail_source import (
    GlassdoorAlertEmailSource,
    IndeedAlertEmailSource,
    LinkedInAlertEmailSource,
    NaukriAlertEmailSource,
)
from app.sources.gmail.models import ParsedEmailData

__all__ = [
    "GmailAPIClient",
    "ParsedEmailData",
    "LinkedInEmailParser",
    "IndeedEmailParser",
    "NaukriEmailParser",
    "GlassdoorEmailParser",
    "LinkedInAlertEmailSource",
    "IndeedAlertEmailSource",
    "NaukriAlertEmailSource",
    "GlassdoorAlertEmailSource",
]
