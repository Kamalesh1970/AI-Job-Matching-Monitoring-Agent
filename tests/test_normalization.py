"""
Tests for app/services/normalization.py.
"""

from app.db.models import Job
from app.services.normalization import (
    normalize_adzuna_job,
    normalize_salary,
    strip_html,
)


def test_strip_html():
    """Test HTML tag removal from strings."""
    assert strip_html("<strong>Senior AI Engineer</strong>") == "Senior AI Engineer"
    assert strip_html("<p>We are hiring <span>Data Scientists</span>.</p>") == "We are hiring Data Scientists."
    assert strip_html(None) == ""
    assert strip_html("") == ""


def test_normalize_salary():
    """Test salary normalization to float or None."""
    assert normalize_salary(50000) == 50000.0
    assert normalize_salary("65000.50") == 65000.50
    assert normalize_salary(None) is None
    assert normalize_salary("invalid") is None


def test_normalize_complete_job():
    """Test normalizing a complete raw Adzuna job dictionary."""
    raw_job = {
        "id": "adz_98765",
        "title": "<strong>Machine Learning Engineer</strong>",
        "company": {"display_name": "Tech Corp Pvt Ltd"},
        "location": {"display_name": "Bengaluru, Karnataka, India"},
        "description": "<p>Develop state-of-the-art LLM pipelines.</p>",
        "redirect_url": "https://adzuna.in/land/ad/98765",
        "created": "2026-09-15T10:30:00Z",
        "salary_min": 800000,
        "salary_max": 1200000,
        "salary_currency": "INR",
        "contract_type": "full_time",
        "category": {"label": "IT Jobs"},
    }

    job = normalize_adzuna_job(raw_job)

    assert isinstance(job, Job)
    assert job.source == "Adzuna"
    assert job.source_job_id == "adz_98765"
    assert job.title == "Machine Learning Engineer"
    assert job.company == "Tech Corp Pvt Ltd"
    assert job.location == "Bengaluru, Karnataka, India"
    assert job.description == "Develop state-of-the-art LLM pipelines."
    assert job.url == "https://adzuna.in/land/ad/98765"
    assert job.created_at == "2026-09-15T10:30:00Z"
    assert job.fetched_at is not None
    assert job.salary_min == 800000.0
    assert job.salary_max == 1200000.0
    assert job.salary_currency == "INR"
    assert job.employment_type == "full_time"
    assert job.category == "IT Jobs"
    assert job.fingerprint is not None
    assert len(job.fingerprint) == 64  # SHA256 hex string length


def test_normalize_missing_optional_fields():
    """Test normalizing raw dictionary with missing/null optional fields."""
    raw_job = {
        "id": 112233,
        "title": "Data Scientist",
    }

    job = normalize_adzuna_job(raw_job)

    assert job.source == "Adzuna"
    assert job.source_job_id == "112233"
    assert job.title == "Data Scientist"
    assert job.company == ""
    assert job.location == ""
    assert job.description == ""
    assert job.url == ""
    assert job.created_at is None
    assert job.salary_min is None
    assert job.salary_max is None
    assert job.salary_currency is None
    assert job.employment_type is None
    assert job.category is None
    assert job.fingerprint is not None
