"""
Tests for Phase 9.1 Job Source Integrations (Arbeitnow, RemoteOK, Jobicy, Himalayas, Jooble).
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app.config import Config
from app.db.models import Job, SourceStatus
from app.services.deduplication import generate_fingerprint
from app.services.normalization import (
    normalize_arbeitnow_job,
    normalize_himalayas_job,
    normalize_jobicy_job,
    normalize_jooble_job,
    normalize_remoteok_job,
)
from app.sources.arbeitnow import ArbeitnowJobSource
from app.sources.himalayas import HimalayasJobSource
from app.sources.jobicy import JobicyJobSource
from app.sources.jooble import JoobleJobSource
from app.sources.registry import JobSourceRegistry, create_default_source_registry
from app.sources.remoteok import RemoteOKJobSource


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        source_arbeitnow_enabled=True,
        source_remoteok_enabled=True,
        source_jobicy_enabled=True,
        source_himalayas_enabled=True,
        source_jooble_enabled=True,
        jooble_api_key="test_jooble_key",
    )


# ============================================================================
# ARBEITNOW SOURCE TESTS
# ============================================================================

def test_arbeitnow_properties():
    source = ArbeitnowJobSource()
    assert source.name == "Arbeitnow"
    assert source.source_identifier == "arbeitnow"
    assert source.source_type == "api"


def test_arbeitnow_is_enabled(mock_config):
    source = ArbeitnowJobSource()
    assert source.is_enabled(mock_config) is True

    mock_config.source_arbeitnow_enabled = False
    assert source.is_enabled(mock_config) is False


@patch("requests.get")
def test_arbeitnow_fetch_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [
            {
                "slug": "ai-engineer-1",
                "company_name": "Tech Corp",
                "title": "AI Engineer",
                "description": "<p>Develop ML models</p>",
                "remote": True,
                "url": "https://www.arbeitnow.com/view/ai-engineer-1",
                "location": "Berlin",
                "created_at": 1672531199,
                "job_types": ["Full Time"],
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    source = ArbeitnowJobSource()
    res = source.fetch_source_jobs()
    assert res.status == SourceStatus.SUCCESS
    assert res.total_fetched == 1

    job = res.jobs[0]
    assert job.source == "Arbeitnow"
    assert job.source_job_id == "ai-engineer-1"
    assert job.company == "Tech Corp"
    assert job.title == "AI Engineer"
    assert "Develop ML models" in job.description
    assert job.url == "https://www.arbeitnow.com/view/ai-engineer-1"
    assert job.employment_type == "Full Time"
    assert job.fingerprint is not None


@patch("requests.get")
def test_arbeitnow_fetch_empty_and_malformed(mock_get):
    source = ArbeitnowJobSource()

    # Empty data
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_get.return_value = mock_resp
    assert len(source.fetch_jobs_raw()) == 0

    # Malformed data (not list)
    mock_resp.json.return_value = {"data": "not a list"}
    assert len(source.fetch_jobs_raw()) == 0

    # Malformed JSON (not dict)
    mock_resp.json.return_value = "invalid json"
    assert len(source.fetch_jobs_raw()) == 0


@patch("requests.get")
def test_arbeitnow_fetch_error_handling(mock_get):
    source = ArbeitnowJobSource()

    # Timeout
    mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
    assert source.fetch_jobs_raw() == []

    # HTTP Error
    mock_get.side_effect = requests.exceptions.HTTPError("500 Server Error")
    assert source.fetch_jobs_raw() == []


# ============================================================================
# REMOTEOK SOURCE TESTS
# ============================================================================

def test_remoteok_properties():
    source = RemoteOKJobSource()
    assert source.name == "RemoteOK"
    assert source.source_identifier == "remoteok"
    assert source.source_type == "api"


def test_remoteok_is_enabled(mock_config):
    source = RemoteOKJobSource()
    assert source.is_enabled(mock_config) is True

    mock_config.source_remoteok_enabled = False
    assert source.is_enabled(mock_config) is False


@patch("requests.get")
def test_remoteok_fetch_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {"legal": "Notice text"},  # Index 0 disclaimer
        {
            "id": "998877",
            "slug": "remote-ml-engineer-998877",
            "company": "RemoteTech",
            "position": "Machine Learning Engineer",
            "location": "Worldwide",
            "description": "Build RL algorithms",
            "url": "https://remoteok.com/remote-jobs/998877",
            "date": "2023-01-01T00:00:00+00:00",
            "salary_min": 120000,
            "salary_max": 180000,
            "tags": ["python", "machine learning"],
        },
    ]
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    source = RemoteOKJobSource()
    res = source.fetch_source_jobs()
    assert res.status == SourceStatus.SUCCESS
    assert res.total_fetched == 1

    job = res.jobs[0]
    assert job.source == "RemoteOK"
    assert job.source_job_id == "998877"
    assert job.company == "RemoteTech"
    assert job.title == "Machine Learning Engineer"
    assert job.salary_min == 120000.0
    assert job.salary_max == 180000.0
    assert job.salary_currency == "USD"
    assert "python" in job.category


@patch("requests.get")
def test_remoteok_fetch_error_handling(mock_get):
    source = RemoteOKJobSource()

    mock_get.side_effect = requests.exceptions.RequestException("Network issue")
    assert source.fetch_jobs_raw() == []


# ============================================================================
# JOBICY SOURCE TESTS
# ============================================================================

def test_jobicy_properties():
    source = JobicyJobSource()
    assert source.name == "Jobicy"
    assert source.source_identifier == "jobicy"
    assert source.source_type == "api"


def test_jobicy_is_enabled(mock_config):
    source = JobicyJobSource()
    assert source.is_enabled(mock_config) is True

    mock_config.source_jobicy_enabled = False
    assert source.is_enabled(mock_config) is False


@patch("requests.get")
def test_jobicy_fetch_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "success",
        "jobs": [
            {
                "id": 54321,
                "url": "https://jobicy.com/jobs/54321",
                "jobTitle": "Data Scientist",
                "companyName": "AI Analytics",
                "jobType": ["full-time"],
                "jobGeo": "India",
                "jobDescription": "NLP and LLM evaluation",
                "pubDate": "2023-05-10 12:00:00",
                "annualSalaryMin": "80000",
                "annualSalaryMax": "110000",
                "salaryCurrency": "USD",
            }
        ],
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    source = JobicyJobSource()
    res = source.fetch_source_jobs()
    assert res.status == SourceStatus.SUCCESS
    assert res.total_fetched == 1

    job = res.jobs[0]
    assert job.source == "Jobicy"
    assert job.source_job_id == "54321"
    assert job.company == "AI Analytics"
    assert job.title == "Data Scientist"
    assert job.location == "India"
    assert job.employment_type == "full-time"


# ============================================================================
# HIMALAYAS SOURCE TESTS
# ============================================================================

def test_himalayas_properties():
    source = HimalayasJobSource()
    assert source.name == "Himalayas"
    assert source.source_identifier == "himalayas"
    assert source.source_type == "api"


def test_himalayas_is_enabled(mock_config):
    source = HimalayasJobSource()
    assert source.is_enabled(mock_config) is True

    mock_config.source_himalayas_enabled = False
    assert source.is_enabled(mock_config) is False


@patch("requests.get")
def test_himalayas_fetch_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "jobs": [
            {
                "guid": "him-101",
                "title": "Computer Vision Specialist",
                "companyName": "Visionary Labs",
                "locationRestrictions": ["Worldwide"],
                "description": "PyTorch, OpenCV models",
                "url": "https://himalayas.app/jobs/him-101",
                "pubDate": 1672531199,
                "type": ["Full-time"],
                "category": ["Software Engineering"],
                "minSalary": 100000,
                "maxSalary": 140000,
                "currency": "USD",
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    source = HimalayasJobSource()
    res = source.fetch_source_jobs()
    assert res.status == SourceStatus.SUCCESS
    assert res.total_fetched == 1

    job = res.jobs[0]
    assert job.source == "Himalayas"
    assert job.source_job_id == "him-101"
    assert job.company == "Visionary Labs"
    assert job.title == "Computer Vision Specialist"
    assert job.salary_min == 100000.0


# ============================================================================
# JOOBLE SOURCE TESTS
# ============================================================================

def test_jooble_properties():
    source = JoobleJobSource(api_key="test_key")
    assert source.name == "Jooble"
    assert source.source_identifier == "jooble"
    assert source.source_type == "api"


def test_jooble_is_enabled_requires_key(mock_config):
    # Without key
    source_no_key = JoobleJobSource(api_key="")
    assert source_no_key.is_enabled(mock_config) is True  # mock_config has jooble_api_key

    mock_config.jooble_api_key = ""
    assert source_no_key.is_enabled(mock_config) is False

    mock_config.source_jooble_enabled = False
    assert source_no_key.is_enabled(mock_config) is False


@patch("requests.post")
def test_jooble_fetch_success(mock_get_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "totalCount": 1,
        "jobs": [
            {
                "id": "-88776655",
                "title": "Python Developer",
                "company": "Web Solutions",
                "location": "Chennai",
                "snippet": "Django, FastAPI backend development",
                "type": "Full-time",
                "salary": "₹6,00,000 - ₹10,00,000",
                "link": "https://jooble.org/desc/-88776655",
                "updated": "2023-06-01",
            }
        ],
    }
    mock_resp.raise_for_status.return_value = None
    mock_get_post.return_value = mock_resp

    source = JoobleJobSource(api_key="valid_key")
    res = source.fetch_source_jobs(keywords=["Python Developer"])
    assert res.status == SourceStatus.SUCCESS
    assert res.total_fetched == 1

    job = res.jobs[0]
    assert job.source == "Jooble"
    assert job.source_job_id == "-88776655"
    assert job.company == "Web Solutions"
    assert job.salary_min == 600000.0
    assert job.salary_max == 1000000.0


def test_jooble_fetch_without_key_returns_disabled():
    source = JoobleJobSource(api_key="")
    res = source.fetch_source_jobs()
    assert res.status == SourceStatus.DISABLED
    assert res.total_fetched == 0


# ============================================================================
# REGISTRY & DEDUPLICATION INTEGRATION TESTS
# ============================================================================

def test_registry_integration(mock_config):
    registry = create_default_source_registry(mock_config)
    sources = registry.list_sources()
    source_ids = [s.source_identifier for s in sources]

    assert "adzuna" in source_ids
    assert "internshala" in source_ids
    assert "arbeitnow" in source_ids
    assert "remoteok" in source_ids
    assert "jobicy" in source_ids
    assert "himalayas" in source_ids
    assert "jooble" in source_ids

    enabled_sources = registry.list_enabled_sources(mock_config)
    enabled_ids = [s.source_identifier for s in enabled_sources]
    assert "arbeitnow" in enabled_ids
    assert "remoteok" in enabled_ids

    # Disable Arbeitnow dynamically
    registry.disable_source("arbeitnow")
    enabled_ids_after = [s.source_identifier for s in registry.list_enabled_sources(mock_config)]
    assert "arbeitnow" not in enabled_ids_after


def test_cross_source_deduplication():
    from app.db.database import initialize_database, insert_job, get_job_by_source_id
    from app.services.digest_service import DigestService
    from app.db.models import MatchResult

    conn = initialize_database(":memory:")

    raw_arbeitnow = {
        "slug": "ml-engineer-1",
        "company_name": "Acme Global",
        "title": "Senior ML Engineer",
        "location": "Remote",
        "description": "Build scale models",
    }
    raw_remoteok = {
        "id": "remote-ml-99",
        "company": "Acme Global",
        "position": "Senior ML Engineer",
        "location": "Remote",
        "description": "Build scale models",
    }

    job1 = normalize_arbeitnow_job(raw_arbeitnow)
    job2 = normalize_remoteok_job(raw_remoteok)

    # 1. Verify source provenance is preserved
    assert job1.source == "Arbeitnow"
    assert job1.source_job_id == "ml-engineer-1"
    assert job2.source == "RemoteOK"
    assert job2.source_job_id == "remote-ml-99"

    # 2. Verify Level 2 SHA-256 fingerprint matches across sources for identical position
    assert job1.fingerprint is not None
    assert job1.fingerprint == job2.fingerprint

    # 3. Both jobs persist into database maintaining source isolation
    assert insert_job(conn, job1) is True
    assert insert_job(conn, job2) is True

    stored1 = get_job_by_source_id(conn, "Arbeitnow", "ml-engineer-1")
    stored2 = get_job_by_source_id(conn, "RemoteOK", "remote-ml-99")
    assert stored1 is not None and stored2 is not None
    assert stored1.id != stored2.id

    # 4. Cross-source duplicate detection in DigestService filters duplicate candidate by fingerprint
    digest_service = DigestService(min_score=70.0, max_jobs=10)
    jobs_map = {stored1.id: stored1, stored2.id: stored2}
    matches = [
        MatchResult(job_id=stored1.id, source_job_id=stored1.source_job_id, title=stored1.title, final_score=85.0),
        MatchResult(job_id=stored2.id, source_job_id=stored2.source_job_id, title=stored2.title, final_score=85.0),
    ]

    filtered_matches = digest_service.filter_and_sort_matches(matches, jobs_map=jobs_map)
    assert len(filtered_matches) == 1
    assert filtered_matches[0].job_id == stored1.id

    conn.close()
