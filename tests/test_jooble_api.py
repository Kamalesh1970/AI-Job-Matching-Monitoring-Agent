"""
Unit tests for JoobleJobSource API client and normalization.
Uses mocked HTTP responses to prevent real API quota consumption.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app.config import Config
from app.db.models import SourceStatus
from app.services.normalization import normalize_jooble_job
from app.sources.jooble import JoobleJobSource


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        jooble_api_key="test_jooble_key",
        source_jooble_enabled=True,
    )


def test_jooble_is_enabled(mock_config):
    source = JoobleJobSource(api_key="test_jooble_key")
    assert source.is_enabled(mock_config) is True

    disabled_config = Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        jooble_api_key="test_jooble_key",
        source_jooble_enabled=False,
    )
    assert source.is_enabled(disabled_config) is False

    no_key_source = JoobleJobSource(api_key="")
    no_key_config = Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        jooble_api_key="",
    )
    assert no_key_source.is_enabled(no_key_config) is False


@patch("requests.post")
def test_jooble_fetch_jobs_raw_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jobs": [
            {
                "id": "101",
                "title": "ML Engineer",
                "company": "Tech Corp",
                "location": "Bangalore",
                "snippet": "Build ML models",
                "link": "https://jooble.org/job/101",
                "updated": "2026-09-20",
                "salary": "₹ 15,000,000 /year",
                "type": "Full-time",
            }
        ]
    }
    mock_post.return_value = mock_response

    source = JoobleJobSource(api_key="test_jooble_key")
    raw_jobs = source.fetch_jobs_raw(keyword="ML Engineer", location="Bangalore", page=1)

    assert len(raw_jobs) == 1
    assert raw_jobs[0]["title"] == "ML Engineer"
    mock_post.assert_called_once()
    url_called = mock_post.call_args[0][0]
    assert "test_jooble_key" in url_called


@patch("requests.post")
def test_jooble_fetch_jobs_raw_empty(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jobs": []}
    mock_post.return_value = mock_response

    source = JoobleJobSource(api_key="test_jooble_key")
    raw_jobs = source.fetch_jobs_raw(keyword="NonexistentJob", page=1)
    assert raw_jobs == []


@patch("requests.post")
def test_jooble_fetch_jobs_raw_malformed_json(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_post.return_value = mock_response

    source = JoobleJobSource(api_key="test_jooble_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.post")
def test_jooble_fetch_jobs_raw_timeout(mock_post):
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

    source = JoobleJobSource(api_key="test_jooble_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


@patch("requests.post")
def test_jooble_fetch_jobs_raw_http_error(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
    mock_post.return_value = mock_response

    source = JoobleJobSource(api_key="test_jooble_key")
    raw_jobs = source.fetch_jobs_raw(keyword="AI Engineer", page=1)
    assert raw_jobs == []


def test_jooble_normalization():
    raw_job = {
        "id": "j_99",
        "title": "<b>AI Agent Architect</b>",
        "company": "DeepMind Partner",
        "location": "Chennai",
        "snippet": "<p>Develop autonomous agents</p>",
        "link": "https://jooble.org/apply/99",
        "updated": "2026-09-21T10:00:00Z",
        "salary": "12,000,000",
        "type": "Full-time",
    }
    job = normalize_jooble_job(raw_job)

    assert job.source == "Jooble"
    assert job.source_job_id == "j_99"
    assert job.title == "AI Agent Architect"
    assert job.company == "DeepMind Partner"
    assert job.location == "Chennai"
    assert job.description == "Develop autonomous agents"
    assert job.url == "https://jooble.org/apply/99"
    assert job.created_at == "2026-09-21T10:00:00Z"
    assert job.salary_min == 12000000.0
    assert job.employment_type == "Full-time"
    assert job.fingerprint is not None
    assert len(job.fingerprint) == 64


@patch("requests.post")
def test_jooble_fetch_source_jobs_success(mock_post, mock_config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jobs": [
            {
                "id": "j_1",
                "title": "Generative AI Engineer",
                "company": "AI Labs",
                "location": "Hyderabad",
                "snippet": "Building LLM pipelines",
                "link": "https://jooble.org/1",
            }
        ]
    }
    mock_post.return_value = mock_response

    source = JoobleJobSource(api_key="test_jooble_key")
    result = source.fetch_source_jobs(keywords=["Generative AI Engineer"], config=mock_config)

    assert result.status == SourceStatus.SUCCESS
    assert result.total_fetched == 1
    assert len(result.jobs) == 1
    assert result.jobs[0].title == "Generative AI Engineer"


def test_jooble_missing_key_status():
    source = JoobleJobSource(api_key="")
    result = source.fetch_source_jobs(keywords=["AI Engineer"])
    assert result.status == SourceStatus.DISABLED
    assert result.total_fetched == 0
