"""
Unit tests for SerpApi Google Jobs client and normalization.
Uses mocked HTTP responses to prevent consuming SerpApi search credits.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app.config import Config
from app.db.models import SourceStatus
from app.services.normalization import normalize_serpapi_job
from app.sources.serpapi import SerpApiJobSource


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        serpapi_key="test_serpapi_key",
        source_serpapi_enabled=True,
    )


def test_serpapi_is_enabled(mock_config):
    source = SerpApiJobSource(api_key="test_serpapi_key")
    assert source.is_enabled(mock_config) is True

    disabled_config = Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        serpapi_key="test_serpapi_key",
        source_serpapi_enabled=False,
    )
    assert source.is_enabled(disabled_config) is False

    no_key_source = SerpApiJobSource(api_key="")
    no_key_config = Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        serpapi_key="",
    )
    assert no_key_source.is_enabled(no_key_config) is False


@patch("requests.get")
def test_serpapi_fetch_jobs_raw_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "search_metadata": {"status": "Success"},
        "jobs_results": [
            {
                "job_id": "serp_888",
                "title": "Computer Vision Engineer",
                "company_name": "Vision AI Inc",
                "location": "Pune, Maharashtra, India",
                "description": "Develop OpenCV and PyTorch models",
                "apply_options": [
                    {"title": "Apply on LinkedIn", "link": "https://linkedin.com/jobs/view/888"},
                    {"title": "Apply on Company Site", "link": "https://visionai.com/careers/888"},
                ],
                "detected_extensions": {
                    "posted_at": "2 days ago",
                    "schedule_type": "Full-time",
                    "salary": "₹1,200,000 - ₹1,800,000 a year",
                },
            }
        ],
    }
    mock_get.return_value = mock_response

    source = SerpApiJobSource(api_key="test_serpapi_key")
    raw_jobs = source.fetch_jobs_raw(keyword="Computer Vision Engineer", location="India", page=1)

    assert len(raw_jobs) == 1
    assert raw_jobs[0]["title"] == "Computer Vision Engineer"

    # Verify query params
    mock_get.assert_called_once()
    params_used = mock_get.call_args[1]["params"]
    assert params_used["engine"] == "google_jobs"
    assert params_used["q"] == "Computer Vision Engineer"
    assert params_used["api_key"] == "test_serpapi_key"


@patch("requests.get")
def test_serpapi_fetch_jobs_raw_empty(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jobs_results": []}
    mock_get.return_value = mock_response

    source = SerpApiJobSource(api_key="test_serpapi_key")
    raw_jobs = source.fetch_jobs_raw(keyword="NonexistentJob", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_serpapi_fetch_jobs_raw_api_error_payload(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "Invalid API Key"}
    mock_get.return_value = mock_response

    source = SerpApiJobSource(api_key="bad_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_serpapi_fetch_jobs_raw_timeout(mock_get):
    mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

    source = SerpApiJobSource(api_key="test_serpapi_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.get")
def test_serpapi_fetch_jobs_raw_http_error(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Forbidden")
    mock_get.return_value = mock_response

    source = SerpApiJobSource(api_key="test_serpapi_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


def test_serpapi_normalization():
    raw_job = {
        "job_id": "serp_999",
        "title": "Generative AI Architect",
        "company_name": "GenAI Tech",
        "location": "Gurgaon, India",
        "description": "Architect LLM and RAG solutions",
        "apply_options": [
            {"title": "Apply via Indeed", "link": "https://indeed.com/viewjob?jk=999"}
        ],
        "detected_extensions": {
            "posted_at": "1 day ago",
            "schedule_type": "Full-time",
            "salary": "₹2,500,000 a year",
        },
    }
    job = normalize_serpapi_job(raw_job)

    assert job.source == "SerpApi"
    assert job.source_job_id == "serp_999"
    assert job.title == "Generative AI Architect"
    assert job.company == "GenAI Tech"
    assert job.location == "Gurgaon, India"
    assert job.description == "Architect LLM and RAG solutions"
    assert job.url == "https://indeed.com/viewjob?jk=999"
    assert job.created_at == "1 day ago"
    assert job.employment_type == "Full-time"
    assert job.salary_min == 2500000.0
    assert job.fingerprint is not None
    assert len(job.fingerprint) == 64


@patch("requests.get")
def test_serpapi_fetch_source_jobs_success(mock_get, mock_config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jobs_results": [
            {
                "job_id": "serp_1",
                "title": "MLOps Engineer",
                "company_name": "Cloud AI",
                "location": "Noida",
                "description": "Deploy AI pipelines",
                "share_link": "https://google.com/jobs/1",
            }
        ]
    }
    mock_get.return_value = mock_response

    source = SerpApiJobSource(api_key="test_serpapi_key")
    result = source.fetch_source_jobs(keywords=["MLOps Engineer"], config=mock_config)

    assert result.status == SourceStatus.SUCCESS
    assert result.total_fetched == 1
    assert len(result.jobs) == 1
    assert result.jobs[0].title == "MLOps Engineer"


def test_serpapi_missing_key_status():
    source = SerpApiJobSource(api_key="")
    result = source.fetch_source_jobs(keywords=["AI Engineer"])
    assert result.status == SourceStatus.DISABLED
    assert result.total_fetched == 0
