"""
Unit tests for Phase 10.4 — Cutshort + Hirist Gmail Job Alert Ingestion.
Verifies plain text and HTML parsing, URL normalization, ID extraction (cs_<id>, hi_<id>),
fingerprint generation, failure isolation, registry integration, and regression across
Naukri, Glassdoor, Unstop, foundit, LinkedIn, Indeed, and Gmail auth.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.models import SourceStatus
from app.sources.gmail.email_parser import (
    CutshortEmailParser,
    GlassdoorEmailParser,
    HiristEmailParser,
    IndeedEmailParser,
    LinkedInEmailParser,
    NaukriEmailParser,
    UnstopEmailParser,
    classify_email,
    founditEmailParser,
    normalize_cutshort_url,
    normalize_hirist_url,
)
from app.sources.gmail.gmail_source import (
    CutshortAlertEmailSource,
    HiristAlertEmailSource,
)
from app.sources.gmail.models import ParsedEmailData
from app.sources.registry import create_default_source_registry


@pytest.fixture
def mock_config():
    return Config(
        adzuna_app_id="test_app_id",
        adzuna_app_key="test_app_key",
        source_cutshort_enabled=True,
        source_hirist_enabled=True,
        source_unstop_enabled=True,
        source_foundit_enabled=True,
        source_naukri_enabled=True,
        source_glassdoor_enabled=True,
        source_gmail_enabled=True,
    )


# ============================================================================
# 1. CUTSHORT PLAIN-TEXT PARSING
# ============================================================================

def test_cutshort_plain_text_parsing():
    email = ParsedEmailData(
        message_id="msg_cs_txt_1",
        received_at="2026-09-19T10:00:00Z",
        subject="Matching Role on Cutshort: Lead AI Engineer",
        sender="notifications@cutshort.io",
        plain_text="Check out this job: https://cutshort.io/job/Lead-AI-Engineer-Startup-1122334?ref=email_alert",
    )

    jobs = CutshortEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "Cutshort Email Alert"
    assert job.source_job_id == "cs_1122334"
    assert job.url == "https://cutshort.io/job/1122334"
    assert "Lead Ai Engineer" in job.title or "Lead AI Engineer" in job.title or "Cutshort" in job.title
    assert job.created_at == "2026-09-19T10:00:00Z"


# ============================================================================
# 2. CUTSHORT HTML PARSING
# ============================================================================

def test_cutshort_html_email_parsing():
    html_body = """
    <html>
      <body>
        <div class="job-card">
          <a class="job-title" href="https://cutshort.io/job/Senior-Backend-Engineer-Acme-7788990?src=recommend">
            Senior Backend Engineer
          </a>
          <span class="company-name">Acme Software</span>
          <span class="location">Bengaluru, Remote</span>
          <div class="description">Build distributed backend systems with Go and PostgreSQL.</div>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_cs_html_1",
        received_at="2026-09-19T11:00:00Z",
        subject="Your Daily Job Recommendations",
        sender="noreply@cutshort.io",
        html_content=html_body,
    )

    jobs = CutshortEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "Cutshort Email Alert"
    assert job.source_job_id == "cs_7788990"
    assert job.title == "Senior Backend Engineer"
    assert job.company == "Acme Software"
    assert job.location == "Bengaluru, Remote"
    assert "PostgreSQL" in job.description


# ============================================================================
# 3. HIRIST PLAIN-TEXT PARSING
# ============================================================================

def test_hirist_plain_text_parsing():
    email = ParsedEmailData(
        message_id="msg_hi_txt_1",
        received_at="2026-09-19T12:00:00Z",
        subject="Hirist Alert: Data Engineer",
        sender="alerts@hirist.tech",
        plain_text="View details for Data Engineer position: https://www.hirist.tech/j/data-engineer-cloud-tech-pune-889900.html?ref=email",
    )

    jobs = HiristEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "Hirist Email Alert"
    assert job.source_job_id == "hi_889900"
    assert job.url == "https://www.hirist.tech/j/889900"
    assert "Data Engineer" in job.title or "Hirist" in job.title


# ============================================================================
# 4. HIRIST HTML PARSING
# ============================================================================

def test_hirist_html_email_parsing():
    html_body = """
    <html>
      <body>
        <div class="job-container">
          <a class="job-title" href="https://www.hirist.tech/j/principal-architect-cloud-services-mumbai-665544.html">
            Principal Architect
          </a>
          <div class="company">Cloud Services Ltd</div>
          <div class="location">Mumbai</div>
          <div class="snippet">Seeking Principal Architect for cloud migration projects.</div>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_hi_html_1",
        received_at="2026-09-19T13:00:00Z",
        subject="Hirist Jobs Digest",
        sender="jobalert@hirist.com",
        html_content=html_body,
    )

    jobs = HiristEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "Hirist Email Alert"
    assert job.source_job_id == "hi_665544"
    assert job.title == "Principal Architect"
    assert job.company == "Cloud Services Ltd"
    assert job.location == "Mumbai"
    assert "cloud migration" in job.description


# ============================================================================
# 5. MISSING OPTIONAL FIELDS
# ============================================================================

def test_missing_optional_fields():
    email = ParsedEmailData(
        message_id="msg_minimal_cs",
        received_at="2026-09-19T14:00:00Z",
        subject="Job Alert",
        sender="alert@cutshort.io",
        plain_text="https://cutshort.io/job/minimal-role-334455",
    )

    jobs = CutshortEmailParser.parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == ""
    assert job.location == ""
    assert job.salary_min is None
    assert job.salary_max is None


# ============================================================================
# 6. MALFORMED CUTSHORT EMAIL
# ============================================================================

def test_malformed_cutshort_email():
    email = ParsedEmailData(
        message_id="msg_bad_cs",
        received_at="2026-09-19T15:00:00Z",
        subject="Broken Email",
        sender="alerts@cutshort.io",
        html_content="<div>Unclosed html with no valid urls <a href='invalid_url'>click here</a></div>",
    )

    jobs = CutshortEmailParser.parse(email)
    assert len(jobs) == 0


# ============================================================================
# 7. MALFORMED HIRIST EMAIL
# ============================================================================

def test_malformed_hirist_email():
    email = ParsedEmailData(
        message_id="msg_bad_hi",
        received_at="2026-09-19T15:00:00Z",
        subject="Malformed Hirist",
        sender="alerts@hirist.tech",
        plain_text="Invalid content with no hirist links present at all",
    )

    jobs = HiristEmailParser.parse(email)
    assert len(jobs) == 0


# ============================================================================
# 8. IRRELEVANT EMAIL REJECTION
# ============================================================================

def test_irrelevant_email_rejection():
    email = ParsedEmailData(
        message_id="msg_privacy",
        received_at="2026-09-19T16:00:00Z",
        subject="Update Privacy Settings",
        sender="support@cutshort.io",
        plain_text="Update your profile settings at https://cutshort.io/settings/privacy",
    )

    jobs = CutshortEmailParser.parse(email)
    assert len(jobs) == 0


# ============================================================================
# 9. CUTSHORT SENDER / DOMAIN RECOGNITION
# ============================================================================

def test_cutshort_sender_domain_recognition():
    email_com = ParsedEmailData(
        message_id="msg_cs_com",
        received_at="2026-09-19T16:30:00Z",
        subject="Matching Jobs",
        sender="alerts@cutshort.com",
        plain_text="https://cutshort.com/job/dev-role-556677",
    )

    assert CutshortEmailParser.is_cutshort_email(email_com) is True
    assert classify_email(email_com) == "cutshort_email"

    jobs = CutshortEmailParser.parse(email_com)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "cs_556677"


# ============================================================================
# 10. HIRIST SENDER / DOMAIN RECOGNITION
# ============================================================================

def test_hirist_sender_domain_recognition():
    email_tech = ParsedEmailData(
        message_id="msg_hi_tech",
        received_at="2026-09-19T17:00:00Z",
        subject="Hirist Digest",
        sender="jobalerts@hirist.tech",
        plain_text="https://www.hirist.tech/j/backend-role-223344.html",
    )

    assert HiristEmailParser.is_hirist_email(email_tech) is True
    assert classify_email(email_tech) == "hirist_email"

    jobs = HiristEmailParser.parse(email_tech)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "hi_223344"


# ============================================================================
# 11. SUBJECT CLASSIFICATION
# ============================================================================

def test_subject_classification():
    email = ParsedEmailData(
        message_id="msg_subj_cs",
        received_at="2026-09-19T17:30:00Z",
        subject="Cutshort Job Alert: DevOps Engineer",
        sender="alerts@cutshort.io",
        plain_text="https://cutshort.io/job/view-details-998877",
    )

    assert classify_email(email) == "cutshort_email"
    jobs = CutshortEmailParser.parse(email)
    assert len(jobs) == 1
    assert "DevOps Engineer" in jobs[0].title or "Cutshort" in jobs[0].title


# ============================================================================
# 12. URL EXTRACTION
# ============================================================================

def test_url_extraction_cutshort_and_hirist():
    url_cs, id_cs = normalize_cutshort_url("https://cutshort.io/job/Full-Stack-Dev-12345?ref=alert")
    assert url_cs == "https://cutshort.io/job/12345"
    assert id_cs == "cs_12345"

    url_hi, id_hi = normalize_hirist_url("https://www.hirist.tech/j/data-analyst-98765.html?src=alert")
    assert url_hi == "https://www.hirist.tech/j/98765"
    assert id_hi == "hi_98765"


# ============================================================================
# 13. URL NORMALIZATION
# ============================================================================

def test_url_normalization():
    clean_cs, id_cs = normalize_cutshort_url("https://cutshort.io/job/ai-lead-54321?jobId=54321&utm_source=email")
    assert clean_cs == "https://cutshort.io/job/54321"
    assert id_cs == "cs_54321"

    clean_hi, id_hi = normalize_hirist_url("https://www.hirist.tech/j/cloud-engineer-654321.html?ref=digest")
    assert clean_hi == "https://www.hirist.tech/j/654321"
    assert id_hi == "hi_654321"


# ============================================================================
# 14. HTML ENTITY DECODING
# ============================================================================

def test_html_entity_decoding():
    html_body = """
    <html>
      <body>
        <div>
          <a href="https://cutshort.io/job/c-plus-plus-dev-889900">
            C&amp;C&#43;&#43; Developer &gt; Tech Lead
          </a>
          <span class="company">R&amp;D Systems</span>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_entities_cs",
        received_at="2026-09-19T18:00:00Z",
        subject="Entities Test",
        sender="alerts@cutshort.io",
        html_content=html_body,
    )

    jobs = CutshortEmailParser.parse(email)
    assert len(jobs) == 1
    assert "C&C++ Developer > Tech Lead" in jobs[0].title
    assert "R&D Systems" in jobs[0].company


# ============================================================================
# 15. WHITESPACE NORMALIZATION
# ============================================================================

def test_whitespace_normalization():
    html_body = """
    <html>
      <body>
        <div>
          <a href="https://www.hirist.tech/j/cloud-architect-112233.html">
            \n\t  Cloud   Architect  \n
          </a>
          <div class="company">\n   NextGen   Cloud   Solutions  \n</div>
        </div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_whitespace_hi",
        received_at="2026-09-19T18:30:00Z",
        subject="Whitespace",
        sender="alerts@hirist.tech",
        html_content=html_body,
    )

    jobs = HiristEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].title == "Cloud Architect"
    assert jobs[0].company == "NextGen Cloud Solutions"


# ============================================================================
# 16. MULTIPLE JOBS IN ONE EMAIL
# ============================================================================

def test_multiple_jobs_in_one_email():
    html_body = """
    <html>
      <body>
        <div><a href="https://cutshort.io/job/role-a-1111">Role A</a><span class="company">Comp A</span></div>
        <div><a href="https://cutshort.io/job/role-b-2222">Role B</a><span class="company">Comp B</span></div>
        <div><a href="https://cutshort.io/job/role-c-3333">Role C</a><span class="company">Comp C</span></div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_multi_cs",
        received_at="2026-09-19T19:00:00Z",
        subject="3 New Jobs",
        sender="alerts@cutshort.io",
        html_content=html_body,
    )

    jobs = CutshortEmailParser.parse(email)
    assert len(jobs) == 3
    assert jobs[0].source_job_id == "cs_1111"
    assert jobs[1].source_job_id == "cs_2222"
    assert jobs[2].source_job_id == "cs_3333"


# ============================================================================
# 17. DUPLICATE JOBS WITHIN SAME ALERT
# ============================================================================

def test_duplicate_jobs_within_same_alert():
    html_body = """
    <html>
      <body>
        <div><a href="https://www.hirist.tech/j/dup-role-99999.html">Role Dup</a></div>
        <div><a href="https://www.hirist.tech/j/dup-role-99999.html?ref=card">Role Dup</a></div>
      </body>
    </html>
    """
    email = ParsedEmailData(
        message_id="msg_dup_hi",
        received_at="2026-09-19T19:30:00Z",
        subject="Duplicate Link",
        sender="alerts@hirist.tech",
        html_content=html_body,
    )

    jobs = HiristEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "hi_99999"


# ============================================================================
# 18. CROSS-SOURCE FINGERPRINT COMPATIBILITY
# ============================================================================

def test_cross_source_fingerprint_compatibility():
    email_cs = ParsedEmailData(
        message_id="msg_cs_fp",
        received_at="2026-09-19T20:00:00Z",
        subject="Role",
        sender="alerts@cutshort.io",
        html_content='<div><a href="https://cutshort.io/job/role-123">AI Engineer</a><span class="company">Microsoft</span><span class="location">Remote</span></div>',
    )
    email_hi = ParsedEmailData(
        message_id="msg_hi_fp",
        received_at="2026-09-19T20:00:00Z",
        subject="Role",
        sender="alerts@hirist.tech",
        html_content='<div><a href="https://www.hirist.tech/j/role-456.html">AI Engineer</a><span class="company">Microsoft</span><span class="location">Remote</span></div>',
    )

    job_cs = CutshortEmailParser.parse(email_cs)[0]
    job_hi = HiristEmailParser.parse(email_hi)[0]

    assert job_cs.fingerprint == job_hi.fingerprint


# ============================================================================
# 19. SOURCE ENABLED / DISABLED BEHAVIOR
# ============================================================================

def test_source_enabled_disabled_behavior(mock_config):
    cs_src = CutshortAlertEmailSource()
    hi_src = HiristAlertEmailSource()

    assert cs_src.is_enabled(mock_config) is True
    assert hi_src.is_enabled(mock_config) is True

    mock_config.source_cutshort_enabled = False
    assert cs_src.is_enabled(mock_config) is False

    mock_config.source_hirist_enabled = False
    assert hi_src.is_enabled(mock_config) is False


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
        plain_text="https://cutshort.io/job/ok-role-777888",
    )

    cs_src = CutshortAlertEmailSource()
    res = cs_src.fetch_source_jobs()

    assert res.status == SourceStatus.PARTIAL_FAILURE
    assert res.total_fetched == 1
    assert res.jobs[0].source_job_id == "cs_777888"

    registry = create_default_source_registry(mock_config)
    source_ids = [s.source_identifier for s in registry.list_sources()]
    assert "cutshort_email" in source_ids
    assert "hirist_email" in source_ids


# ============================================================================
# 21. NAUKRI REGRESSION
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
# 22. GLASSDOOR REGRESSION
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
# 23. UNSTOP REGRESSION
# ============================================================================

def test_unstop_parser_regression():
    email = ParsedEmailData(
        message_id="msg_un_regr",
        received_at="2026-09-19T21:20:00Z",
        subject="Unstop Alert",
        sender="alerts@unstop.com",
        plain_text="https://unstop.com/o/role-998877",
    )
    jobs = UnstopEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "un_998877"


# ============================================================================
# 24. FOUNDIT REGRESSION
# ============================================================================

def test_foundit_parser_regression():
    email = ParsedEmailData(
        message_id="msg_fm_regr",
        received_at="2026-09-19T21:25:00Z",
        subject="foundit Alert",
        sender="alerts@foundit.in",
        plain_text="https://www.foundit.in/job/role-887766",
    )
    jobs = founditEmailParser.parse(email)
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "fm_887766"


# ============================================================================
# 25. LINKEDIN REGRESSION
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
# 26. INDEED REGRESSION
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
# 27. GMAIL AUTHENTICATION REGRESSION
# ============================================================================

@patch("os.path.exists")
def test_gmail_auth_regression(mock_exists):
    from app.sources.gmail.gmail_client import GmailAPIClient
    mock_exists.return_value = False
    client = GmailAPIClient(credentials_path="non_existent.json", token_path="non_existent_token.json")
    with pytest.raises(FileNotFoundError):
        client.authenticate()
