"""
Configuration loader for the AI Job-Matching & Monitoring Agent.
Loads environment variables using python-dotenv and validates required parameters.
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv


DEFAULT_SEARCH_KEYWORDS: List[str] = [
    "AI Engineer",
    "Machine Learning Engineer",
    "Artificial Intelligence",
    "Machine Learning",
    "Data Scientist",
    "Data Science",
    "Computer Vision",
    "NLP",
    "Deep Learning",
    "Python Developer",
]


@dataclass
class Config:
    """Application configuration container."""

    adzuna_app_id: str
    adzuna_app_key: str
    adzuna_country: str = "in"
    adzuna_results_per_page: int = 20
    adzuna_max_pages: int = 2
    db_path: str = "data/jobs.db"
    keywords: List[str] = field(default_factory=lambda: list(DEFAULT_SEARCH_KEYWORDS))


def load_config(env_path: str = None) -> Config:
    """
    Loads configuration from environment variables or .env file.

    Raises:
        ValueError: If required API credentials (ADZUNA_APP_ID or ADZUNA_APP_KEY) are missing.
    """
    if env_path:
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()

    missing_keys = []
    if not app_id:
        missing_keys.append("ADZUNA_APP_ID")
    if not app_key:
        missing_keys.append("ADZUNA_APP_KEY")

    if missing_keys:
        raise ValueError(
            f"Missing required configuration parameter(s): {', '.join(missing_keys)}. "
            "Please ensure they are set in your environment or .env file."
        )

    country = os.getenv("ADZUNA_COUNTRY", "in").strip() or "in"

    try:
        results_per_page = int(os.getenv("ADZUNA_RESULTS_PER_PAGE", "20"))
    except ValueError:
        results_per_page = 20

    try:
        max_pages = int(os.getenv("ADZUNA_MAX_PAGES", "2"))
    except ValueError:
        max_pages = 2

    db_path = os.getenv("DB_PATH", "data/jobs.db").strip() or "data/jobs.db"

    return Config(
        adzuna_app_id=app_id,
        adzuna_app_key=app_key,
        adzuna_country=country,
        adzuna_results_per_page=results_per_page,
        adzuna_max_pages=max_pages,
        db_path=db_path,
        keywords=list(DEFAULT_SEARCH_KEYWORDS),
    )
