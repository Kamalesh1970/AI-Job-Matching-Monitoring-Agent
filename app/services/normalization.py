"""
Normalization service to transform raw API responses into internal Job models.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db.models import Job
from app.services.deduplication import generate_fingerprint


def strip_html(text: Optional[str]) -> str:
    """Removes HTML tags from string if present."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]*>", "", text)
    return clean.strip()


def normalize_salary(val: Any) -> Optional[float]:
    """Safely converts salary input to float or None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def normalize_adzuna_job(raw_job: Dict[str, Any], default_currency: str = "INR") -> Job:
    """
    Transforms a raw Adzuna API dictionary into a normalized Job dataclass.

    Args:
        raw_job: Raw dictionary from Adzuna API results list.
        default_currency: Fallback currency code if not provided.

    Returns:
        Job: Cleaned, structured Job instance.
    """
    if not isinstance(raw_job, dict):
        raw_job = {}

    # Source & ID
    source = "Adzuna"
    raw_id = raw_job.get("id")
    source_job_id = str(raw_id).strip() if raw_id is not None else ""

    # Title & Description
    title = strip_html(raw_job.get("title", ""))
    description = strip_html(raw_job.get("description", ""))

    # Company
    company_obj = raw_job.get("company")
    company = ""
    if isinstance(company_obj, dict):
        company = str(company_obj.get("display_name", "") or "").strip()
    elif isinstance(company_obj, str):
        company = company_obj.strip()

    # Location
    location_obj = raw_job.get("location")
    location = ""
    if isinstance(location_obj, dict):
        location = str(location_obj.get("display_name", "") or "").strip()
        if not location and "area" in location_obj and isinstance(location_obj["area"], list):
            location = ", ".join([str(a) for a in location_obj["area"] if a])
    elif isinstance(location_obj, str):
        location = location_obj.strip()

    # URL
    url = str(raw_job.get("redirect_url") or raw_job.get("url") or "").strip()

    # Created date
    created_at = raw_job.get("created")
    if created_at is not None:
        created_at = str(created_at).strip()

    # Salary
    salary_min = normalize_salary(raw_job.get("salary_min"))
    salary_max = normalize_salary(raw_job.get("salary_max"))
    salary_currency = raw_job.get("salary_currency")
    if not salary_currency and (salary_min is not None or salary_max is not None):
        salary_currency = default_currency
    elif salary_currency:
        salary_currency = str(salary_currency).strip().upper()

    # Employment Type / Contract
    contract_type = raw_job.get("contract_type") or raw_job.get("contract_time") or ""
    employment_type = str(contract_type).strip() if contract_type else None

    # Category
    category_obj = raw_job.get("category")
    category = None
    if isinstance(category_obj, dict):
        cat_label = category_obj.get("label")
        if cat_label:
            category = str(cat_label).strip()
    elif isinstance(category_obj, str) and category_obj.strip():
        category = category_obj.strip()

    # Timestamps
    fetched_at = datetime.now(timezone.utc).isoformat()

    # Fingerprint
    fingerprint = generate_fingerprint(company=company, title=title, location=location)

    return Job(
        source=source,
        source_job_id=source_job_id,
        title=title,
        company=company,
        location=location,
        description=description,
        url=url,
        created_at=created_at,
        fetched_at=fetched_at,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        employment_type=employment_type,
        category=category,
        fingerprint=fingerprint,
    )
