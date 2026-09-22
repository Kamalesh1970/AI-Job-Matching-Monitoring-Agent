"""
Unit tests for JSearchJobSource (RapidAPI) client and normalization.
Uses mocked HTTP responses to prevent consuming RapidAPI quota.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app.config import Config
from app.db.models import SourceStatus
from app.services.normalization import normalize_jsearch_job
from app.sources.jsearch import JSearchJobSource


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        jsearch_api_key="test_jsearch_key",
        jsearch_rapidapi_host="jsearch.p.rapidapi.com",
        source_jsearch_enabled=True,
    )


def test_jsearch_is_enabled(mock_config):
    source = JSearchJobSource(api_key="test_jsearch_key")
    assert source.is_enabled(mock_config) is True

    disabled_config = Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        jsearch_api_key="test_jsearch_key",
        source_jsearch_enabled=False,
    )
    assert source.is_enabled(disabled_config) is False

    no_key_source = JSearchJobSource(api_key="")
    no_key_config = Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        jsearch_api_key="",
    )
    assert no_key_source.is_enabled(no_key_config) is False


@patch("requests.get")
def test_jsearch_fetch_jobs_raw_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OK",
        "data": [
            {
                "job_id": "js_1001",
                "job_title": "Machine Learning Engineer",
                "employer_name": "Google",
                "job_city": "Bangalore",
                "job_state": "Karnataka",
                "job_country": "IN",
                "job_is_remote": False,
                "job_description": "Work on Gemini AI systems",
                "job_apply_link": "https://careers.google.com/jobs/js_1001",
                "job_posted_at_datetime_utc": "2026-09-22T00:00:00.000Z",
                "job_employment_type": "FULLTIME",
                "job_min_salary": 1800000,
                "job_max_salary": 2500000,
                "job_salary_currency": "INR",
            }
        ],
    }
    mock_get.return_value = mock_response

    source = JSearchJobSource(api_key="test_jsearch_key", rapidapi_host="jsearch.p.rapidapi.com")
    raw_jobs = source.fetch_jobs_raw(keyword="Machine Learning Engineer", location="Bangalore", page=1)

    assert len(raw_jobs) == 1
    assert raw_jobs[0]["job_title"] == "Machine Learning Engineer"

    # Verify RapidAPI headers were passed
    mock_get.assert_called_once()
    headers_used = mock_get.call_args[1]["headers"]
    assert headers_used["X-RapidAPI-Key"] == "test_jsearch_key"
    assert headers_used["X-RapidAPI-Host"] == "jsearch.p.rapidapi.com"


@patch("requests.get")
def test_jsearch_fetch_jobs_raw_empty(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "OK", "data": []}
    mock_get.return_value = mock_response

    source = JSearchJobSource(api_key="test_jsearch_key")
    raw_jobs = source.fetch_jobs_raw(keyword="NonexistentJob", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_jsearch_fetch_jobs_raw_malformed_json(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value = mock_response

    source = JSearchJobSource(api_key="test_jsearch_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_jsearch_fetch_jobs_raw_timeout(mock_get):
    mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

    source = JSearchJobSource(api_key="test_jsearch_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_jsearch_fetch_jobs_raw_http_429(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")
    mock_get.return_value = mock_response

    source = JSearchJobSource(api_key="test_jsearch_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


def test_jsearch_normalization():
    raw_job = {
        "job_id": "js_555",
        "job_title": "NLP Engineer",
        "employer_name": "AI Solutions Ltd",
        "job_city": "Coimbatore",
        "job_state": "Tamil Nadu",
        "job_country": "IN",
        "job_is_remote": True,
        "job_description": "<p>NLP and LLM development</p>",
        "job_apply_link": "https://example.com/apply/555",
        "job_posted_at_datetime_utc": "2026-09-20T12:00:00Z",
        "job_employment_type": "CONTRACT",
        "job_min_salary": 50000,
        "job_max_salary": 80000,
        "job_salary_currency": "USD",
    }
    job = normalize_jsearch_job(raw_job)

    assert job.source == "JSearch"
    assert job.source_job_id == "js_555"
    assert job.title == "NLP Engineer"
    assert job.company == "AI Solutions Ltd"
    assert "Coimbatore, Tamil Nadu, IN (Remote)" == job.location
    assert job.description == "NLP and LLM development"
    assert job.url == "https://example.com/apply/555"
    assert job.created_at == "2026-09-20T12:00:00Z"
    assert job.employment_type == "CONTRACT"
    assert job.salary_min == 50000.0
    assert job.salary_max == 80000.0
    assert job.salary_currency == "USD"
    assert job.fingerprint is not None
    assert len(job.fingerprint) == 64


def test_jsearch_normalization_remote_with_location():
    raw_job = {
        "job_id": "js_101",
        "job_title": "AI Developer",
        "employer_name": "Tech Corp",
        "job_city": "Bangalore",
        "job_country": "IN",
        "job_is_remote": True,
    }
    job = normalize_jsearch_job(raw_job)
    assert job.location == "Bangalore, IN (Remote)"


def test_jsearch_normalization_remote_without_location():
    raw_job = {
        "job_id": "js_102",
        "job_title": "Data Scientist",
        "employer_name": "Global AI",
        "job_is_remote": True,
    }
    job = normalize_jsearch_job(raw_job)
    assert job.location == "Remote"


def test_jsearch_normalization_non_remote():
    raw_job = {
        "job_id": "js_103",
        "job_title": "MLOps Engineer",
        "employer_name": "InOffice Tech",
        "job_city": "Chennai",
        "job_country": "IN",
        "job_is_remote": False,
    }
    job = normalize_jsearch_job(raw_job)
    assert job.location == "Chennai, IN"
    assert "Remote" not in job.location


def test_jsearch_normalization_missing_remote_metadata():
    raw_job = {
        "job_id": "js_104",
        "job_title": "Prompt Engineer",
        "employer_name": "Prompt Co",
        "job_city": "Hyderabad",
    }
    job = normalize_jsearch_job(raw_job)
    assert job.location == "Hyderabad"
    assert "Remote" not in job.location


@patch("requests.get")
def test_jsearch_fetch_source_jobs_success(mock_get, mock_config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "job_id": "js_1",
                "job_title": "AI Security Engineer",
                "employer_name": "Cyber AI",
                "job_city": "Chennai",
                "job_description": "AI Threat Detection",
                "job_apply_link": "https://example.com/sec/1",
            }
        ]
    }
    mock_get.return_value = mock_response

    source = JSearchJobSource(api_key="test_jsearch_key")
    result = source.fetch_source_jobs(keywords=["AI Security Engineer"], config=mock_config)

    assert result.status == SourceStatus.SUCCESS
    assert result.total_fetched == 1
    assert len(result.jobs) == 1
    assert result.jobs[0].title == "AI Security Engineer"


def test_jsearch_missing_key_status():
    source = JSearchJobSource(api_key="")
    result = source.fetch_source_jobs(keywords=["AI Engineer"])
    assert result.status == SourceStatus.DISABLED
    assert result.total_fetched == 0
