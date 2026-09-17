"""
Data models for the job ingestion pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Job:
    """
    Normalized internal Job representation.
    """

    source: str
    source_job_id: str
    title: str
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    created_at: Optional[str] = None
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    employment_type: Optional[str] = None
    category: Optional[str] = None
    fingerprint: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Converts Job instance to dictionary."""
        return {
            "source": self.source,
            "source_job_id": self.source_job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "url": self.url,
            "created_at": self.created_at,
            "fetched_at": self.fetched_at,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "employment_type": self.employment_type,
            "category": self.category,
            "fingerprint": self.fingerprint,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
        }
