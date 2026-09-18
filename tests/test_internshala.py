"""
Unit tests for InternshalaJobSource HTML parsing, network failure handling,
rate limiting, URL normalization, and SourceResult status.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app.db.models import SourceStatus
from app.services.normalization import normalize_internshala_job, parse_stipend_range
from app.sources.internshala import InternshalaJobSource, normalize_internshala_url


SAMPLE_INTERNSHALA_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="individual_internship" data-id="101" data-href="/internship/detail/machine-learning-intern-101">
    <div class="heading_4_5 profile">
        <a href="/internship/detail/machine-learning-intern-101?utm_source=hp">Machine Learning Intern</a>
    </div>
    <div class="heading_6 company_name">
        <a href="/company/ai-innovations">AI Innovations Labs</a>
    </div>
    <div id="location_names">
        <a class="location_link" href="/internships/in-bangalore">Bangalore</a>
    </div>
    <div class="stipend_container">
        <span class="stipend">₹ 15,000 /month</span>
    </div>
    <div class="label_container">
        <span class="status-container">Internship</span>
    </div>
    <div class="posted_by_container">
        <span class="status-success">Posted 2 days ago</span>
    </div>
    <div class="internship_other_details_container">
        Work on deep learning and NLP models.
    </div>
</div>

<div class="individual_internship" data-id="102" data-href="/job/detail/data-scientist-102">
    <div class="heading_4_5 profile">
        <a href="/job/detail/data-scientist-102">Junior Data Scientist</a>
    </div>
    <div class="heading_6 company_name">
        <a href="/company/analytics-corp">Analytics Corp</a>
    </div>
    <div id="location_names">
        <span class="location">Remote</span>
    </div>
    <div class="stipend_container">
        <span class="stipend">₹ 25,000-35,000 /month</span>
    </div>
    <div class="label_container">
        <span class="status-container">Fresher Job</span>
    </div>
    <div class="posted_by_container">
        <span class="status-success">Just now</span>
    </div>
    <div class="internship_other_details_container">
        Build predictive models using Python.
    </div>
</div>
</body>
</html>
"""

MISSING_FIELDS_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="individual_internship" data-href="/internship/detail/ai-researcher">
    <div class="heading_4_5 profile">
        <a href="/internship/detail/ai-researcher">AI Researcher</a>
    </div>
    <!-- Missing company, location, stipend, posted date -->
</div>
</body>
</html>
"""

MALFORMED_CARD_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="individual_internship">
    <!-- Card without any profile title or link -->
    <div class="some_other_div">No title here</div>
</div>
</body>
</html>
"""

CLOUDFLARE_CHALLENGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Attention Required! | Cloudflare</title></head>
<body>
    <h1>Security Check</h1>
    <p>Please solve the captcha to continue. cf-browser-verification</p>
</body>
</html>
"""

EMPTY_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="no_results">No internships found matching your criteria.</div>
</body>
</html>
"""


def test_normalize_internshala_url():
    """Test URL normalization cleans tracking parameters and ensures absolute format."""
    raw = "/internship/detail/ml-intern-123?utm_source=search&ref=job_board#section"
    clean = normalize_internshala_url(raw)
    assert clean == "https://internshala.com/internship/detail/ml-intern-123"

    raw_abs = "https://internshala.com/job/detail/ds-456?tracker=abc"
    clean_abs = normalize_internshala_url(raw_abs)
    assert clean_abs == "https://internshala.com/job/detail/ds-456"

    assert normalize_internshala_url("") == ""


def test_parse_stipend_range():
    """Test stipend string parsing into numeric min, max, and currency."""
    smin, smax, curr = parse_stipend_range("₹ 10,000 /month")
    assert smin == 10000.0
    assert smax == 10000.0
    assert curr == "INR"

    smin, smax, curr = parse_stipend_range("₹ 15,000 - 25,000 /month")
    assert smin == 15000.0
    assert smax == 25000.0
    assert curr == "INR"

    smin, smax, curr = parse_stipend_range("Unpaid")
    assert smin == 0.0
    assert smax == 0.0
    assert curr == "INR"

    smin, smax, curr = parse_stipend_range("Not disclosed")
    assert smin is None
    assert smax is None


def test_parse_html_listings_normal():
    """Test parsing a normal Internshala HTML page with multiple listing cards."""
    source = InternshalaJobSource()
    cards = source.parse_html_listings(SAMPLE_INTERNSHALA_HTML)

    assert len(cards) == 2

    c1 = cards[0]
    assert c1["source_job_id"] == "101"
    assert c1["title"] == "Machine Learning Intern"
    assert c1["company"] == "AI Innovations Labs"
    assert c1["location"] == "Bangalore"
    assert c1["url"] == "https://internshala.com/internship/detail/machine-learning-intern-101"
    assert c1["salary_text"] == "₹ 15,000 /month"
    assert c1["employment_type"] == "Internship"

    c2 = cards[1]
    assert c2["source_job_id"] == "102"
    assert c2["title"] == "Junior Data Scientist"
    assert c2["company"] == "Analytics Corp"
    assert c2["location"] == "Remote"
    assert c2["url"] == "https://internshala.com/job/detail/data-scientist-102"


def test_parse_html_listings_missing_fields():
    """Test parsing cards with missing optional fields."""
    source = InternshalaJobSource()
    cards = source.parse_html_listings(MISSING_FIELDS_HTML)

    assert len(cards) == 1
    c = cards[0]
    assert c["title"] == "AI Researcher"
    assert c["company"] == ""
    assert c["location"] == ""
    # Should derive deterministic hash ID starting with 'ish_' when data-id is missing
    assert c["source_job_id"].startswith("ish_")


def test_parse_html_listings_malformed():
    """Test parsing card with missing title element does not crash and skips bad card."""
    source = InternshalaJobSource()
    cards = source.parse_html_listings(MALFORMED_CARD_HTML)
    assert len(cards) == 0


def test_normalize_internshala_job_model():
    """Test normalizing raw dictionary into internal Job model."""
    raw = {
        "source_job_id": "202",
        "title": "Computer Vision Specialist",
        "company": "Vision Works",
        "location": "Chennai",
        "url": "https://internshala.com/internship/detail/cv-202",
        "salary_text": "₹ 20,000 /month",
        "employment_type": "Internship",
        "created_at": "Posted 1 day ago",
        "description": "Develop OpenCV and PyTorch solutions.",
    }

    job = normalize_internshala_job(raw)
    assert job.source == "Internshala"
    assert job.source_job_id == "202"
    assert job.title == "Computer Vision Specialist"
    assert job.company == "Vision Works"
    assert job.location == "Chennai"
    assert job.salary_min == 20000.0
    assert job.salary_currency == "INR"
    assert job.fingerprint is not None


@patch("app.sources.internshala.requests.get")
def test_fetch_source_jobs_success(mock_get):
    """Test successful Internshala fetch across keywords."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_INTERNSHALA_HTML
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    mock_sleep = MagicMock()
    source = InternshalaJobSource(
        request_delay_min=0.1,
        request_delay_max=0.2,
        sleep_fn=mock_sleep,
    )

    result = source.fetch_source_jobs(keywords=["machine learning", "data science"], max_pages=1)

    assert result.status == SourceStatus.SUCCESS
    assert result.total_fetched == 4  # 2 jobs x 2 keywords
    assert len(result.jobs) == 4
    # Ensure sleep_fn was called for rate limiting between requests
    assert mock_sleep.called


@patch("app.sources.internshala.requests.get")
def test_fetch_source_jobs_blocked_403(mock_get):
    """Test gracefully catching HTTP 403 forbidden without crashing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden"
    mock_get.return_value = mock_resp

    source = InternshalaJobSource(sleep_fn=MagicMock())
    result = source.fetch_source_jobs(keywords=["AI engineer"], max_pages=1)

    assert result.status == SourceStatus.BLOCKED
    assert result.total_fetched == 0
    assert result.error_message is not None


@patch("app.sources.internshala.requests.get")
def test_fetch_source_jobs_cloudflare_challenge(mock_get):
    """Test detecting Cloudflare challenge in HTML body."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = CLOUDFLARE_CHALLENGE_HTML
    mock_get.return_value = mock_resp

    source = InternshalaJobSource(sleep_fn=MagicMock())
    result = source.fetch_source_jobs(keywords=["deep learning"], max_pages=1)

    assert result.status == SourceStatus.BLOCKED
    assert result.total_fetched == 0


@patch("app.sources.internshala.requests.get")
def test_fetch_source_jobs_network_error(mock_get):
    """Test handling network connection error gracefully."""
    mock_get.side_effect = requests.exceptions.ConnectionError("Failed to connect")

    source = InternshalaJobSource(sleep_fn=MagicMock())
    result = source.fetch_source_jobs(keywords=["Python"], max_pages=1)

    assert result.status == SourceStatus.FAILED
    assert result.total_fetched == 0
    assert "Network error" in result.error_message
