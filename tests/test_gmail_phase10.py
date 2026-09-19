"""
Unit tests for Phase 10.2: Naukri & Glassdoor Gmail job-alert email ingestion and parsing.
Includes 20 targeted tests plus regression checks for LinkedIn, Indeed, and Gmail authentication.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.models import Job, SourceStatus
from app.sources.gmail.email_parser import (
    GlassdoorEmailParser,
    IndeedEmailParser,
    LinkedInEmailParser,
    NaukriEmailParser,
    normalize_glassdoor_url,
    normalize_naukri_url,
)
from app.sources.gmail.gmail_source import GlassdoorAlertEmailSource, NaukriAlertEmailSource
from app.sources.gmail.models import ParsedEmailData
from app.sources.registry import create_default_source_registry


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_app_id",
        adzuna_app_key="test_app_key",
        source_gmail_enabled=True,
        source_naukri_enabled=True,
        source_glassdoor_enabled=True,
        gmail_naukri_query="from:(naukri.com) newer_than:2d",
        gmail_glassdoor_query="from:(glassdoor.com) newer_than:2d",
    )


# ============================================================================
# 1. NAUKRI PLAIN-TEXT EMAIL PARSING
# ============================================================================

def test_naukri_plain_text_parsing():
    email = ParsedEmailData(
        message_id="msg_nk_01",
        received_at="2026-09-19T10:00:00Z",
        subject="Naukri Job Alert: Senior Python Developer",
        sender="naukrialerts@naukri.com",
        plain_text="""
        Job Recommendation:
        Title: Senior Python Developer
        Company: Tech Solutions Ltd
        Location: Bengaluru
        Link: https://www.naukri.com/job-listings-senior-python-developer-tech-solutions-bengaluru-120923005555
        """,
    )
    jobs = NaukriEmailParser.parse(email)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "Naukri Email Alert"
    assert j.source_job_id == "nk_120923005555"
    assert "https://www.naukri.com/job-listings-senior-python-developer-tech-solutions-bengaluru-120923005555" in j.url
    assert j.fingerprint is not None


# ============================================================================
# 2. NAUKRI HTML EMAIL PARSING
# ============================================================================

def test_naukri_html_email_parsing():
    html_content = """
    <html>
      <body>
        <div class="job-tuple">
          <a href="https://www.naukri.com/job-listings-ai-engineer-acme-corp-chennai-998877665544?src=alert">
            AI & Machine Learning Engineer
          </a>
          <span class="comp-name">Acme Corp</span>
          <span class="loc">Chennai</span>
          <p class="desc">Develop LLM and computer vision pipelines using PyTorch and FastAPI.</p>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_nk_02",
        received_at="2026-09-19T11:00:00Z",
        subject="Naukri Job Alerts",
        sender="naukrialerts@naukri.com",
        html_content=html_content,
    )
    jobs = NaukriEmailParser.parse(email)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "AI & Machine Learning Engineer"
    assert j.company == "Acme Corp"
    assert j.location == "Chennai"
    assert j.source_job_id == "nk_998877665544"
    assert "LLM and computer vision" in j.description


# ============================================================================
# 3. GLASSDOOR PLAIN-TEXT EMAIL PARSING
# ============================================================================

def test_glassdoor_plain_text_parsing():
    email = ParsedEmailData(
        message_id="msg_gd_01",
        received_at="2026-09-19T10:00:00Z",
        subject="Glassdoor Alert: New Data Scientist Jobs",
        sender="alerts@glassdoor.com",
        plain_text="""
        New job matched your search:
        Title: Data Scientist
        Link: https://www.glassdoor.com/job-listing/data-scientist-JV_IC1147401.htm?jl=10099887766
        """,
    )
    jobs = GlassdoorEmailParser.parse(email)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "Glassdoor Email Alert"
    assert j.source_job_id == "gd_10099887766"


# ============================================================================
# 4. GLASSDOOR HTML EMAIL PARSING
# ============================================================================

def test_glassdoor_html_email_parsing():
    html_content = """
    <html>
      <body>
        <div class="job-card">
          <a href="https://www.glassdoor.com/job-listing/lead-mlops-engineer-JV_IC1147401.htm?jl=8877665544">
            Lead MLOps Engineer
          </a>
          <div class="employer-name">DataScale Inc</div>
          <div class="location">Remote - US</div>
          <div class="snippet">Kubernetes, MLflow, and CI/CD automation</div>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_gd_02",
        received_at="2026-09-19T12:00:00Z",
        subject="Glassdoor Daily Digest",
        sender="noreply@glassdoor.com",
        html_content=html_content,
    )
    jobs = GlassdoorEmailParser.parse(email)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "Lead MLOps Engineer"
    assert j.company == "DataScale Inc"
    assert j.location == "Remote - US"
    assert j.source_job_id == "gd_8877665544"
    assert "Kubernetes" in j.description


# ============================================================================
# 5. MISSING OPTIONAL FIELDS
# ============================================================================

def test_missing_optional_fields():
    html_content = """
    <html>
      <body>
        <a href="https://www.naukri.com/job-listings-minimal-role-111111222222">Minimal Role Title</a>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_nk_03",
        received_at="2026-09-19T12:00:00Z",
        subject="Naukri Minimal",
        sender="naukri@naukri.com",
        html_content=html_content,
    )
    jobs = NaukriEmailParser.parse(email)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "Minimal Role Title"
    assert j.company == ""
    assert j.location == ""
    assert j.fingerprint is not None


# ============================================================================
# 6. MALFORMED EMAIL
# ============================================================================

def test_malformed_email():
    email = ParsedEmailData(
        message_id="msg_malformed",
        received_at="2026-09-19T12:00:00Z",
        subject="Broken Email",
        sender="bad@example.com",
        html_content="<><><invalid html body without any valid links>>>",
    )
    assert NaukriEmailParser.parse(email) == []
    assert GlassdoorEmailParser.parse(email) == []


# ============================================================================
# 7. IRRELEVANT EMAIL REJECTION
# ============================================================================

def test_irrelevant_email_rejection():
    email = ParsedEmailData(
        message_id="msg_marketing",
        received_at="2026-09-19T12:00:00Z",
        subject="Password Reset Confirmation",
        sender="no-reply@naukri.com",
        plain_text="Your password has been changed successfully. Click here to login: https://www.naukri.com/nlogin/login",
    )
    jobs = NaukriEmailParser.parse(email)
    assert len(jobs) == 0


# ============================================================================
# 8. SENDER / DOMAIN RECOGNITION
# ============================================================================

def test_sender_domain_recognition(mock_config):
    naukri_src = NaukriAlertEmailSource(query="from:(naukri.com) newer_than:2d")
    assert naukri_src.source_identifier == "naukri_email"
    assert naukri_src.is_enabled(mock_config) is True

    glassdoor_src = GlassdoorAlertEmailSource(query="from:(glassdoor.com) newer_than:2d")
    assert glassdoor_src.source_identifier == "glassdoor_email"
    assert glassdoor_src.is_enabled(mock_config) is True


# ============================================================================
# 9. SUBJECT RECOGNITION
# ============================================================================

def test_subject_recognition():
    email = ParsedEmailData(
        message_id="msg_subj",
        received_at="2026-09-19T12:00:00Z",
        subject="Recommended Jobs: 5 New Opportunities for AI Engineer",
        sender="jobalerts@naukri.com",
        plain_text="https://www.naukri.com/job-listings-ai-engineer-123456789000",
    )
    assert email.subject.startswith("Recommended Jobs")
    jobs = NaukriEmailParser.parse(email)
    assert len(jobs) == 1


# ============================================================================
# 10. URL EXTRACTION & CANONICALIZATION
# ============================================================================

def test_url_extraction_naukri_and_glassdoor():
    nk_url, nk_id = normalize_naukri_url("https://www.naukri.com/job-listings-deep-learning-expert-554433221100?src=jobsearch&sp=1")
    assert nk_id == "nk_554433221100"
    assert "src=jobsearch" not in nk_url

    gd_url, gd_id = normalize_glassdoor_url("https://www.glassdoor.com/job-listing/nlp-engineer-JV_IC1147401.htm?jl=99887766")
    assert gd_id == "gd_99887766"
    assert gd_url == "https://www.glassdoor.com/job-listing/?jl=99887766"


# ============================================================================
# 11. HTML ENTITY DECODING
# ============================================================================

def test_html_entity_decoding():
    html_content = """
    <html>
      <body>
        <a href="https://www.naukri.com/job-listings-r-amp-d-engineer-887766554433">R &amp; D Engineer &quot;AI&quot;</a>
        <span class="comp-name">AT&amp;T Inc.</span>
        <span class="loc">Bengaluru &amp; Remote</span>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_entities",
        received_at="2026-09-19T12:00:00Z",
        subject="Entities Test",
        sender="alerts@naukri.com",
        html_content=html_content,
    )
    jobs = NaukriEmailParser.parse(email)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == 'R & D Engineer "AI"'
    assert j.company == "AT&T Inc."
    assert j.location == "Bengaluru & Remote"


# ============================================================================
# 12. WHITESPACE NORMALIZATION
# ============================================================================

def test_whitespace_normalization():
    html_content = """
    <html>
      <body>
        <a href="https://www.glassdoor.com/job-listing/?jl=555444333">
          \n\n  Senior   Fullstack   Engineer  \n\t
        </a>
        <div class="employer-name">  Cloud   Scale   Inc  </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_ws",
        received_at="2026-09-19T12:00:00Z",
        subject="Whitespace",
        sender="alerts@glassdoor.com",
        html_content=html_content,
    )
    jobs = GlassdoorEmailParser.parse(email)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "Senior Fullstack Engineer"
    assert j.company == "Cloud Scale Inc"


# ============================================================================
# 13. MULTIPLE JOBS IN ONE EMAIL
# ============================================================================

def test_multiple_jobs_in_one_email():
    html_content = """
    <html>
      <body>
        <div class="item">
          <a href="https://www.naukri.com/job-listings-role-one-111111111111">Role One</a>
          <span class="comp-name">Company A</span>
        </div>
        <div class="item">
          <a href="https://www.naukri.com/job-listings-role-two-222222222222">Role Two</a>
          <span class="comp-name">Company B</span>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_multi",
        received_at="2026-09-19T12:00:00Z",
        subject="Multiple Jobs Alert",
        sender="naukrialerts@naukri.com",
        html_content=html_content,
    )
    jobs = NaukriEmailParser.parse(email)
    assert len(jobs) == 2
    assert jobs[0].title == "Role One"
    assert jobs[1].title == "Role Two"


# ============================================================================
# 14. DUPLICATE JOBS WITHIN THE SAME ALERT
# ============================================================================

def test_duplicate_jobs_within_same_alert():
    html_content = """
    <html>
      <body>
        <a href="https://www.glassdoor.com/job-listing/?jl=777888999">Backend Engineer</a>
        <a href="https://www.glassdoor.com/job-listing/?jl=777888999">Backend Engineer (Apply Now)</a>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_dup",
        received_at="2026-09-19T12:00:00Z",
        subject="Duplicate Alert",
        sender="alerts@glassdoor.com",
        html_content=html_content,
    )
    jobs = GlassdoorEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "gd_777888999"


# ============================================================================
# 15. CROSS-SOURCE FINGERPRINT COMPATIBILITY
# ============================================================================

def test_cross_source_fingerprint_compatibility():
    nk_email = ParsedEmailData(
        message_id="m_nk",
        received_at="2026-09-19T12:00:00Z",
        subject="Naukri Job",
        sender="alerts@naukri.com",
        html_content='<a href="https://www.naukri.com/job-listings-devops-lead-acme-corp-remote-123456789">DevOps Lead</a><span class="comp-name">Acme Corp</span><span class="loc">Remote</span>',
    )
    gd_email = ParsedEmailData(
        message_id="m_gd",
        received_at="2026-09-19T12:00:00Z",
        subject="Glassdoor Job",
        sender="alerts@glassdoor.com",
        html_content='<a href="https://www.glassdoor.com/job-listing/?jl=987654">DevOps Lead</a><div class="employer-name">Acme Corp</div><div class="location">Remote</div>',
    )

    nk_jobs = NaukriEmailParser.parse(nk_email)
    gd_jobs = GlassdoorEmailParser.parse(gd_email)

    assert len(nk_jobs) == 1
    assert len(gd_jobs) == 1

    # Same company, title, location -> identical Level 2 SHA-256 fingerprint
    assert nk_jobs[0].fingerprint == gd_jobs[0].fingerprint


# ============================================================================
# 16. LINKEDIN PARSER REGRESSION
# ============================================================================

def test_linkedin_parser_regression():
    html_content = """
    <html>
      <body>
        <a href="https://www.linkedin.com/comm/jobs/view/3912345678/?refId=abc">Staff AI Architect</a>
        <span class="company-name">DeepTech Solutions</span>
        <span class="location">Bengaluru, Karnataka, India</span>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_li_reg",
        received_at="2026-09-19T12:00:00Z",
        subject="LinkedIn Job Recommendations",
        sender="jobalerts-noreply@linkedin.com",
        html_content=html_content,
    )
    jobs = LinkedInEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "LinkedIn Email Alert"
    assert jobs[0].title == "Staff AI Architect"


# ============================================================================
# 17. INDEED PARSER REGRESSION
# ============================================================================

def test_indeed_parser_regression():
    html_content = """
    <html>
      <body>
        <a href="https://www.indeed.com/rc/clk?jk=1234567890abcdef&from=ja">Senior Data Engineer</a>
        <span class="companyName">BigData Systems</span>
        <span class="companyLocation">Pune, Maharashtra</span>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_ind_reg",
        received_at="2026-09-19T12:00:00Z",
        subject="Indeed Job Alert",
        sender="alert@indeed.com",
        html_content=html_content,
    )
    jobs = IndeedEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source == "Indeed Email Alert"
    assert jobs[0].title == "Senior Data Engineer"


# ============================================================================
# 18. GMAIL AUTHENTICATION REGRESSION
# ============================================================================

@patch("os.path.exists")
def test_gmail_auth_regression_missing_credentials(mock_exists):
    from app.sources.gmail.gmail_client import GmailAPIClient
    mock_exists.return_value = False
    client = GmailAPIClient(credentials_path="non_existent.json", token_path="non_existent_token.json")
    with pytest.raises(FileNotFoundError):
        client.authenticate()


# ============================================================================
# 19. DISABLED SOURCE BEHAVIOR
# ============================================================================

def test_disabled_source_behavior(mock_config):
    naukri_src = NaukriAlertEmailSource()
    glassdoor_src = GlassdoorAlertEmailSource()

    assert naukri_src.is_enabled(mock_config) is True
    assert glassdoor_src.is_enabled(mock_config) is True

    mock_config.source_naukri_enabled = False
    assert naukri_src.is_enabled(mock_config) is False

    mock_config.source_glassdoor_enabled = False
    assert glassdoor_src.is_enabled(mock_config) is False


# ============================================================================
# 20. PARSER FAILURE ISOLATION & REGISTRY INTEGRATION
# ============================================================================

@patch("app.sources.gmail.gmail_client.GmailAPIClient.search_messages")
@patch("app.sources.gmail.gmail_client.GmailAPIClient.get_message_detail")
@patch("app.sources.gmail.gmail_client.GmailAPIClient.decode_message_payload")
def test_parser_failure_isolation_and_registry(mock_decode, mock_get_detail, mock_search, mock_config):
    mock_search.return_value = [{"id": "msg_err_1"}, {"id": "msg_ok_1"}]
    mock_get_detail.side_effect = [Exception("API detail error"), {"id": "msg_ok_1"}]
    mock_decode.return_value = ParsedEmailData(
        message_id="msg_ok_1",
        received_at="2026-09-19T12:00:00Z",
        plain_text="https://www.naukri.com/job-listings-ok-role-999000111222",
    )

    naukri_src = NaukriAlertEmailSource()
    res = naukri_src.fetch_source_jobs()

    # Isolated failure: 1 email failed, 1 email succeeded -> PARTIAL_FAILURE, pipeline continues
    assert res.status == SourceStatus.PARTIAL_FAILURE
    assert res.total_fetched == 1
    assert res.jobs[0].title == "Ok Role"

    # Registry integration
    registry = create_default_source_registry(mock_config)
    registered_ids = [s.source_identifier for s in registry.list_sources()]
    assert "naukri_email" in registered_ids
    assert "glassdoor_email" in registered_ids
