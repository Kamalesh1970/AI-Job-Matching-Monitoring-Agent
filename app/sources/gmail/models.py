"""
Data models for raw Gmail email message structures and alert payloads.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedEmailData:
    """
    Decoded MIME structure of an ingested Gmail email message.
    """

    message_id: str
    received_at: str
    subject: str = ""
    sender: str = ""
    plain_text: str = ""
    html_content: str = ""
