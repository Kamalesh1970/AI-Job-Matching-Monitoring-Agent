"""
Configuration loader for the AI Job-Matching & Monitoring Agent.
Loads environment variables using python-dotenv and validates required parameters.
"""

import math
import os
from dataclasses import dataclass, field
from typing import List, Optional
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

DEFAULT_PREFERRED_LOCATIONS: List[str] = [
    "Coimbatore",
    "Chennai",
    "Bangalore",
    "Bengaluru",
    "Hyderabad",
    "Pune",
    "Remote",
    "India",
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
    resume_path: str = "data/resume/base_resume.txt"
    embedding_model: str = "all-MiniLM-L6-v2"
    semantic_weight: float = 0.50
    skill_weight: float = 0.30
    rule_weight: float = 0.20
    min_match_score: float = 60.0
    preferred_locations: List[str] = field(
        default_factory=lambda: list(DEFAULT_PREFERRED_LOCATIONS)
    )
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_min_match_score: float = 70.0
    telegram_max_jobs_per_digest: int = 10
    telegram_enabled: bool = False
    send_empty_digest: bool = False
    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = 60
    heartbeat_timeout_minutes: int = 180
    run_on_startup: bool = True

    def __post_init__(self):
        """Validate matching weights sum up to 1.0."""
        total_weight = self.semantic_weight + self.skill_weight + self.rule_weight
        if not math.isclose(total_weight, 1.0, abs_tol=1e-4):
            raise ValueError(
                f"Matching weights must sum to 1.0 (got {total_weight:.4f}: "
                f"semantic={self.semantic_weight}, skill={self.skill_weight}, rule={self.rule_weight})"
            )


def load_config(env_path: Optional[str] = None, load_env_file: bool = True) -> Config:
    """
    Loads configuration from environment variables or .env file.

    Args:
        env_path: Optional path to a specific .env file.
        load_env_file: If True, loads variables from .env file into os.environ.
                      Set to False during unit tests to test environment variables in isolation.

    Raises:
        ValueError: If required credentials are missing or weights do not sum to 1.0.
    """
    if load_env_file:
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
    resume_path = os.getenv("RESUME_PATH", "data/resume/base_resume.txt").strip() or "data/resume/base_resume.txt"
    embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip() or "all-MiniLM-L6-v2"

    try:
        semantic_weight = float(os.getenv("SEMANTIC_WEIGHT", "0.50"))
    except ValueError:
        semantic_weight = 0.50

    try:
        skill_weight = float(os.getenv("SKILL_WEIGHT", "0.30"))
    except ValueError:
        skill_weight = 0.30

    try:
        rule_weight = float(os.getenv("RULE_WEIGHT", "0.20"))
    except ValueError:
        rule_weight = 0.20

    try:
        min_match_score = float(os.getenv("MIN_MATCH_SCORE", "60.0"))
    except ValueError:
        min_match_score = 60.0

    pref_loc_str = os.getenv("PREFERRED_LOCATIONS", "").strip()
    if pref_loc_str:
        preferred_locations = [loc.strip() for loc in pref_loc_str.split(",") if loc.strip()]
    else:
        preferred_locations = list(DEFAULT_PREFERRED_LOCATIONS)

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    try:
        telegram_min_match_score = float(os.getenv("TELEGRAM_MIN_MATCH_SCORE", "70.0"))
    except ValueError:
        telegram_min_match_score = 70.0

    try:
        telegram_max_jobs_per_digest = int(os.getenv("TELEGRAM_MAX_JOBS_PER_DIGEST", "10"))
    except ValueError:
        telegram_max_jobs_per_digest = 10

    tg_enabled_env = os.getenv("TELEGRAM_ENABLED", "true").strip().lower()
    telegram_enabled = (
        bool(telegram_bot_token and telegram_chat_id)
        and tg_enabled_env in ("true", "1", "yes")
    )

    send_empty_digest = os.getenv("SEND_EMPTY_DIGEST", "false").strip().lower() in ("true", "1", "yes")

    scheduler_enabled_env = os.getenv("SCHEDULER_ENABLED", "true").strip().lower()
    scheduler_enabled = scheduler_enabled_env in ("true", "1", "yes")

    try:
        scheduler_interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "60"))
    except ValueError:
        scheduler_interval_minutes = 60

    try:
        heartbeat_timeout_minutes = int(os.getenv("HEARTBEAT_TIMEOUT_MINUTES", "180"))
    except ValueError:
        heartbeat_timeout_minutes = 180

    run_on_startup_env = os.getenv("RUN_ON_STARTUP", "true").strip().lower()
    run_on_startup = run_on_startup_env in ("true", "1", "yes")

    return Config(
        adzuna_app_id=app_id,
        adzuna_app_key=app_key,
        adzuna_country=country,
        adzuna_results_per_page=results_per_page,
        adzuna_max_pages=max_pages,
        db_path=db_path,
        keywords=list(DEFAULT_SEARCH_KEYWORDS),
        resume_path=resume_path,
        embedding_model=embedding_model,
        semantic_weight=semantic_weight,
        skill_weight=skill_weight,
        rule_weight=rule_weight,
        min_match_score=min_match_score,
        preferred_locations=preferred_locations,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        telegram_min_match_score=telegram_min_match_score,
        telegram_max_jobs_per_digest=telegram_max_jobs_per_digest,
        telegram_enabled=telegram_enabled,
        send_empty_digest=send_empty_digest,
        scheduler_enabled=scheduler_enabled,
        scheduler_interval_minutes=scheduler_interval_minutes,
        heartbeat_timeout_minutes=heartbeat_timeout_minutes,
        run_on_startup=run_on_startup,
    )
