"""
Unit tests for Phase 10.3 — Unstop + foundit Gmail Job Alert Ingestion.
Verifies plain text and HTML parsing, URL normalization, ID extraction (un_<id>, fm_<id>),
fingerprint generation, failure isolation, registry integration, and regression across
Naukri, Glassdoor, LinkedIn, Indeed, and Gmail auth.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.models import SourceStatus
from app.sources.gmail.email_parser import (
    GlassdoorEmailParser,
    IndeedEmailParser,
    LinkedInEmailParser,
    NaukriEmailParser,
    UnstopEmailParser,
    founditEmailParser,
    normalize_foundit_url,
    normalize_unstop_url,
)
from app.sources.gmail.gmail_source import (
    UnstopAlertEmailSource,
    founditAlertEmailSource,
)
from app.sources.gmail.models import ParsedEmailData
from app.sources.registry import create_default_source_registry


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_app_id",
        adzuna_app_key="test_app_key",
        source_unstop_enabled=True,
        source_foundit_enabled=True,
        source_naukri_enabled=True,
        source_glassdoor_enabled=True,
        source_gmail_enabled=True,
    )


# ============================================================================
# 1. UNSTOP PLAIN-TEXT PARSING
# ============================================================================

def test_unstop_plain_text_parsing():
    email = ParsedEmailData(
        message_id="msg_unstop_txt_1",
        received_at="2026-09-19T10:00:00Z",
        subject="New Job Opportunity on Unstop: AI Engineer",
        sender="opportunity-alerts@unstop.com",
        plain_text="Check out this opportunity: https://unstop.com/o/ai-engineer-sub-100200300?ref=email_alert",
    )

    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "Unstop Email Alert"
    assert job.source_job_id == "un_100200300"
    assert job.url == "https://unstop.com/o/100200300"
    assert "Ai Engineer" in job.title or "AI Engineer" in job.title or "Unstop" in job.title
    assert job.created_at == "2026-09-19T10:00:00Z"


# ============================================================================
# 2. UNSTOP HTML PARSING
# ============================================================================

def test_unstop_html_email_parsing():
    html_body = """
    <html>
      <body>
        <div class="opportunity-card">
          <a class="title-link" href="https://unstop.com/o/machine-learning-lead-999888777?utm_source=alert">
            Machine Learning Lead
          </a>
          <span class="organization">Tech Corp</span>
          <span class="location">Bengaluru, India</span>
          <div class="description">Lead our machine learning team building LLM pipelines.</div>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_unstop_html_1",
        received_at="2026-09-19T11:00:00Z",
        subject="Matching Opportunities for You",
        sender="no-reply@unstop.com",
        html_content=html_body,
    )

    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "Unstop Email Alert"
    assert job.source_job_id == "un_999888777"
    assert job.title == "Machine Learning Lead"
    assert job.company == "Tech Corp"
    assert job.location == "Bengaluru, India"
    assert "LLM pipelines" in job.description


# ============================================================================
# 3. FOUNDIT PLAIN-TEXT PARSING
# ============================================================================

def test_foundit_plain_text_parsing():
    email = ParsedEmailData(
        message_id="msg_foundit_txt_1",
        received_at="2026-09-19T12:00:00Z",
        subject="foundit Job Alert: Data Scientist",
        sender="alerts@foundit.in",
        plain_text="View details for Data Scientist position: https://www.foundit.in/job/data-scientist-innovate-tech-pune-77665544?ref=email",
    )

    jobs = founditEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "foundit Email Alert"
    assert job.source_job_id == "fm_77665544"
    assert job.url == "https://www.foundit.in/job/77665544"
    assert "Data Scientist" in job.title or "foundit" in job.title


# ============================================================================
# 4. FOUNDIT HTML PARSING
# ============================================================================

def test_foundit_html_email_parsing():
    html_body = """
    <html>
      <body>
        <div class="job-container">
          <a class="job-title" href="https://www.foundit.in/job/senior-nlp-engineer-acme-inc-hyderabad-44332211">
            Senior NLP Engineer
          </a>
          <div class="company-name">Acme Inc</div>
          <div class="location">Hyderabad</div>
          <div class="snippet">Seeking NLP experts with Transformers and PyTorch expertise.</div>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_foundit_html_1",
        received_at="2026-09-19T13:00:00Z",
        subject="Daily Jobs Digest",
        sender="jobs@monsterindia.com",
        html_content=html_body,
    )

    jobs = founditEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "foundit Email Alert"
    assert job.source_job_id == "fm_44332211"
    assert job.title == "Senior NLP Engineer"
    assert job.company == "Acme Inc"
    assert job.location == "Hyderabad"
    assert "Transformers" in job.description


# ============================================================================
# 5. MISSING OPTIONAL FIELDS
# ============================================================================

def test_missing_optional_fields():
    email = ParsedEmailData(
        message_id="msg_minimal_1",
        received_at="2026-09-19T14:00:00Z",
        subject="Opportunity",
        sender="alert@unstop.com",
        plain_text="https://unstop.com/o/minimal-role-554433",
    )

    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == ""
    assert job.location == ""
    assert job.salary_min is None
    assert job.salary_max is None


# ============================================================================
# 6. MALFORMED UNSTOP EMAIL
# ============================================================================

def test_malformed_unstop_email():
    email = ParsedEmailData(
        message_id="msg_bad_unstop",
        received_at="2026-09-19T15:00:00Z",
        subject="Broken Email",
        sender="alerts@unstop.com",
        html_content="<div>Unclosed html with no valid urls <a href='invalid_url'>click here</a></div>",
    )

    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 0


# ============================================================================
# 7. MALFORMED FOUNDIT EMAIL
# ============================================================================

def test_malformed_foundit_email():
    email = ParsedEmailData(
        message_id="msg_bad_foundit",
        received_at="2026-09-19T15:00:00Z",
        subject="Malformed foundit",
        sender="alerts@foundit.in",
        plain_text="Invalid content with no foundit links present at all",
    )

    jobs = founditEmailParser.parse(email)
    assert len(jobs) == 0


# ============================================================================
# 8. IRRELEVANT EMAIL REJECTION
# ============================================================================

def test_irrelevant_email_rejection():
    email = ParsedEmailData(
        message_id="msg_marketing",
        received_at="2026-09-19T16:00:00Z",
        subject="Your Account Preferences",
        sender="newsletter@unstop.com",
        plain_text="Update your email subscription preferences at https://unstop.com/settings/privacy",
    )

    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 0


# ============================================================================
# 9. UNSTOP SENDER / DOMAIN RECOGNITION
# ============================================================================

def test_unstop_sender_domain_recognition():
    email_d2c = ParsedEmailData(
        message_id="msg_d2c",
        received_at="2026-09-19T16:30:00Z",
        subject="Challenge Alert",
        sender="notifications@d2c.in",
        plain_text="https://d2c.in/o/d2c-role-887766",
    )

    jobs = UnstopEmailParser.parse(email_d2c)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "un_887766"


# ============================================================================
# 10. FOUNDIT SENDER / DOMAIN RECOGNITION
# ============================================================================

def test_foundit_sender_domain_recognition():
    email_monster = ParsedEmailData(
        message_id="msg_monster",
        received_at="2026-09-19T17:00:00Z",
        subject="Monster Job Digest",
        sender="jobalerts@monsterindia.com",
        plain_text="https://www.monsterindia.com/job/dev-role-11223344",
    )

    jobs = founditEmailParser.parse(email_monster)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "fm_11223344"


# ============================================================================
# 11. SUBJECT CLASSIFICATION
# ============================================================================

def test_subject_classification():
    email = ParsedEmailData(
        message_id="msg_subj",
        received_at="2026-09-19T17:30:00Z",
        subject="Unstop Job Alert: Backend Developer",
        sender="alerts@unstop.com",
        plain_text="https://unstop.com/o/view-job-details-500600",
    )

    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 1
    assert "Backend Developer" in jobs[0].title or "Unstop" in jobs[0].title


# ============================================================================
# 12. URL EXTRACTION
# ============================================================================

def test_url_extraction_unstop_and_foundit():
    url_un, id_un = normalize_unstop_url("https://unstop.com/o/full-stack-engineer-12345?utm_source=email")
    assert url_un == "https://unstop.com/o/12345"
    assert id_un == "un_12345"

    url_fm, id_fm = normalize_foundit_url("https://www.foundit.in/job/devops-engineer-9876543?ref=alert")
    assert url_fm == "https://www.foundit.in/job/9876543"
    assert id_fm == "fm_9876543"


# ============================================================================
# 13. URL NORMALIZATION
# ============================================================================

def test_url_normalization():
    clean_un, id_un = normalize_unstop_url("https://unstop.com/jobs/ai-lead-54321?opportunityId=54321&ref=xyz")
    assert clean_un == "https://unstop.com/o/54321"
    assert id_un == "un_54321"

    clean_fm, id_fm = normalize_foundit_url("https://www.foundit.in/seeker/job-details?jobId=12345678&src=alert")
    assert clean_fm == "https://www.foundit.in/job/12345678"
    assert id_fm == "fm_12345678"


# ============================================================================
# 14. HTML ENTITY DECODING
# ============================================================================

def test_html_entity_decoding():
    html_body = """
    <html>
      <body>
        <div>
          <a href="https://unstop.com/o/c-plus-plus-dev-889900">
            C&amp;C&#43;&#43; Developer &gt; Senior Level
          </a>
          <span class="organization">R&amp;D Labs</span>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_entities",
        received_at="2026-09-19T18:00:00Z",
        subject="Entities Test",
        sender="alerts@unstop.com",
        html_content=html_body,
    )

    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 1
    assert "C&C++ Developer > Senior Level" in jobs[0].title
    assert "R&D Labs" in jobs[0].company


# ============================================================================
# 15. WHITESPACE NORMALIZATION
# ============================================================================

def test_whitespace_normalization():
    html_body = """
    <html>
      <body>
        <div>
          <a href="https://www.foundit.in/job/cloud-architect-112233">
            \n\t  Cloud   Architect  \n
          </a>
          <div class="company">\n   Enterprise   Cloud   Services  \n</div>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_whitespace",
        received_at="2026-09-19T18:30:00Z",
        subject="Whitespace",
        sender="alerts@foundit.in",
        html_content=html_body,
    )

    jobs = founditEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].title == "Cloud Architect"
    assert jobs[0].company == "Enterprise Cloud Services"


# ============================================================================
# 16. MULTIPLE JOBS IN ONE EMAIL
# ============================================================================

def test_multiple_jobs_in_one_email():
    html_body = """
    <html>
      <body>
        <div><a href="https://unstop.com/o/role-a-1111">Role A</a><span class="organization">Comp A</span></div>
        <div><a href="https://unstop.com/o/role-b-2222">Role B</a><span class="organization">Comp B</span></div>
        <div><a href="https://unstop.com/o/role-c-3333">Role C</a><span class="organization">Comp C</span></div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_multi",
        received_at="2026-09-19T19:00:00Z",
        subject="3 New Roles",
        sender="alerts@unstop.com",
        html_content=html_body,
    )

    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 3
    assert jobs[0].source_job_id == "un_1111"
    assert jobs[1].source_job_id == "un_2222"
    assert jobs[2].source_job_id == "un_3333"


# ============================================================================
# 17. DUPLICATE JOBS WITHIN SAME ALERT
# ============================================================================

def test_duplicate_jobs_within_same_alert():
    html_body = """
    <html>
      <body>
        <div><a href="https://www.foundit.in/job/dup-role-99999">Role Dup</a></div>
        <div><a href="https://www.foundit.in/job/dup-role-99999?ref=card">Role Dup</a></div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_dup",
        received_at="2026-09-19T19:30:00Z",
        subject="Duplicate Link",
        sender="alerts@foundit.in",
        html_content=html_body,
    )

    jobs = founditEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "fm_99999"


# ============================================================================
# 18. CROSS-SOURCE FINGERPRINT COMPATIBILITY
# ============================================================================

def test_cross_source_fingerprint_compatibility():
    email_un = ParsedEmailData(
        message_id="msg_un_fp",
        received_at="2026-09-19T20:00:00Z",
        subject="Role",
        sender="alerts@unstop.com",
        html_content='<div><a href="https://unstop.com/o/role-123">AI Engineer</a><span class="organization">Google</span><span class="location">Remote</span></div>',
    )
    email_fm = ParsedEmailData(
        message_id="msg_fm_fp",
        received_at="2026-09-19T20:00:00Z",
        subject="Role",
        sender="alerts@foundit.in",
        html_content='<div><a href="https://www.foundit.in/job/role-456">AI Engineer</a><span class="company">Google</span><span class="location">Remote</span></div>',
    )

    job_un = UnstopEmailParser.parse(email_un)[0]
    job_fm = founditEmailParser.parse(email_fm)[0]

    assert job_un.fingerprint == job_fm.fingerprint


# ============================================================================
# 19. SOURCE ENABLED / DISABLED BEHAVIOR
# ============================================================================

def test_source_enabled_disabled_behavior(mock_config):
    unstop_src = UnstopAlertEmailSource()
    foundit_src = founditAlertEmailSource()

    assert unstop_src.is_enabled(mock_config) is True
    assert foundit_src.is_enabled(mock_config) is True

    mock_config.source_unstop_enabled = False
    assert unstop_src.is_enabled(mock_config) is False

    mock_config.source_foundit_enabled = False
    assert foundit_src.is_enabled(mock_config) is False


# ============================================================================
# 20. PARSER FAILURE ISOLATION & REGISTRY INTEGRATION
# ============================================================================

@patch("app.sources.gmail.gmail_client.GmailAPIClient.search_messages")
@patch("app.sources.gmail.gmail_client.GmailAPIClient.get_message_detail")
@patch("app.sources.gmail.gmail_client.GmailAPIClient.decode_message_payload")
def test_parser_failure_isolation_and_registry(mock_decode, mock_get_detail, mock_search, mock_config):
    mock_search.return_value = [{"id": "msg_err"}, {"id": "msg_ok"}]
    mock_get_detail.side_effect = [Exception("Detail error"), {"id": "msg_ok"}]
    mock_decode.return_value = ParsedEmailData(
        message_id="msg_ok",
        received_at="2026-09-19T20:30:00Z",
        plain_text="https://unstop.com/o/ok-role-777888",
    )

    unstop_src = UnstopAlertEmailSource()
    res = unstop_src.fetch_source_jobs()

    assert res.status == SourceStatus.PARTIAL_FAILURE
    assert res.total_fetched == 1
    assert res.jobs[0].source_job_id == "un_777888"

    registry = create_default_source_registry(mock_config)
    source_ids = [s.source_identifier for s in registry.list_sources()]
    assert "unstop_email" in source_ids
    assert "foundit_email" in source_ids


# ============================================================================
# 21. EXISTING NAUKRI REGRESSION
# ============================================================================

def test_naukri_parser_regression():
    email = ParsedEmailData(
        message_id="msg_nk_regr",
        received_at="2026-09-19T21:00:00Z",
        subject="Naukri Job Alert: Python Developer",
        sender="no-reply@naukri.com",
        plain_text="https://www.naukri.com/job-listings-python-developer-company-chennai-120923005555",
    )
    jobs = NaukriEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "nk_120923005555"


# ============================================================================
# 22. EXISTING GLASSDOOR REGRESSION
# ============================================================================

def test_glassdoor_parser_regression():
    email = ParsedEmailData(
        message_id="msg_gd_regr",
        received_at="2026-09-19T21:15:00Z",
        subject="Glassdoor Alert",
        sender="noreply@glassdoor.com",
        plain_text="https://www.glassdoor.com/job-listing/ml-engineer-JV_IC1147401.htm?jl=1008899776",
    )
    jobs = GlassdoorEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "gd_1008899776"


# ============================================================================
# 23. EXISTING LINKEDIN REGRESSION
# ============================================================================

def test_linkedin_parser_regression():
    email = ParsedEmailData(
        message_id="msg_li_regr",
        received_at="2026-09-19T21:30:00Z",
        subject="LinkedIn Alert",
        sender="jobalerts-noreply@linkedin.com",
        html_content='<div><a href="https://www.linkedin.com/comm/jobs/view/3912345678/?refId=abc">Software Engineer</a><span class="company-name">Meta</span></div>',
    )
    jobs = LinkedInEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "li_3912345678"


# ============================================================================
# 24. EXISTING INDEED REGRESSION
# ============================================================================

def test_indeed_parser_regression():
    email = ParsedEmailData(
        message_id="msg_ind_regr",
        received_at="2026-09-19T21:45:00Z",
        subject="Indeed Alert",
        sender="alert@indeed.com",
        html_content='<div><a href="https://www.indeed.com/rc/clk?jk=abc1234567890def">Data Analyst</a><span class="company">Amazon</span></div>',
    )
    jobs = IndeedEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "ind_abc1234567890def"


# ============================================================================
# 25. GMAIL AUTHENTICATION REGRESSION
# ============================================================================

@patch("os.path.exists")
def test_gmail_auth_regression(mock_exists):
    from app.sources.gmail.gmail_client import GmailAPIClient
    mock_exists.return_value = False
    client = GmailAPIClient(credentials_path="non_existent.json", token_path="non_existent_token.json")
    with pytest.raises(FileNotFoundError):
        client.authenticate()
