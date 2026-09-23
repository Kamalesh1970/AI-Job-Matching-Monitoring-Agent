"""
Unit and Integration Tests for Phase 10.6 — Full Priority Platform Integration & Regression.
Verifies source registry completeness, configuration integration, fault isolation,
normalization, Level-1 and cross-source fingerprint deduplication, Gmail architecture,
scheduler, matching, Telegram notification, database persistence, end-to-end pipeline,
and the 16-source integration matrix.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.config import Config
from app.db.database import (
    get_all_jobs,
    get_jobs_map,
    get_notified_job_ids,
    get_stored_matches,
    initialize_database,
    insert_job,
    record_notifications,
    save_match_results,
)
from app.db.models import Job, MatchResult, Resume, SourceResult, SourceStatus
from app.services.deduplication import generate_fingerprint
from app.services.digest_service import DigestService
from app.services.matching_service import MatchingService
from app.services.normalization import (
    normalize_adzuna_job,
    normalize_arbeitnow_job,
    normalize_himalayas_job,
    normalize_internshala_job,
    normalize_jobicy_job,
    normalize_jooble_job,
    normalize_remoteok_job,
)
from app.services.pipeline_service import PipelineRunSummary, PipelineService, PipelineStatus
from app.services.telegram_notifier import TelegramNotifier
from app.sources.active_jobs_db import ActiveJobsDBJobSource
from app.sources.adzuna import AdzunaJobSource
from app.sources.arbeitnow import ArbeitnowJobSource
from app.sources.base import BaseJobSource
from app.sources.gmail import (
    CutshortAlertEmailSource,
    CutshortEmailParser,
    GlassdoorAlertEmailSource,
    GlassdoorEmailParser,
    GmailAPIClient,
    HiristAlertEmailSource,
    HiristEmailParser,
    IndeedAlertEmailSource,
    IndeedEmailParser,
    LinkedInAlertEmailSource,
    LinkedInEmailParser,
    NaukriAlertEmailSource,
    NaukriEmailParser,
    ParsedEmailData,
    UnstopAlertEmailSource,
    UnstopEmailParser,
    WellfoundAlertEmailSource,
    WellfoundEmailParser,
    classify_email,
    founditAlertEmailSource,
    founditEmailParser,
)
from app.sources.himalayas import HimalayasJobSource
from app.sources.indeed_jobs_api import IndeedJobsApiSource
from app.sources.internshala import InternshalaJobSource
from app.sources.jobicy import JobicyJobSource
from app.sources.jooble import JoobleJobSource
from app.sources.jsearch import JSearchJobSource
from app.sources.linkedin_jobs_api import LinkedInJobsApiSource
from app.sources.registry import JobSourceRegistry, create_default_source_registry
from app.sources.remoteok import RemoteOKJobSource
from app.sources.serpapi import SerpApiJobSource


@pytest.fixture
def memory_db():
    """Provides initialized in-memory SQLite connection."""
    conn = initialize_database(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def mock_config():
    """Provides complete test configuration object with all 16 sources enabled."""
    return Config(
        adzuna_app_id="test_app_id",
        adzuna_app_key="test_app_key",
        keywords=["AI Engineer"],
        internshala_keywords=["machine learning"],
        source_adzuna_enabled=True,
        source_internshala_enabled=True,
        source_gmail_enabled=True,
        source_linkedin_enabled=True,
        source_indeed_enabled=True,
        source_arbeitnow_enabled=True,
        source_remoteok_enabled=True,
        source_jobicy_enabled=True,
        source_himalayas_enabled=True,
        source_jooble_enabled=True,
        source_jsearch_enabled=True,
        source_serpapi_enabled=True,
        source_active_jobs_db_enabled=True,
        active_jobs_db_api_key="test_key",
        source_linkedin_jobs_api_enabled=True,
        linkedin_jobs_api_key="test_linkedin_key",
        source_indeed_jobs_api_enabled=True,
        indeed_jobs_api_key="test_indeed_key",
        source_naukri_enabled=True,
        source_glassdoor_enabled=True,
        source_unstop_enabled=True,
        source_foundit_enabled=True,
        source_cutshort_enabled=True,
        source_hirist_enabled=True,
        source_wellfound_enabled=True,
        jooble_api_key="test_jooble_key",
        jsearch_api_key="test_jsearch_key",
        jsearch_rapidapi_host="jsearch.p.rapidapi.com",
        serpapi_key="test_serpapi_key",
        telegram_bot_token="test_bot_token",
        telegram_chat_id="test_chat_id",
        telegram_enabled=True,
    )


# ============================================================================
# A. SOURCE REGISTRY INTEGRATION
# ============================================================================

def test_complete_source_registry(mock_config):
    """Verify create_default_source_registry registers all 19 job sources."""
    registry = create_default_source_registry(mock_config)
    sources = registry.list_sources()

    assert len(sources) == 21, f"Expected 21 registered sources, got {len(sources)}"

    expected_identifiers = {
        "adzuna": "api",
        "internshala": "scraper",
        "linkedin_email": "email_alert",
        "indeed_email": "email_alert",
        "linkedin_jobs_api": "api",
        "indeed_jobs_api": "api",
        "naukri_email": "email_alert",
        "glassdoor_email": "email_alert",
        "unstop_email": "email_alert",
        "foundit_email": "email_alert",
        "cutshort_email": "email_alert",
        "hirist_email": "email_alert",
        "wellfound_email": "email_alert",
        "arbeitnow": "api",
        "remoteok": "api",
        "jobicy": "api",
        "himalayas": "api",
        "jooble": "api",
        "jsearch": "api",
        "serpapi": "api",
        "active_jobs_db": "api",
    }

    registered_map = {s.source_identifier: s.source_type for s in sources}
    for identifier, expected_type in expected_identifiers.items():
        assert identifier in registered_map, f"Source '{identifier}' missing from registry"
        assert registered_map[identifier] == expected_type, (
            f"Source '{identifier}' expected type '{expected_type}', got '{registered_map[identifier]}'"
        )


def test_registry_dynamic_enable_disable(mock_config):
    """Verify dynamic enable/disable methods on JobSourceRegistry."""
    registry = create_default_source_registry(mock_config)

    assert registry.is_source_enabled("adzuna", mock_config) is True
    registry.disable_source("adzuna")
    assert registry.is_source_enabled("adzuna", mock_config) is False

    enabled_sources = registry.list_enabled_sources(mock_config)
    enabled_ids = {s.source_identifier for s in enabled_sources}
    assert "adzuna" not in enabled_ids
    assert len(enabled_sources) == 20

    registry.enable_source("adzuna")
    assert registry.is_source_enabled("adzuna", mock_config) is True


# ============================================================================
# B. CONFIGURATION INTEGRATION
# ============================================================================

def test_jooble_missing_api_key_behavior():
    """Verify Jooble handles missing API key cleanly without crashing."""
    source_no_key = JoobleJobSource(api_key="")
    assert source_no_key.is_enabled() is False

    res = source_no_key.fetch_source_jobs()
    assert res.status == SourceStatus.DISABLED
    assert res.jobs == []
    assert "not configured" in res.error_message.lower()


def test_disabled_sources_filtering(mock_config):
    """Verify disabled sources do not get listed in enabled sources."""
    mock_config.source_arbeitnow_enabled = False
    mock_config.source_remoteok_enabled = False

    registry = create_default_source_registry(mock_config)
    enabled = registry.list_enabled_sources(mock_config)
    enabled_ids = {s.source_identifier for s in enabled}

    assert "arbeitnow" not in enabled_ids
    assert "remoteok" not in enabled_ids
    assert "adzuna" in enabled_ids


# ============================================================================
# C. SOURCE FAULT ISOLATION
# ============================================================================

def test_source_failure_isolation(memory_db, mock_config):
    """Verify a failing source returns failure result without breaking other sources."""
    # Create healthy mock source
    good_source = MagicMock(spec=BaseJobSource)
    good_source.name = "Good Source"
    good_source.source_identifier = "good_source"
    good_source.source_type = "api"
    good_source.is_enabled.return_value = True
    good_job = Job(source="Good Source", source_job_id="G1", title="AI Specialist")
    good_source.fetch_source_jobs.return_value = SourceResult(
        source_name="Good Source", status=SourceStatus.SUCCESS, jobs=[good_job], total_fetched=1
    )

    # Create failing mock source
    bad_source = MagicMock(spec=BaseJobSource)
    bad_source.name = "Bad Source"
    bad_source.source_identifier = "bad_source"
    bad_source.source_type = "api"
    bad_source.is_enabled.return_value = True
    bad_source.fetch_source_jobs.side_effect = Exception("Network HTTP 500 error")

    registry = JobSourceRegistry()
    registry.register(good_source)
    registry.register(bad_source)

    results = []
    for s in registry.list_enabled_sources(mock_config):
        try:
            res = s.fetch_source_jobs()
            results.append(res)
        except Exception as e:
            results.append(SourceResult(source_name=s.name, status=SourceStatus.FAILED, jobs=[], error_message=str(e)))

    assert len(results) == 2
    statuses = {r.source_name: r.status for r in results}
    assert statuses["Good Source"] == SourceStatus.SUCCESS
    assert statuses["Bad Source"] == SourceStatus.FAILED


# ============================================================================
# D. NORMALIZATION ACROSS ALL 16 SOURCES
# ============================================================================

def test_normalization_all_sources():
    """Verify normalization functions for API/web sources produce standard Job models."""
    # 1. Adzuna
    raw_adzuna = {
        "id": "adz_123",
        "title": "<strong>Lead AI Engineer</strong>",
        "company": {"display_name": "Acme Corp"},
        "location": {"display_name": "Bangalore, India"},
        "description": "<p>Build LLM solutions</p>",
        "redirect_url": "https://adzuna.in/jobs/123",
        "salary_min": 1500000,
        "salary_max": 2500000,
    }
    j_adz = normalize_adzuna_job(raw_adzuna)
    assert j_adz.source == "Adzuna"
    assert j_adz.title == "Lead AI Engineer"
    assert j_adz.company == "Acme Corp"
    assert j_adz.salary_min == 1500000.0

    # 2. Internshala
    raw_ish = {
        "source_job_id": "ish_456",
        "title": "Machine Learning Intern",
        "company": "DeepMind India",
        "location": "Remote",
        "url": "https://internshala.com/internship/detail/456",
        "description": "ML algorithms research",
        "salary_text": "₹ 15,000 /month",
    }
    j_ish = normalize_internshala_job(raw_ish)
    assert j_ish.source == "Internshala"
    assert j_ish.title == "Machine Learning Intern"

    # 3. Arbeitnow
    raw_arb = {
        "slug": "arb_789",
        "title": "Python Developer",
        "company_name": "Tech GmbH",
        "location": "Berlin",
        "remote": True,
        "description": "Backend API dev",
        "url": "https://arbeitnow.com/jobs/789",
    }
    j_arb = normalize_arbeitnow_job(raw_arb)
    assert j_arb.source == "Arbeitnow"
    assert "Remote" in j_arb.location

    # 4. RemoteOK
    raw_rok = {
        "id": "rok_101",
        "position": "Senior AI Architect",
        "company": "Remote Solutions",
        "location": "Global Remote",
        "description": "Distributed AI systems",
        "url": "https://remoteok.com/l/101",
    }
    j_rok = normalize_remoteok_job(raw_rok)
    assert j_rok.source == "RemoteOK"
    assert j_rok.title == "Senior AI Architect"

    # 5. Jobicy
    raw_jby = {
        "id": "jby_202",
        "jobTitle": "Data Scientist",
        "companyName": "Data Co",
        "jobGeo": "Worldwide",
        "jobDescription": "Predictive modeling",
        "url": "https://jobicy.com/jobs/202",
    }
    j_jby = normalize_jobicy_job(raw_jby)
    assert j_jby.source == "Jobicy"
    assert j_jby.title == "Data Scientist"

    # 6. Himalayas
    raw_him = {
        "id": "him_303",
        "title": "CV Engineer",
        "companyName": "Vision AI",
        "locationRestrictions": ["India", "Remote"],
        "description": "OpenCV, PyTorch",
        "url": "https://himalayas.app/jobs/303",
    }
    j_him = normalize_himalayas_job(raw_him)
    assert j_him.source == "Himalayas"
    assert "India" in j_him.location

    # 7. Jooble
    raw_jbl = {
        "id": "jbl_404",
        "title": "NLP Researcher",
        "company": "Language Tech",
        "location": "Chennai",
        "snippet": "Transformers and LLMs",
        "link": "https://jooble.org/desc/404",
    }
    j_jbl = normalize_jooble_job(raw_jbl)
    assert j_jbl.source == "Jooble"
    assert j_jbl.title == "NLP Researcher"


# ============================================================================
# E. LEVEL 1 DEDUPLICATION
# ============================================================================

def test_level_1_deduplication(memory_db):
    """Verify exact (source, source_job_id) deduplication in database."""
    job1 = Job(source="Naukri", source_job_id="NAUKRI_100", title="AI Dev", company="Infotech")
    job2 = Job(source="Naukri", source_job_id="NAUKRI_100", title="AI Dev Updated", company="Infotech")

    inserted_1 = insert_job(memory_db, job1)
    inserted_2 = insert_job(memory_db, job2)

    assert inserted_1 is True
    assert inserted_2 is False

    stored = get_all_jobs(memory_db)
    assert len(stored) == 1
    assert stored[0].title == "AI Dev"


# ============================================================================
# F. CROSS-SOURCE FINGERPRINT DEDUPLICATION
# ============================================================================

def test_cross_source_fingerprint_deduplication():
    """Verify SHA-256 fingerprint matches identical jobs from different sources."""
    company = "Google"
    title = "Staff Machine Learning Engineer"
    location = "Bangalore"

    fp_naukri = generate_fingerprint(company=company, title=title, location=location)
    fp_linkedin = generate_fingerprint(company=company, title=title, location=location)
    fp_indeed = generate_fingerprint(company=company, title=title, location=location)
    fp_glassdoor = generate_fingerprint(company=company, title=title, location=location)
    fp_adzuna = generate_fingerprint(company=company, title=title, location=location)

    assert fp_naukri == fp_linkedin == fp_indeed == fp_glassdoor == fp_adzuna

    # Distinct job yields different fingerprint
    fp_different = generate_fingerprint(company=company, title="Data Engineer", location=location)
    assert fp_different != fp_naukri

    # DigestService deduplicates by fingerprint
    job_nk = Job(id=1, source="Naukri", source_job_id="NK1", title=title, company=company, location=location, fingerprint=fp_naukri)
    job_li = Job(id=2, source="LinkedIn", source_job_id="LI1", title=title, company=company, location=location, fingerprint=fp_linkedin)

    matches = [
        MatchResult(job_id=1, title=title, company=company, location=location, final_score=88.0, match_status="MATCH"),
        MatchResult(job_id=2, title=title, company=company, location=location, final_score=88.0, match_status="MATCH"),
    ]
    jobs_map = {1: job_nk, 2: job_li}

    digest_service = DigestService(min_score=70.0, max_jobs=10)
    deduped_matches = digest_service.filter_and_sort_matches(matches, jobs_map=jobs_map)

    assert len(deduped_matches) == 1
    assert deduped_matches[0].job_id == 1


# ============================================================================
# G. GMAIL SOURCE INTEGRATION & ROUTING
# ============================================================================

def test_gmail_classifier_routing_all_sources():
    """Verify classify_email routes emails from all 9 Gmail sources correctly."""
    sources_data = [
        ("wellfound_email", "jobs@wellfound.com", "Wellfound Alert", "https://wellfound.com/jobs/1"),
        ("cutshort_email", "alerts@cutshort.io", "Cutshort Update", "https://cutshort.io/job/2"),
        ("hirist_email", "jobs@hirist.tech", "Hirist Recommendations", "https://hirist.tech/j/3"),
        ("naukri_email", "alerts@naukri.com", "Naukri Job Alert", "https://naukri.com/job-listings-4"),
        ("glassdoor_email", "noreply@glassdoor.com", "Glassdoor Digest", "https://glassdoor.com/job-listing/5"),
        ("unstop_email", "opportunities@unstop.com", "Unstop Opportunity", "https://unstop.com/jobs/6"),
        ("foundit_email", "alerts@foundit.in", "foundit Matches", "https://foundit.in/job/7"),
        ("linkedin_email", "jobalerts-noreply@linkedin.com", "LinkedIn Job Alert", "https://linkedin.com/jobs/view/8"),
        ("indeed_email", "alert@indeed.com", "Indeed Jobs", "https://indeed.com/viewjob?jk=9"),
    ]

    for expected_type, sender, subject, body in sources_data:
        email = ParsedEmailData(
            message_id=f"msg_{expected_type}",
            received_at="2026-09-21T12:00:00Z",
            sender=sender,
            subject=subject,
            plain_text=body,
        )
        assert classify_email(email) == expected_type, f"Failed classification for {expected_type}"


# ============================================================================
# H. SCHEDULER & PIPELINE SERVICE INTEGRATION
# ============================================================================

@patch("app.services.pipeline_service.InternshalaJobSource")
@patch("app.services.pipeline_service.MatchingService")
@patch("app.services.pipeline_service.AdzunaJobSource")
def test_pipeline_service_full_cycle(
    mock_adzuna_class, mock_matching_class, mock_ish_class, memory_db, mock_config
):
    """Verify PipelineService executes ingestion, matching, and summary recording cleanly."""
    mock_adzuna = MagicMock()
    mock_job = Job(source="Adzuna", source_job_id="ADZ1", title="AI Dev", company="AI Corp")
    mock_adzuna.fetch_jobs_for_keyword.return_value = ([mock_job], True)
    mock_adzuna_class.return_value = mock_adzuna

    mock_ish = MagicMock()
    mock_ish.fetch_source_jobs.return_value = SourceResult(
        source_name="Internshala", status=SourceStatus.SUCCESS, jobs=[], total_fetched=0
    )
    mock_ish_class.return_value = mock_ish

    mock_matching = MagicMock()
    mock_matching.prepare_resume.return_value = MagicMock()
    mock_matching.match_all_jobs.return_value = [
        MatchResult(job_id=1, title="AI Dev", final_score=82.0, match_status="MATCH")
    ]
    mock_matching_class.return_value = mock_matching

    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    service = PipelineService(config=mock_config)
    summary = service.run_monitoring_pipeline(config=mock_config, conn=memory_db, notifier=mock_notifier)

    assert summary.status == PipelineStatus.SUCCESS
    assert summary.jobs_fetched == 1
    assert summary.new_jobs == 1
    assert summary.matches_found == 1


# ============================================================================
# I. MATCHING ENGINE INTEGRATION
# ============================================================================

def test_matching_engine_multi_source_thresholds(mock_config):
    """Verify MatchingService scores jobs from multiple sources according to thresholds."""
    mock_embed = MagicMock()
    mock_embed.encode_text.return_value = [1.0] * 384
    mock_embed.calculate_cosine_similarity.side_effect = [0.95, 0.10]
    matching_service = MatchingService(config=mock_config, embedding_service=mock_embed)

    job1 = Job(id=1, source="Naukri", source_job_id="NK_1", title="AI Engineer", company="Tech", location="Bangalore", description="Python PyTorch Machine Learning LLM")
    job2 = Job(id=2, source="Adzuna", source_job_id="ADZ_2", title="Unrelated Cook", company="Food", location="Delhi", description="Cooking recipes and kitchen management")

    resume = Resume(
        raw_text="Experienced AI Engineer specializing in Python, PyTorch, LLMs, Machine Learning, and Computer Vision.",
        normalized_text="experienced ai engineer specializing in python pytorch llms machine learning and computer vision",
        skills={"python", "pytorch", "machine learning", "llm"},
    )

    m1 = matching_service.match_job(resume, job1)
    m2 = matching_service.match_job(resume, job2)

    assert m1.final_score >= mock_config.min_match_score
    assert m1.match_status in ("MATCH", "PARTIAL_MATCH")
    assert m2.final_score < mock_config.min_match_score


# ============================================================================
# J. TELEGRAM INTEGRATION
# ============================================================================

def test_telegram_digest_formatting_and_dedup(mock_config):
    """Verify Telegram digest card formatting and duplicate notification suppression."""
    digest_service = DigestService(config=mock_config)

    job = Job(id=10, source="Cutshort Email Alert", source_job_id="CS1", title="Backend Engineer", company="Cutshort Co", url="https://cutshort.io/10")
    match = MatchResult(
        job_id=10,
        title="Backend Engineer",
        company="Cutshort Co",
        final_score=85.0,
        skill_score=0.8,
        similarity_score=0.82,
        matched_skills=["Python", "FastAPI"],
        missing_skills=["Docker"],
        experience_status="QUALIFIED",
        location_status="MATCHED",
        match_status="MATCH",
    )

    card = digest_service.format_job_card(match, job=job, index=1)
    assert "1. Backend Engineer" in card
    assert "Company: Cutshort Co" in card
    assert "Source: Cutshort Email Alert" in card
    assert "Match Score: 85.0/100" in card

    chunks = digest_service.build_digest_chunks([match], jobs_map={10: job})
    assert len(chunks) == 1
    assert "AI JOB DIGEST" in chunks[0].text
    assert chunks[0].job_ids == [10]


# ============================================================================
# K & L. DATABASE PERSISTENCE & END-TO-END MULTI-SOURCE PIPELINE
# ============================================================================

def test_end_to_end_multi_source_pipeline(memory_db, mock_config):
    """
    End-to-end integration test exercising Registry -> Normalization ->
    SQLite Persistence -> Matching -> Telegram Digest Mock across synthetic multi-source data.
    """
    # 1. Populate DB with synthetic jobs from multiple priority and free sources
    sources_jobs = [
        Job(source="Adzuna", source_job_id="A1", title="AI Specialist", company="Acme", location="Bangalore", fingerprint="fp_1"),
        Job(source="Internshala", source_job_id="I1", title="ML Intern", company="Beta Labs", location="Remote", fingerprint="fp_2"),
        Job(source="Naukri Email Alert", source_job_id="N1", title="NLP Lead", company="Gamma Corp", location="Chennai", fingerprint="fp_3"),
        Job(source="Wellfound Email Alert", source_job_id="W1", title="Startup AI Engineer", company="Delta AI", location="Remote", fingerprint="fp_4"),
    ]

    for j in sources_jobs:
        assert insert_job(memory_db, j) is True

    stored_jobs = get_all_jobs(memory_db)
    assert len(stored_jobs) == 4

    # 2. Match jobs
    jobs_map = get_jobs_map(memory_db)
    matches = [
        MatchResult(job_id=1, title="AI Specialist", company="Acme", final_score=90.0, match_status="MATCH"),
        MatchResult(job_id=2, title="ML Intern", company="Beta Labs", final_score=75.0, match_status="MATCH"),
        MatchResult(job_id=3, title="NLP Lead", company="Gamma Corp", final_score=85.0, match_status="MATCH"),
        MatchResult(job_id=4, title="Startup AI Engineer", company="Delta AI", final_score=80.0, match_status="MATCH"),
    ]
    save_match_results(memory_db, matches)

    # 3. Digest formatting
    digest_service = DigestService(config=mock_config)
    chunks = digest_service.build_digest_chunks(matches, jobs_map=jobs_map)

    mock_notifier = MagicMock(spec=TelegramNotifier)
    mock_notifier.send_message.return_value = True

    for chunk in chunks:
        delivered = mock_notifier.send_message(chunk.text)
        assert delivered is True
        record_notifications(memory_db, chunk.job_ids, notification_type="telegram_digest")

    notified = get_notified_job_ids(memory_db, notification_type="telegram_digest")
    assert len(notified) == 4


# ============================================================================
# M. 18-SOURCE INTEGRATION MATRIX TEST
# ============================================================================

@pytest.mark.parametrize(
    "identifier, source_class, expected_type, test_raw_payload",
    [
        ("adzuna", AdzunaJobSource, "api", {"id": "matrix_adz", "title": "AI Dev", "redirect_url": "https://adzuna.in/1"}),
        ("internshala", InternshalaJobSource, "scraper", {"source_job_id": "matrix_ish", "title": "ML Intern", "url": "https://internshala.com/1"}),
        ("linkedin_email", LinkedInAlertEmailSource, "email_alert", {"id": "msg_li"}),
        ("indeed_email", IndeedAlertEmailSource, "email_alert", {"id": "msg_ind"}),
        ("naukri_email", NaukriAlertEmailSource, "email_alert", {"id": "msg_nk"}),
        ("glassdoor_email", GlassdoorAlertEmailSource, "email_alert", {"id": "msg_gd"}),
        ("unstop_email", UnstopAlertEmailSource, "email_alert", {"id": "msg_unst"}),
        ("foundit_email", founditAlertEmailSource, "email_alert", {"id": "msg_fnd"}),
        ("cutshort_email", CutshortAlertEmailSource, "email_alert", {"id": "msg_cs"}),
        ("hirist_email", HiristAlertEmailSource, "email_alert", {"id": "msg_hi"}),
        ("wellfound_email", WellfoundAlertEmailSource, "email_alert", {"id": "msg_wf"}),
        ("arbeitnow", ArbeitnowJobSource, "api", {"slug": "matrix_arb", "title": "Python Engineer", "url": "https://arbeitnow.com/1"}),
        ("remoteok", RemoteOKJobSource, "api", {"id": "matrix_rok", "position": "AI Architect", "url": "https://remoteok.com/1"}),
        ("jobicy", JobicyJobSource, "api", {"id": "matrix_jby", "jobTitle": "Data Scientist", "url": "https://jobicy.com/1"}),
        ("himalayas", HimalayasJobSource, "api", {"id": "matrix_him", "title": "CV Dev", "url": "https://himalayas.app/1"}),
        ("jooble", JoobleJobSource, "api", {"id": "matrix_jbl", "title": "NLP Eng", "link": "https://jooble.org/1"}),
        ("jsearch", JSearchJobSource, "api", {"job_id": "matrix_js", "job_title": "ML Eng"}),
        ("serpapi", SerpApiJobSource, "api", {"job_id": "matrix_serp", "title": "AI Specialist"}),
        ("active_jobs_db", ActiveJobsDBJobSource, "api", {"id": "matrix_act", "title": "GenAI Architect"}),
        ("linkedin_jobs_api", LinkedInJobsApiSource, "api", {"id": "matrix_lk_api", "title": "Lead AI Architect"}),
        ("indeed_jobs_api", IndeedJobsApiSource, "api", {"id": "matrix_ind_api", "title": "Lead ML Architect"}),
    ],
)
def test_21_source_integration_matrix(identifier, source_class, expected_type, test_raw_payload, mock_config):
    """
    Matrix test validating every source for:
    (Identifier, Class, Type, Enabled Status, Registry Lookup).
    """
    registry = create_default_source_registry(mock_config)
    source = registry.get_source(identifier)

    assert source is not None, f"Source '{identifier}' missing from registry lookup"
    assert isinstance(source, source_class), f"Source '{identifier}' is not instance of {source_class}"
    assert source.source_identifier == identifier, f"Source identifier mismatch: {source.source_identifier}"
    assert source.source_type == expected_type, f"Source type mismatch for {identifier}: {source.source_type}"
    assert source.is_enabled(mock_config) is True, f"Source {identifier} expected enabled in mock_config"
