"""
Tests for app/sources/adzuna.py Adzuna API client.
"""

from unittest import mock
import requests

from app.sources.adzuna import AdzunaJobSource


def test_adzuna_client_initialization():
    """Test client initialization and property getters."""
    client = AdzunaJobSource(app_id="dummy_id", app_key="dummy_key", country="in")
    assert client.name == "Adzuna"
    assert client.app_id == "dummy_id"
    assert client.app_key == "dummy_key"
    assert client.country == "in"


@mock.patch("app.sources.adzuna.requests.get")
def test_fetch_jobs_raw_success(mock_get):
    """Test successful API call returning raw job dictionaries."""
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "id": "12345",
                "title": "Machine Learning Engineer",
                "company": {"display_name": "Test Company"},
            }
        ]
    }
    mock_get.return_value = mock_response

    client = AdzunaJobSource(app_id="id123", app_key="key123", country="in")
    results = client.fetch_jobs_raw(keyword="Machine Learning", page=1, results_per_page=10)

    assert len(results) == 1
    assert results[0]["id"] == "12345"
    assert results[0]["title"] == "Machine Learning Engineer"

    mock_get.assert_called_once()
    called_url = mock_get.call_args[0][0]
    called_params = mock_get.call_args[1]["params"]

    assert "https://api.adzuna.com/v1/api/jobs/in/search/1" in called_url
    assert called_params["app_id"] == "id123"
    assert called_params["app_key"] == "key123"
    assert called_params["what"] == "Machine Learning"
    assert called_params["results_per_page"] == 10


@mock.patch("app.sources.adzuna.requests.get")
def test_fetch_jobs_raw_http_error(mock_get):
    """Test HTTP status error (e.g. 500) returns empty list and does not raise exception."""
    mock_response = mock.MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
    mock_get.return_value = mock_response

    client = AdzunaJobSource(app_id="id123", app_key="key123")
    results = client.fetch_jobs_raw(keyword="AI Engineer")

    assert results == []


@mock.patch("app.sources.adzuna.requests.get")
def test_fetch_jobs_raw_timeout(mock_get):
    """Test Timeout exception returns empty list without crashing."""
    mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

    client = AdzunaJobSource(app_id="id123", app_key="key123")
    results = client.fetch_jobs_raw(keyword="Data Science")

    assert results == []


@mock.patch("app.sources.adzuna.requests.get")
def test_fetch_jobs_raw_connection_error(mock_get):
    """Test ConnectionError exception returns empty list without crashing."""
    mock_get.side_effect = requests.exceptions.ConnectionError("Failed to establish connection")

    client = AdzunaJobSource(app_id="id123", app_key="key123")
    results = client.fetch_jobs_raw(keyword="Python Developer")

    assert results == []


@mock.patch("app.sources.adzuna.requests.get")
def test_fetch_jobs_raw_malformed_response(mock_get):
    """Test handling of unexpected or malformed API JSON responses."""
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    # Field 'results' missing or not a list
    mock_response.json.return_value = {"status": "ok", "results": "not a list"}
    mock_get.return_value = mock_response

    client = AdzunaJobSource(app_id="id123", app_key="key123")
    results = client.fetch_jobs_raw(keyword="NLP")

    assert results == []


@mock.patch("app.sources.adzuna.requests.get")
def test_fetch_jobs_for_keyword_pagination(mock_get):
    """Test fetch_jobs_for_keyword paginates up to max_pages and normalizes jobs."""
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "id": "job_1",
                "title": "AI Researcher",
                "company": {"display_name": "AI Lab"},
                "redirect_url": "https://example.com/job1",
            }
        ]
    }
    mock_get.return_value = mock_response

    client = AdzunaJobSource(app_id="id123", app_key="key123")
    jobs, success = client.fetch_jobs_for_keyword("AI Researcher", max_pages=2, results_per_page=10)

    assert success is True
    assert len(jobs) == 2  # 1 job per page for 2 pages
    assert mock_get.call_count == 2
