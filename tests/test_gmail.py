"""
Comprehensive offline unit and integration tests for Phase 6 Gmail API client,
LinkedIn and Indeed HTML email alert parsers, source wrappers, failure isolation, and CLI options.
No live external API or internet requests are made during test execution.
"""

import base64
import json
import os
from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.database import initialize_database
from app.db.models import Job, SourceStatus
from app.services.matching_service import MatchingService
from app.services.pipeline_service import PipelineService, PipelineStatus
from app.sources.gmail.email_parser import (
    IndeedEmailParser,
    LinkedInEmailParser,
    normalize_indeed_url,
    normalize_linkedin_url,
)
from app.sources.gmail.gmail_client import GmailAPIClient
from app.sources.gmail.gmail_source import IndeedAlertEmailSource, LinkedInAlertEmailSource
from app.sources.gmail.models import ParsedEmailData


LINKEDIN_EMAIL_HTML = """
<!DOCTYPE html>
<html>
<body>
<table class="job-card">
  <tr>
    <td>
      <a href="https://www.linkedin.com/comm/jobs/view/3912345678/?trackingId=abc123">Senior AI Engineer</a>
      <a href="https://www.linkedin.com/company/ai-alpha-labs/">AI Alpha Labs</a>
      <span class="location">Bangalore, India</span>
      <p class="snippet">Work on large language models and PyTorch pipelines.</p>
    </td>
  </tr>
  <tr>
    <td>
      <a href="https://www.linkedin.com/jobs/view/3987654321">Data Scientist</a>
      <div class="company-name">Data Dynamics</div>
      <div class="location">Remote</div>
      <div class="job-card-snippet">Build machine learning models and SQL pipelines.</div>
    </td>
  </tr>
</table>
</body>
</html>
"""

LINKEDIN_MISSING_FIELDS_HTML = """
<!DOCTYPE html>
<html>
<body>
<div>
    <a href="https://www.linkedin.com/comm/jobs/view/3955555555">Computer Vision Researcher</a>
    <!-- Missing company and location elements -->
</div>
</body>
</html>
"""

INDEED_EMAIL_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="job-box">
    <a href="https://www.indeed.com/rc/clk?jk=1234567890abcdef&from=ja">Machine Learning Developer</a>
    <span class="companyName">Beta Tech Systems</span>
    <span class="companyLocation">Chennai, Tamil Nadu</span>
    <div class="jobSnippet">Develop deep learning algorithms using TensorFlow.</div>
</div>

<div class="job-box">
    <a href="https://www.indeed.com/viewjob?jk=fedcba0987654321">Python Developer</a>
    <div class="company">PyCorp</div>
    <div class="location">Bangalore</div>
    <div class="snippet">Build scalable FastAPI and Flask microservices.</div>
</div>
</body>
</html>
"""

INDEED_MISSING_FIELDS_HTML = """
<!DOCTYPE html>
<html>
<body>
<div>
    <a href="https://www.indeed.com/viewjob?jk=9998887776665554">NLP Engineer</a>
</div>
</body>
</html>
"""


@pytest.fixture
def memory_db():
    """Provides an in-memory SQLite database connection."""
    conn = initialize_database(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def test_config():
    """Provides Config container with Gmail enabled for testing."""
    return Config(
        adzuna_app_id="app_id",
        adzuna_app_key="app_key",
        keywords=["AI Engineer"],
        internshala_enabled=False,
        gmail_enabled=True,
        gmail_credentials_path="test_credentials.json",
        gmail_token_path="test_token.json",
        telegram_bot_token="123:ABC",
        telegram_chat_id="456",
        telegram_enabled=False,
    )


# ---------------------------------------------------------------------
# 1. URL Normalization & ID Extraction Tests
# ---------------------------------------------------------------------


def test_normalize_linkedin_url():
    """Test LinkedIn URL cleaning and stable job ID extraction."""
    url, job_id = normalize_linkedin_url("https://www.linkedin.com/comm/jobs/view/3912345678/?trackingId=xyz")
    assert url == "https://www.linkedin.com/jobs/view/3912345678"
    assert job_id == "li_3912345678"

    url2, job_id2 = normalize_linkedin_url("https://www.linkedin.com/jobs/view/3987654321")
    assert url2 == "https://www.linkedin.com/jobs/view/3987654321"
    assert job_id2 == "li_3987654321"

    url_empty, id_empty = normalize_linkedin_url("")
    assert url_empty == ""
    assert id_empty == ""


def test_normalize_indeed_url():
    """Test Indeed URL cleaning and stable jk job ID extraction."""
    url, job_id = normalize_indeed_url("https://www.indeed.com/rc/clk?jk=1234567890abcdef&from=ja")
    assert url == "https://www.indeed.com/viewjob?jk=1234567890abcdef"
    assert job_id == "ind_1234567890abcdef"

    url2, job_id2 = normalize_indeed_url("https://www.indeed.com/viewjob?jk=fedcba0987654321")
    assert url2 == "https://www.indeed.com/viewjob?jk=fedcba0987654321"
    assert job_id2 == "ind_fedcba0987654321"

    url_empty, id_empty = normalize_indeed_url("")
    assert url_empty == ""
    assert id_empty == ""


# ---------------------------------------------------------------------
# 2. LinkedIn Email Parser Tests
# ---------------------------------------------------------------------


def test_linkedin_email_parser_valid_html():
    """Test parsing standard LinkedIn job alert HTML email fixture."""
    email_data = ParsedEmailData(
        message_id="msg_1",
        received_at="2026-09-18T10:00:00Z",
        subject="8 new jobs for 'AI Engineer'",
        sender="jobalerts-noreply@linkedin.com",
        html_content=LINKEDIN_EMAIL_HTML,
    )

    jobs = LinkedInEmailParser.parse(email_data)
    assert len(jobs) == 2

    j1 = jobs[0]
    assert j1.source == "LinkedIn Email Alert"
    assert j1.source_job_id == "li_3912345678"
    assert j1.title == "Senior AI Engineer"
    assert j1.company == "AI Alpha Labs"
    assert j1.location == "Bangalore, India"
    assert j1.url == "https://www.linkedin.com/jobs/view/3912345678"
    assert j1.fingerprint is not None

    j2 = jobs[1]
    assert j2.source_job_id == "li_3987654321"
    assert j2.title == "Data Scientist"
    assert j2.company == "Data Dynamics"


def test_linkedin_email_parser_missing_fields():
    """Test parsing LinkedIn card with missing optional company/location."""
    email_data = ParsedEmailData(
        message_id="msg_2",
        received_at="2026-09-18T10:00:00Z",
        html_content=LINKEDIN_MISSING_FIELDS_HTML,
    )

    jobs = LinkedInEmailParser.parse(email_data)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "Computer Vision Researcher"
    assert j.source_job_id == "li_3955555555"


def test_linkedin_email_parser_empty_body():
    """Test parsing email with empty body does not crash."""
    email_data = ParsedEmailData(message_id="msg_empty", received_at="", html_content="", plain_text="")
    jobs = LinkedInEmailParser.parse(email_data)
    assert len(jobs) == 0


# ---------------------------------------------------------------------
# 3. Indeed Email Parser Tests
# ---------------------------------------------------------------------


def test_indeed_email_parser_valid_html():
    """Test parsing standard Indeed job alert HTML email fixture."""
    email_data = ParsedEmailData(
        message_id="msg_ind_1",
        received_at="2026-09-18T11:00:00Z",
        subject="10 new Machine Learning jobs",
        sender="alert@indeed.com",
        html_content=INDEED_EMAIL_HTML,
    )

    jobs = IndeedEmailParser.parse(email_data)
    assert len(jobs) == 2

    j1 = jobs[0]
    assert j1.source == "Indeed Email Alert"
    assert j1.source_job_id == "ind_1234567890abcdef"
    assert j1.title == "Machine Learning Developer"
    assert j1.company == "Beta Tech Systems"
    assert j1.location == "Chennai, Tamil Nadu"
    assert j1.url == "https://www.indeed.com/viewjob?jk=1234567890abcdef"

    j2 = jobs[1]
    assert j2.source_job_id == "ind_fedcba0987654321"
    assert j2.title == "Python Developer"
    assert j2.company == "PyCorp"


def test_indeed_email_parser_missing_fields():
    """Test parsing Indeed card with missing optional company/location."""
    email_data = ParsedEmailData(
        message_id="msg_ind_2",
        received_at="2026-09-18T11:00:00Z",
        html_content=INDEED_MISSING_FIELDS_HTML,
    )

    jobs = IndeedEmailParser.parse(email_data)
    assert len(jobs) == 1
    assert jobs[0].title == "NLP Engineer"
    assert jobs[0].source_job_id == "ind_9998887776665554"


# ---------------------------------------------------------------------
# 4. Gmail Client Tests (Base64url Decoding & OAuth Flow Mocks)
# ---------------------------------------------------------------------


def test_decode_message_payload():
    """Test base64url decoding of MIME body parts in GmailAPIClient."""
    sample_text = "<h1>Job Alert</h1>"
    encoded_bytes = base64.urlsafe_b64encode(sample_text.encode("utf-8")).decode("utf-8")

    message_dict = {
        "id": "1893abc",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Job Alert"},
                {"name": "From", "value": "alert@linkedin.com"},
                {"name": "Date", "value": "2026-09-18T12:00:00Z"},
            ],
            "mimeType": "text/html",
            "body": {"data": encoded_bytes},
        },
    }

    client = GmailAPIClient()
    parsed = client.decode_message_payload(message_dict)

    assert parsed.message_id == "1893abc"
    assert parsed.subject == "Job Alert"
    assert parsed.sender == "alert@linkedin.com"
    assert "Job Alert" in parsed.html_content


@patch("app.sources.gmail.gmail_client.Credentials")
@patch("os.path.exists")
def test_gmail_client_authenticate_valid_token(mock_exists, mock_credentials_cls):
    """Test authentication with cached token.json."""
    mock_exists.return_value = True
    mock_creds_inst = MagicMock()
    mock_creds_inst.valid = True
    mock_credentials_cls.from_authorized_user_file.return_value = mock_creds_inst

    client = GmailAPIClient(token_path="test_token.json")
    creds = client.authenticate()

    assert creds.valid
    assert mock_credentials_cls.from_authorized_user_file.called


@patch("app.sources.gmail.gmail_client.Credentials")
@patch("os.path.exists")
def test_gmail_client_authenticate_refresh_token(mock_exists, mock_credentials_cls):
    """Test refreshing expired OAuth credentials when refresh token exists."""
    mock_exists.return_value = True
    mock_creds_inst = MagicMock()
    mock_creds_inst.valid = False
    mock_creds_inst.expired = True
    mock_creds_inst.refresh_token = "ref_123"
    mock_credentials_cls.from_authorized_user_file.return_value = mock_creds_inst

    client = GmailAPIClient(token_path="test_token.json")
    with patch("app.sources.gmail.gmail_client.Request"):
        creds = client.authenticate()

    assert mock_creds_inst.refresh.called


# ---------------------------------------------------------------------
# 5. Source Execution & Failure Isolation Tests
# ---------------------------------------------------------------------


@patch.object(GmailAPIClient, "search_messages")
@patch.object(GmailAPIClient, "get_message_detail")
def test_linkedin_alert_email_source_success(mock_detail, mock_search):
    """Test successful LinkedIn alert source fetching and parsing."""
    mock_search.return_value = [{"id": "m1"}]

    encoded_bytes = base64.urlsafe_b64encode(LINKEDIN_EMAIL_HTML.encode("utf-8")).decode("utf-8")
    mock_detail.return_value = {
        "id": "m1",
        "payload": {
            "headers": [{"name": "Subject", "value": "Job Alert"}],
            "mimeType": "text/html",
            "body": {"data": encoded_bytes},
        },
    }

    client = GmailAPIClient()
    source = LinkedInAlertEmailSource(gmail_client=client)
    res = source.fetch_source_jobs()

    assert res.status == SourceStatus.SUCCESS
    assert res.total_fetched == 2
    assert len(res.jobs) == 2


@patch.object(GmailAPIClient, "search_messages")
def test_indeed_alert_email_source_api_failure(mock_search):
    """Test Gmail API failure handling in Indeed alert source returns FAILED status cleanly."""
    mock_search.side_effect = Exception("API Quota exceeded")

    client = GmailAPIClient()
    source = IndeedAlertEmailSource(gmail_client=client)
    res = source.fetch_source_jobs()

    assert res.status == SourceStatus.FAILED
    assert res.total_fetched == 0
    assert "API Quota exceeded" in res.error_message


# ---------------------------------------------------------------------
# 6. Pipeline Integration & Resume Matching Tests
# ---------------------------------------------------------------------


@patch("app.services.pipeline_service.GmailAPIClient")
@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_pipeline_service_gmail_enabled(mock_adzuna_class, mock_matching_class, mock_gmail_client_cls, memory_db, test_config):
    """Test pipeline execution with Gmail API ingestion enabled."""
    mock_source = MagicMock()
    mock_source.fetch_jobs_for_keyword.return_value = ([], True)
    mock_adzuna_class.return_value = mock_source

    mock_client_inst = MagicMock()
    encoded_bytes = base64.urlsafe_b64encode(LINKEDIN_EMAIL_HTML.encode("utf-8")).decode("utf-8")
    mock_client_inst.search_messages.return_value = [{"id": "m1"}]
    mock_client_inst.get_message_detail.return_value = {
        "id": "m1",
        "payload": {
            "headers": [{"name": "Subject", "value": "Job Alert"}],
            "mimeType": "text/html",
            "body": {"data": encoded_bytes},
        },
    }
    mock_client_inst.decode_message_payload.side_effect = lambda msg: GmailAPIClient().decode_message_payload(msg)
    mock_gmail_client_cls.return_value = mock_client_inst


    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = []
    mock_matching_class.return_value = mock_matching

    pipeline_service = PipelineService(config=test_config)
    summary = pipeline_service.run_monitoring_pipeline(config=test_config, conn=memory_db)

    assert summary.status == PipelineStatus.SUCCESS
    assert summary.jobs_fetched > 0
    assert summary.failed_sources == 0
