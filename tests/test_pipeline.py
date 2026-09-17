"""
Tests for app/main.py pipeline execution and error isolation.
"""

from unittest import mock
import pytest

from app.config import Config
from app.db.database import initialize_database, get_recent_jobs
from app.main import run_pipeline


@pytest.fixture
def mock_config(tmp_path):
    """Fixture to create a temporary test Config with a temp SQLite DB path."""
    db_file = str(tmp_path / "test_jobs.db")
    return Config(
        adzuna_app_id="test_app_id",
        adzuna_app_key="test_app_key",
        adzuna_country="in",
        adzuna_results_per_page=10,
        adzuna_max_pages=1,
        db_path=db_file,
        keywords=["AI Engineer", "Broken Keyword", "Data Scientist"],
    )


@mock.patch("app.sources.adzuna.requests.get")
def test_pipeline_error_isolation(mock_get, mock_config):
    """
    Test that an API error or timeout on one keyword ('Broken Keyword') does NOT crash
    the pipeline and allows subsequent keywords ('Data Scientist') to process successfully.
    """

    def side_effect_func(url, params, timeout=15):
        kw = params.get("what")
        mock_resp = mock.MagicMock()
        if kw == "AI Engineer":
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "results": [
                    {
                        "id": "ai_1",
                        "title": "AI Engineer",
                        "company": {"display_name": "AI Corp"},
                    }
                ]
            }
            return mock_resp
        elif kw == "Broken Keyword":
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
            return mock_resp
        elif kw == "Data Scientist":
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "results": [
                    {
                        "id": "ds_1",
                        "title": "Data Scientist",
                        "company": {"display_name": "Data Corp"},
                    }
                ]
            }
            return mock_resp
        return mock_resp

    mock_get.side_effect = side_effect_func

    # Run pipeline with mocked config
    run_pipeline(mock_config)

    # Verify database contains jobs from both successful keywords
    conn = initialize_database(mock_config.db_path)
    jobs = get_recent_jobs(conn)
    conn.close()

    assert len(jobs) == 2
    job_ids = {j.source_job_id for j in jobs}
    assert "ai_1" in job_ids
    assert "ds_1" in job_ids


@mock.patch("app.sources.adzuna.requests.get")
def test_pipeline_deduplicates_same_job_across_multiple_keywords(mock_get, mock_config):
    """
    Test that when the exact same Adzuna job appears under multiple search keywords,
    only 1 database row is created.
    """

    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "id": "shared_job_1",
                "title": "AI ML Engineer",
                "company": {"display_name": "Omni Tech"},
            }
        ]
    }
    mock_get.return_value = mock_resp

    run_pipeline(mock_config)

    conn = initialize_database(mock_config.db_path)
    jobs = get_recent_jobs(conn)
    conn.close()

    assert len(jobs) == 1
    assert jobs[0].source_job_id == "shared_job_1"
