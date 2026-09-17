"""
Data models for the job ingestion pipeline and matching engine.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional, Set


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
    id: Optional[int] = None

    def to_dict(self) -> dict:
        """Converts Job instance to dictionary."""
        return {
            "id": self.id,
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


@dataclass
class Resume:
    """
    Internal representation of the candidate resume.
    """

    raw_text: str
    normalized_text: str
    skills: Set[str] = field(default_factory=set)
    embedding: Optional[Any] = None


@dataclass
class MatchResult:
    """
    Detailed match evaluation result between a resume and a job.
    """

    job_id: Optional[int] = None
    source_job_id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    similarity_score: float = 0.0  # Cosine similarity (0.0 - 1.0)
    skill_score: float = 0.0       # Skill overlap ratio (0.0 - 1.0)
    rule_score: float = 0.0        # Rule compatibility ratio (0.0 - 1.0)
    final_score: float = 0.0       # Weighted match score (0.0 - 100.0)
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    experience_status: str = "UNKNOWN"  # MATCH, MISMATCH, UNKNOWN
    location_status: str = "UNKNOWN"    # MATCH, MISMATCH, UNKNOWN
    match_status: str = "MATCH"         # MATCH, PARTIAL_MATCH, FILTERED
    reasons: List[str] = field(default_factory=list)
    calculated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Converts MatchResult to dictionary format."""
        return {
            "job_id": self.job_id,
            "source_job_id": self.source_job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "similarity_score": self.similarity_score,
            "skill_score": self.skill_score,
            "rule_score": self.rule_score,
            "final_score": self.final_score,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "experience_status": self.experience_status,
            "location_status": self.location_status,
            "match_status": self.match_status,
            "reasons": self.reasons,
            "calculated_at": self.calculated_at,
        }
