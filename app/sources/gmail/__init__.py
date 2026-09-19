"""
Gmail API Ingestion Subpackage for LinkedIn and Indeed Job Alerts.
"""

from app.sources.gmail.email_parser import (
    CutshortEmailParser,
    GlassdoorEmailParser,
    HiristEmailParser,
    IndeedEmailParser,
    LinkedInEmailParser,
    NaukriEmailParser,
    UnstopEmailParser,
    classify_email,
    founditEmailParser,
)
from app.sources.gmail.gmail_client import GmailAPIClient
from app.sources.gmail.gmail_source import (
    CutshortAlertEmailSource,
    GlassdoorAlertEmailSource,
    HiristAlertEmailSource,
    IndeedAlertEmailSource,
    LinkedInAlertEmailSource,
    NaukriAlertEmailSource,
    UnstopAlertEmailSource,
    founditAlertEmailSource,
)
from app.sources.gmail.models import ParsedEmailData

__all__ = [
    "GmailAPIClient",
    "ParsedEmailData",
    "LinkedInEmailParser",
    "IndeedEmailParser",
    "NaukriEmailParser",
    "GlassdoorEmailParser",
    "UnstopEmailParser",
    "founditEmailParser",
    "CutshortEmailParser",
    "HiristEmailParser",
    "classify_email",
    "LinkedInAlertEmailSource",
    "IndeedAlertEmailSource",
    "NaukriAlertEmailSource",
    "GlassdoorAlertEmailSource",
    "UnstopAlertEmailSource",
    "founditAlertEmailSource",
    "CutshortAlertEmailSource",
    "HiristAlertEmailSource",
]


