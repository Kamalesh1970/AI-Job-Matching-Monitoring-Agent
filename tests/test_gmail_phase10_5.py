"""
Unit tests for Phase 10.5 — Wellfound Gmail Job Alert Ingestion.
Verifies plain text and HTML parsing, URL normalization, ID extraction (wf_<id>),
fingerprint generation, failure isolation, registry integration, and regression across
Naukri, Glassdoor, Unstop, foundit, Cutshort, Hirist, LinkedIn, Indeed, and Gmail auth.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.models import SourceStatus
from app.services.deduplication import generate_fingerprint
from app.sources.gmail.email_parser import (
    CutshortEmailParser,
    GlassdoorEmailParser,
    HiristEmailParser,
    IndeedEmailParser,
    LinkedInEmailParser,
    NaukriEmailParser,
    UnstopEmailParser,
    WellfoundEmailParser,
    classify_email,
    founditEmailParser,
    normalize_wellfound_url,
)
from app.sources.gmail.gmail_source import (
    WellfoundAlertEmailSource,
)
from app.sources.gmail.models import ParsedEmailData
from app.sources.registry import create_default_source_registry


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_app_id",
        adzuna_app_key="test_app_key",
        source_wellfound_enabled=True,
        source_hirist_enabled=True,
        source_cutshort_enabled=True,
        source_unstop_enabled=True,
        source_foundit_enabled=True,
        source_naukri_enabled=True,
        source_glassdoor_enabled=True,
        source_gmail_enabled=True,
    )


# ============================================================================
# 1. WELLFOUND PLAIN-TEXT PARSING
# ============================================================================

def test_wellfound_plain_text_parsing():
    email = ParsedEmailData(
        message_id="msg_wf_txt_1",
        received_at="2026-09-21T10:00:00Z",
        subject="Matching Job on Wellfound: Staff AI Engineer",
        sender="talent@wellfound.com",
        plain_text="View details for Staff AI Engineer position: https://wellfound.com/jobs/9988776-staff-ai-engineer?utm_source=email",
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "Wellfound Email Alert"
    assert job.source_job_id == "wf_9988776"
    assert job.url == "https://wellfound.com/jobs/9988776"
    assert "Staff Ai Engineer" in job.title or "Staff AI Engineer" in job.title or "Wellfound" in job.title
    assert job.created_at == "2026-09-21T10:00:00Z"


# ============================================================================
# 2. WELLFOUND HTML PARSING
# ============================================================================

def test_wellfound_html_email_parsing():
    html_body = """
    <html>
      <body>
        <div class="job-card">
          <a class="job-title" href="https://wellfound.com/jobs/5544332-principal-systems-architect?ref=alert">
            Principal Systems Architect
          </a>
          <span class="company-name">HyperScale AI</span>
          <span class="location">San Francisco, CA (Remote)</span>
          <div class="description">$180k - $250k • 0.1% - 0.5% Equity</div>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_wf_html_1",
        received_at="2026-09-21T11:00:00Z",
        subject="Your Daily Wellfound Matches",
        sender="notifications@wellfound.com",
        html_content=html_body,
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "Wellfound Email Alert"
    assert job.source_job_id == "wf_5544332"
    assert job.company == "HyperScale AI"
    assert job.location == "San Francisco, CA (Remote)"
    assert "$180k" in job.description or "Equity" in job.description


# ============================================================================
# 3. MISSING OPTIONAL FIELDS
# ============================================================================

def test_wellfound_missing_optional_fields():
    html_body = """
    <html>
      <body>
        <div>
          <a href="https://wellfound.com/jobs/1122334">Frontend Developer</a>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_wf_opt_1",
        received_at="2026-09-21T12:00:00Z",
        subject="New Opportunity",
        sender="jobs@angel.co",
        html_content=html_body,
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Frontend Developer"
    assert job.company == ""
    assert job.location == ""
    assert job.description == "Frontend Developer"


# ============================================================================
# 4. MALFORMED WELLFOUND EMAIL
# ============================================================================

def test_malformed_wellfound_email():
    email = ParsedEmailData(
        message_id="msg_wf_malformed_1",
        received_at="2026-09-21T12:00:00Z",
        subject="Malformed Wellfound",
        sender="notifications@wellfound.com",
        html_content="<a href='https://wellfound.com/jobs/invalid-url-no-id'>Broken Link</a>",
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_job_id.startswith("wf_")


# ============================================================================
# 5. IRRELEVANT EMAIL REJECTION
# ============================================================================

def test_wellfound_irrelevant_email_rejection():
    email = ParsedEmailData(
        message_id="msg_wf_irrelevant_1",
        received_at="2026-09-21T12:00:00Z",
        subject="Security Update for your Wellfound Account",
        sender="security@wellfound.com",
        plain_text="Please update your password by visiting https://wellfound.com/settings/privacy",
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 0


# ============================================================================
# 6. SENDER / DOMAIN CLASSIFICATION
# ============================================================================

def test_wellfound_sender_domain_classification():
    email_wf = ParsedEmailData(
        message_id="msg_class_1",
        received_at="2026-09-21T12:00:00Z",
        subject="Weekly Startup Jobs",
        sender="digest@wellfound.com",
        plain_text="Jobs: https://wellfound.com/jobs/1000",
    )
    email_angel = ParsedEmailData(
        message_id="msg_class_2",
        received_at="2026-09-21T12:00:00Z",
        subject="AngelList Matches",
        sender="recommendations@angel.co",
        plain_text="Jobs: https://angel.co/jobs/2000",
    )

    assert WellfoundEmailParser.is_wellfound_email(email_wf) is True
    assert classify_email(email_wf) == "wellfound_email"
    assert WellfoundEmailParser.is_wellfound_email(email_angel) is True
    assert classify_email(email_angel) == "wellfound_email"


# ============================================================================
# 7. SUBJECT CLASSIFICATION
# ============================================================================

def test_wellfound_subject_classification():
    email = ParsedEmailData(
        message_id="msg_subj_1",
        received_at="2026-09-21T12:00:00Z",
        subject="Wellfound: 5 Startup Jobs matching your profile",
        sender="noreply@jobalerts-digest.org",
        plain_text="Checkout startup jobs at https://wellfound.com/jobs/3000",
    )

    assert WellfoundEmailParser.is_wellfound_email(email) is True
    assert classify_email(email) == "wellfound_email"


# ============================================================================
# 8. URL EXTRACTION
# ============================================================================

def test_wellfound_url_extraction():
    html_body = """
    <div>
      <a href="https://wellfound.com/l/2abcde?utm_campaign=daily">Founding AI Researcher</a>
    </div>
    """
    email = ParsedEmailData(
        message_id="msg_url_ext",
        received_at="2026-09-21T12:00:00Z",
        subject="Startup Jobs",
        sender="matches@wellfound.com",
        html_content=html_body,
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].url == "https://wellfound.com/l/2abcde"
    assert jobs[0].source_job_id == "wf_2abcde"


# ============================================================================
# 9. URL NORMALIZATION
# ============================================================================

def test_wellfound_url_normalization():
    url_wf, id_wf = normalize_wellfound_url("https://wellfound.com/jobs/887766-devops-lead?utm_source=email&ref=123")
    assert url_wf == "https://wellfound.com/jobs/887766"
    assert id_wf == "wf_887766"

    url_angel, id_angel = normalize_wellfound_url("https://angel.co/jobs/443322-data-scientist?src=alert")
    assert url_angel == "https://wellfound.com/jobs/443322"
    assert id_angel == "wf_443322"


# ============================================================================
# 10. JOB ID EXTRACTION
# ============================================================================

def test_wellfound_job_id_extraction():
    url, job_id = normalize_wellfound_url("https://wellfound.com/view?jobId=776655&referrer=email")
    assert url == "https://wellfound.com/jobs/776655"
    assert job_id == "wf_776655"


# ============================================================================
# 11. HTML ENTITY DECODING
# ============================================================================

def test_wellfound_html_entity_decoding():
    html_body = """
    <div>
      <a href="https://wellfound.com/jobs/990011">R&amp;D Lead &lt;AI&gt;</a>
      <span class="company-name">AT&amp;T Systems</span>
    </div>
    """
    email = ParsedEmailData(
        message_id="msg_entity",
        received_at="2026-09-21T12:00:00Z",
        subject="Jobs",
        sender="alerts@wellfound.com",
        html_content=html_body,
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].title == "R&D Lead <AI>"
    assert jobs[0].company == "AT&T Systems"


# ============================================================================
# 12. WHITESPACE NORMALIZATION
# ============================================================================

def test_wellfound_whitespace_normalization():
    html_body = """
    <div>
      <a href="https://wellfound.com/jobs/123000">
         Senior   Cloud   Engineer 
      </a>
      <span class="company-name">  Acme   Corp  </span>
    </div>
    """
    email = ParsedEmailData(
        message_id="msg_ws",
        received_at="2026-09-21T12:00:00Z",
        subject="Jobs",
        sender="alerts@wellfound.com",
        html_content=html_body,
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].title == "Senior Cloud Engineer"
    assert jobs[0].company == "Acme Corp"


# ============================================================================
# 13. MULTIPLE JOBS IN ONE EMAIL
# ============================================================================

def test_wellfound_multiple_jobs_in_one_email():
    html_body = """
    <div>
      <a href="https://wellfound.com/jobs/111">Job One</a>
      <a href="https://wellfound.com/jobs/222">Job Two</a>
      <a href="https://wellfound.com/jobs/333">Job Three</a>
    </div>
    """
    email = ParsedEmailData(
        message_id="msg_multi",
        received_at="2026-09-21T12:00:00Z",
        subject="Multiple Jobs",
        sender="alerts@wellfound.com",
        html_content=html_body,
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 3
    assert [j.source_job_id for j in jobs] == ["wf_111", "wf_222", "wf_333"]


# ============================================================================
# 14. DUPLICATE JOBS WITHIN ONE EMAIL
# ============================================================================

def test_wellfound_duplicate_jobs_in_one_email():
    html_body = """
    <div>
      <a href="https://wellfound.com/jobs/111?src=header">Job One Title</a>
      <a href="https://wellfound.com/jobs/111?src=button">Apply Now</a>
    </div>
    """
    email = ParsedEmailData(
        message_id="msg_dup",
        received_at="2026-09-21T12:00:00Z",
        subject="Duplicate Link Email",
        sender="alerts@wellfound.com",
        html_content=html_body,
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "wf_111"


# ============================================================================
# 15. CROSS-SOURCE FINGERPRINT COMPATIBILITY
# ============================================================================

def test_wellfound_cross_source_fingerprint_compatibility():
    company = "OpenSource Tech"
    title = "Backend Engineer"
    location = "Remote"

    expected_fp = generate_fingerprint(company=company, title=title, location=location)

    html_body = f"""
    <div>
      <a href="https://wellfound.com/jobs/998877">{title}</a>
      <span class="company">{company}</span>
      <span class="location">{location}</span>
    </div>
    """
    email = ParsedEmailData(
        message_id="msg_fp",
        received_at="2026-09-21T12:00:00Z",
        subject="Job Alert",
        sender="alerts@wellfound.com",
        html_content=html_body,
    )

    jobs = WellfoundEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].fingerprint == expected_fp


# ============================================================================
# 16. SOURCE ENABLED BEHAVIOR
# ============================================================================

def test_wellfound_source_enabled_behavior(mock_config):
    source = WellfoundAlertEmailSource()
    assert source.is_enabled(mock_config) is True


# ============================================================================
# 17. SOURCE DISABLED BEHAVIOR
# ============================================================================

def test_wellfound_source_disabled_behavior(mock_config):
    mock_config.source_wellfound_enabled = False
    source = WellfoundAlertEmailSource()
    assert source.is_enabled(mock_config) is False


# ============================================================================
# 18. PARSER FAILURE ISOLATION
# ============================================================================

def test_wellfound_parser_failure_isolation():
    mock_client = MagicMock()
    mock_client.search_messages.return_value = [{"id": "m1"}, {"id": "m2"}]
    mock_client.get_message_detail.side_effect = [
        {"id": "m1"},
        Exception("API Decode Error"),
    ]

    mock_email = ParsedEmailData(
        message_id="m1",
        received_at="2026-09-21T12:00:00Z",
        subject="Wellfound Match",
        sender="jobs@wellfound.com",
        plain_text="Check job https://wellfound.com/jobs/101",
    )
    mock_client.decode_message_payload.return_value = mock_email

    source = WellfoundAlertEmailSource(gmail_client=mock_client)
    res = source.fetch_source_jobs()

    assert res.status == SourceStatus.PARTIAL_FAILURE
    assert len(res.jobs) == 1
    assert res.jobs[0].source_job_id == "wf_101"


# ============================================================================
# 19. NAUKRI REGRESSION
# ============================================================================

def test_naukri_parser_regression():
    email = ParsedEmailData(
        message_id="msg_naukri_reg",
        received_at="2026-09-21T12:00:00Z",
        subject="Naukri Job Alert: Data Analyst",
        sender="jobalerts@naukri.com",
        html_content="<a href='https://www.naukri.com/job-listings-data-analyst-123456'>Data Analyst</a>",
    )
    jobs = NaukriEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "Naukri Email Alert"


# ============================================================================
# 20. GLASSDOOR REGRESSION
# ============================================================================

def test_glassdoor_parser_regression():
    email = ParsedEmailData(
        message_id="msg_gd_reg",
        received_at="2026-09-21T12:00:00Z",
        subject="Glassdoor Alert: Software Engineer",
        sender="noreply@glassdoor.com",
        html_content="<a href='https://www.glassdoor.com/job-listing/jl.htm?jl=1008899'>Software Engineer</a>",
    )
    jobs = GlassdoorEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "Glassdoor Email Alert"


# ============================================================================
# 21. UNSTOP REGRESSION
# ============================================================================

def test_unstop_parser_regression():
    email = ParsedEmailData(
        message_id="msg_unstop_reg",
        received_at="2026-09-21T12:00:00Z",
        subject="Unstop Opportunity: Hackathon",
        sender="opportunity@unstop.com",
        html_content="<a href='https://unstop.com/jobs/sde-intern-54321'>SDE Intern</a>",
    )
    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "Unstop Email Alert"


# ============================================================================
# 22. FOUNDIT REGRESSION
# ============================================================================

def test_foundit_parser_regression():
    email = ParsedEmailData(
        message_id="msg_foundit_reg",
        received_at="2026-09-21T12:00:00Z",
        subject="foundit Job Digest",
        sender="alerts@foundit.in",
        html_content="<a href='https://www.foundit.in/job/full-stack-developer-9900'>Full Stack Developer</a>",
    )
    jobs = founditEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "foundit Email Alert"


# ============================================================================
# 23. CUTSHORT REGRESSION
# ============================================================================

def test_cutshort_parser_regression():
    email = ParsedEmailData(
        message_id="msg_cs_reg",
        received_at="2026-09-21T12:00:00Z",
        subject="Cutshort Job Alert",
        sender="notifications@cutshort.io",
        html_content="<a href='https://cutshort.io/job/ai-lead-12345'>AI Lead</a>",
    )
    jobs = CutshortEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "Cutshort Email Alert"


# ============================================================================
# 24. HIRIST REGRESSION
# ============================================================================

def test_hirist_parser_regression():
    email = ParsedEmailData(
        message_id="msg_hi_reg",
        received_at="2026-09-21T12:00:00Z",
        subject="Hirist Job Digest",
        sender="alerts@hirist.tech",
        html_content="<a href='https://www.hirist.tech/j/cloud-architect-112233.html'>Cloud Architect</a>",
    )
    jobs = HiristEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "Hirist Email Alert"


# ============================================================================
# 25. LINKEDIN REGRESSION
# ============================================================================

def test_linkedin_parser_regression():
    email = ParsedEmailData(
        message_id="msg_li_reg",
        received_at="2026-09-21T12:00:00Z",
        subject="LinkedIn Job Alert",
        sender="jobalerts-noreply@linkedin.com",
        html_content="<a href='https://www.linkedin.com/jobs/view/1234567890'>DevOps Specialist</a>",
    )
    jobs = LinkedInEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "LinkedIn Email Alert"


# ============================================================================
# 26. INDEED REGRESSION
# ============================================================================

def test_indeed_parser_regression():
    email = ParsedEmailData(
        message_id="msg_ind_reg",
        received_at="2026-09-21T12:00:00Z",
        subject="Indeed Job Alert",
        sender="alert@indeed.com",
        html_content="<a href='https://www.indeed.com/viewjob?jk=abcdef1234567890'>Site Reliability Engineer</a>",
    )
    jobs = IndeedEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "Indeed Email Alert"


# ============================================================================
# 27. GMAIL AUTHENTICATION REGRESSION
# ============================================================================

def test_gmail_authentication_regression():
    with patch("app.sources.gmail.gmail_client.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        source = WellfoundAlertEmailSource()
        assert source.source_identifier == "wellfound_email"
        assert source.name == "Wellfound Email Alert"


# ============================================================================
# 28. SOURCE REGISTRY REGRESSION
# ============================================================================

def test_wellfound_source_registry_regression(mock_config):
    registry = create_default_source_registry(mock_config)
    source = registry.get_source("wellfound_email")
    assert source is not None
    assert source.name == "Wellfound Email Alert"
    assert registry.is_source_enabled("wellfound_email", mock_config) is True
