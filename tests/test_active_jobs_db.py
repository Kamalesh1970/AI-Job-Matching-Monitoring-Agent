"""
Unit tests for ActiveJobsDBJobSource (RapidAPI) client and normalization.
Uses mocked HTTP responses to prevent consuming RapidAPI quota.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app.config import Config
from app.db.database import get_connection, initialize_database, insert_job
from app.db.models import SourceStatus
from app.services.normalization import normalize_active_jobs_db_job
from app.sources.active_jobs_db import ActiveJobsDBJobSource


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        active_jobs_db_api_key="test_active_jobs_key",
        active_jobs_db_rapidapi_host="active-jobs-db.p.rapidapi.com",
        source_active_jobs_db_enabled=True,
    )


def test_active_jobs_db_configuration_and_is_enabled(mock_config):
    source = ActiveJobsDBJobSource(api_key="test_active_jobs_key")
    assert source.is_enabled(mock_config) is True

    disabled_config = Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        active_jobs_db_api_key="test_active_jobs_key",
        source_active_jobs_db_enabled=False,
    )
    assert source.is_enabled(disabled_config) is False


def test_active_jobs_db_missing_api_key():
    source = ActiveJobsDBJobSource(api_key="")
    no_key_config = Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        active_jobs_db_api_key="",
        source_active_jobs_db_enabled=True,
    )
    assert source.is_enabled(no_key_config) is False

    result = source.fetch_source_jobs(keywords=["AI Engineer"])
    assert result.status == SourceStatus.DISABLED
    assert result.total_fetched == 0


@patch("requests.get")
def test_active_jobs_db_authentication_headers_and_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "id": "act_101",
            "title": "Senior AI Architect",
            "company": "DeepMind Partner",
            "location": "Bangalore, India",
            "description": "Build agentic workflow systems",
            "url": "https://example.com/jobs/act_101",
            "posted_at": "2026-09-22T10:00:00Z",
            "employment_type": "Full-Time",
            "salary_min": 2000000,
            "salary_max": 3500000,
            "salary_currency": "INR",
        }
    ]
    mock_get.return_value = mock_response

    source = ActiveJobsDBJobSource(
        api_key="test_active_jobs_key",
        rapidapi_host="active-jobs-db.p.rapidapi.com",
    )
    raw_jobs = source.fetch_jobs_raw(keyword="Senior AI Architect", location="India", page=1)

    assert len(raw_jobs) == 1
    assert raw_jobs[0]["title"] == "Senior AI Architect"

    mock_get.assert_called_once()
    headers_used = mock_get.call_args[1]["headers"]
    assert headers_used["X-RapidAPI-Key"] == "test_active_jobs_key"
    assert headers_used["X-RapidAPI-Host"] == "active-jobs-db.p.rapidapi.com"


def test_active_jobs_db_normalization():
    raw_job = {
        "id": "act_202",
        "title": "Machine Learning Engineer",
        "company": "AI Scale Inc",
        "location": ["Chennai", "India"],
        "description": "Train and deploy PyTorch models",
        "url": "https://example.com/apply/act_202",
        "posted_at": "2026-09-21T14:00:00Z",
        "employment_type": ["Full-Time"],
        "min_salary": 1500000,
        "max_salary": 2200000,
        "currency": "INR",
    }
    job = normalize_active_jobs_db_job(raw_job)

    assert job.source == "Active Jobs DB"
    assert job.source_job_id == "act_202"
    assert job.title == "Machine Learning Engineer"
    assert job.company == "AI Scale Inc"
    assert job.location == "Chennai, India"
    assert job.description == "Train and deploy PyTorch models"
    assert job.url == "https://example.com/apply/act_202"
    assert job.created_at == "2026-09-21T14:00:00Z"
    assert job.employment_type == "Full-Time"
    assert job.salary_min == 1500000.0
    assert job.salary_max == 2200000.0
    assert job.salary_currency == "INR"
    assert job.fingerprint is not None
    assert len(job.fingerprint) == 64


def test_active_jobs_db_normalization_missing_optional_fields():
    raw_job = {
        "id": "act_303",
        "title": "Junior Data Scientist",
    }
    job = normalize_active_jobs_db_job(raw_job)

    assert job.source == "Active Jobs DB"
    assert job.source_job_id == "act_303"
    assert job.title == "Junior Data Scientist"
    assert job.company == ""
    assert job.location == ""
    assert job.description == ""
    assert job.url == ""
    assert job.salary_min is None
    assert job.fingerprint is not None


@patch("requests.get")
def test_active_jobs_db_malformed_json(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON string")
    mock_get.return_value = mock_response

    source = ActiveJobsDBJobSource(api_key="test_active_jobs_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_active_jobs_db_http_401_403(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
    mock_get.return_value = mock_response

    source = ActiveJobsDBJobSource(api_key="bad_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_active_jobs_db_http_429(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")
    mock_get.return_value = mock_response

    source = ActiveJobsDBJobSource(api_key="test_active_jobs_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_active_jobs_db_http_5xx(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("503 Service Unavailable")
    mock_get.return_value = mock_response

    source = ActiveJobsDBJobSource(api_key="test_active_jobs_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_active_jobs_db_timeout(mock_get):
    mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
    source = ActiveJobsDBJobSource(api_key="test_active_jobs_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_active_jobs_db_connection_failure(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("Failed to resolve host")
    source = ActiveJobsDBJobSource(api_key="test_active_jobs_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


def test_active_jobs_db_cross_source_deduplication_and_database_persistence():
    raw_job1 = {
        "id": "act_505",
        "title": "NLP Developer",
        "company": "Cognitive AI",
        "location": "Hyderabad",
    }
    raw_job2 = {
        "id": "act_506",
        "title": "NLP Developer",
        "company": "Cognitive AI",
        "location": "Hyderabad",
    }

    job1 = normalize_active_jobs_db_job(raw_job1)
    job2 = normalize_active_jobs_db_job(raw_job2)

    # Identical company, title, location MUST generate the exact same fingerprint
    assert job1.fingerprint == job2.fingerprint

    # Database persistence & Level 1 deduplication test
    conn = initialize_database(":memory:")
    inserted1 = insert_job(conn, job1)
    inserted2 = insert_job(conn, job1)  # Insert same job again

    assert inserted1 is True
    # Level 1 deduplication prevents duplicate insert of same (source, source_job_id)
    assert inserted2 is False
    conn.close()
