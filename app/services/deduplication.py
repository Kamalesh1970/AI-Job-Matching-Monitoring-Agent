"""
Deduplication and fingerprinting service for job postings.
"""

import hashlib
import re
from typing import Optional


def normalize_text_for_fingerprint(text: Optional[str]) -> str:
    """
    Normalizes string for deterministic fingerprinting by converting to lowercase,
    removing punctuation, and normalizing whitespace.
    """
    if not text:
        return ""
    # Convert to lowercase
    lowered = text.lower().strip()
    # Replace non-alphanumeric characters with spaces
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    # Collapse multiple spaces into one single space
    normalized = re.sub(r"\s+", " ", cleaned).strip()
    return normalized


def generate_fingerprint(company: str, title: str, location: str) -> str:
    """
    Generates a deterministic SHA256 hex digest fingerprint for Level 2 cross-source deduplication.

    Args:
        company: Raw or normalized company name
        title: Raw or normalized job title
        location: Raw or normalized job location

    Returns:
        str: 64-character SHA256 hex string
    """
    norm_company = normalize_text_for_fingerprint(company)
    norm_title = normalize_text_for_fingerprint(title)
    norm_location = normalize_text_for_fingerprint(location)

    raw_fingerprint_str = f"{norm_company}|{norm_title}|{norm_location}"
    return hashlib.sha256(raw_fingerprint_str.encode("utf-8")).hexdigest()
