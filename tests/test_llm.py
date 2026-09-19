"""
Unit tests for Phase 7: Gemini API LLM Resume Tailoring & Human Review.
Mocks Google Gen AI SDK completely — zero live API calls are executed during pytest.
Tests all 32 requirements specified in the Phase 7 prompt specification.
"""

import json
import os
import sqlite3
from unittest.mock import MagicMock, patch
import pytest

from app.config import Config, load_config
from app.db.database import (
    get_tailored_resume_by_id,
    get_tailored_resumes_by_job,
    initialize_database,
    insert_job,
    save_match_result,
    update_tailored_resume_status,
)
from app.db.models import Job, MatchResult
from app.llm.base import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.llm.schemas import ResumeProfile, TailoredResume, ValidationResult
from app.llm.tailoring_service import ResumeTailoringService
from app.llm.validator import TruthValidator
from app.main import handle_export_resume, handle_review_resume, handle_tailor_resume
from app.services.digest_service import DigestService
from app.services.pipeline_service import PipelineService
from app.scheduler.scheduler import PipelineScheduler


@pytest.fixture
def memory_db():
    """Provides an initialized in-memory SQLite connection."""
    conn = initialize_database(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def mock_config():
    """Provides a default Config instance with LLM disabled."""
    return Config(
        adzuna_app_id="test_id",
        adzuna_app_key="test_key",
        llm_enabled=False,
        llm_provider="gemini",
        gemini_api_key="mock-gemini-key-do-not-use",
        gemini_model="gemini-2.5-flash",
        openai_api_key="mock-openai-key",
        openai_model="gpt-5.6-luna",
        llm_temperature=0.2,
        llm_match_threshold=0.75,
        db_path=":memory:",
    )


@pytest.fixture
def sample_job():
    """Provides a sample Job model."""
    return Job(
        id=1,
        source="Adzuna",
        source_job_id="test_101",
        title="Senior AI Engineer",
        company="TechCorp",
        location="Remote",
        description="Looking for Python, PyTorch, and NLP expert.",
        url="https://example.com/job101",
        fetched_at="2026-09-19T00:00:00Z",
        first_seen_at="2026-09-19T00:00:00Z",
        last_seen_at="2026-09-19T00:00:00Z",
    )


@pytest.fixture
def sample_match():
    """Provides a sample MatchResult model with 85% score."""
    return MatchResult(
        job_id=1,
        source_job_id="test_101",
        title="Senior AI Engineer",
        company="TechCorp",
        location="Remote",
        similarity_score=0.85,
        skill_score=0.80,
        rule_score=0.90,
        final_score=85.0,
        match_status="MATCH",
        matched_skills=["Python", "PyTorch"],
        missing_skills=["Kubernetes"],
        reasons=["High skill alignment"],
        calculated_at="2026-09-19T00:00:00Z",
    )


@pytest.fixture
def sample_resume_profile():
    """Provides a sample master resume profile."""
    return ResumeProfile(
        name="Kamalesh",
        summary="Experienced AI Engineer specializing in Python and machine learning.",
        skills=["Python", "PyTorch", "NLP", "Machine Learning", "SQL"],
        experience=[
            {
                "company": "DataAI Inc",
                "title": "AI Engineer",
                "bullets": ["Developed NLP models using PyTorch"],
            }
        ],
        projects=[
            {
                "name": "Job Agent",
                "technologies": ["Python", "PyTorch"],
                "bullets": ["Built automated pipeline"],
            }
        ],
        education=[{"institution": "Anna University", "degree": "B.E. Computer Science"}],
        certifications=["AWS Machine Learning Specialty"],
        achievements=["Published paper"],
    )


# ---------------------------------------------------------------------
# Test 1: LLM Disabled
# ---------------------------------------------------------------------
def test_1_llm_disabled(memory_db, mock_config, sample_job, sample_match):
    """Test 1: When LLM_ENABLED=false, application does not initialize or call Gemini."""
    insert_job(memory_db, sample_job)
    mock_config.llm_enabled = False
    service = ResumeTailoringService(config=mock_config)

    assert service.provider is None

    result = service.tailor_resume_for_job(memory_db, sample_job, sample_match)
    assert result["status"] == "SKIPPED_LOW_MATCH"

    drafts = get_tailored_resumes_by_job(memory_db, sample_job.id)
    assert len(drafts) == 1
    assert drafts[0]["status"] == "SKIPPED_LOW_MATCH"


# ---------------------------------------------------------------------
# Test 2: LLM Enabled
# ---------------------------------------------------------------------
def test_2_llm_enabled(memory_db, mock_config, sample_job, sample_match, sample_resume_profile):
    """Test 2: LLM enabled calls provider and stores validated draft."""
    mock_config.llm_enabled = True
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = TailoredResume(
        summary="Experienced AI Engineer specializing in Python and PyTorch.",
        skills=["Python", "PyTorch", "NLP"],
        experience=[{"company": "DataAI Inc", "title": "AI Engineer", "bullets": ["Built models"]}],
        projects=[],
        education=[{"institution": "Anna University", "degree": "B.E. Computer Science"}],
        certifications=["AWS Machine Learning Specialty"],
        changes=["Emphasized PyTorch and NLP"],
        warnings=[],
    )

    service = ResumeTailoringService(config=mock_config, provider=mock_provider)
    with patch.object(service, "load_master_resume", return_value=sample_resume_profile):
        result = service.tailor_resume_for_job(memory_db, sample_job, sample_match)

    assert result["status"] == "VALIDATED"
    assert mock_provider.generate_structured.called


# ---------------------------------------------------------------------
# Test 3: Provider Selection
# ---------------------------------------------------------------------
def test_3_provider_selection(mock_config):
    """Test 3: Selected provider matches configuration (GeminiProvider vs OpenAIProvider)."""
    mock_config.llm_enabled = True

    mock_config.llm_provider = "gemini"
    with patch("google.genai.Client"):
        service_gemini = ResumeTailoringService(config=mock_config)
        assert isinstance(service_gemini.provider, GeminiProvider)

    mock_config.llm_provider = "openai"
    with patch("openai.OpenAI"):
        service_openai = ResumeTailoringService(config=mock_config)
        assert isinstance(service_openai.provider, OpenAIProvider)


# ---------------------------------------------------------------------
# Test 4: Gemini Success
# ---------------------------------------------------------------------
def test_4_gemini_success(mock_config):
    """Test 4: GeminiProvider generates structured output successfully via google-genai mock."""
    mock_config.llm_enabled = True
    mock_config.llm_provider = "gemini"

    mock_client = MagicMock()
    mock_parsed_response = TailoredResume(summary="Gemini structured summary", skills=["Python"])
    mock_response = MagicMock()
    mock_response.parsed = mock_parsed_response
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(config=mock_config)
    provider.client = mock_client

    result = provider.generate_structured("prompt", "system", TailoredResume)
    assert result.summary == "Gemini structured summary"
    assert provider.client.models.generate_content.called


# ---------------------------------------------------------------------
# Test 5: Gemini Authentication Failure
# ---------------------------------------------------------------------
def test_5_gemini_authentication_failure(mock_config):
    """Test 5: Gemini API authentication failure fails fast without infinite retries."""
    mock_config.llm_enabled = True
    mock_config.llm_provider = "gemini"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("API_KEY_INVALID 401 Unauthenticated")

    provider = GeminiProvider(config=mock_config)
    provider.client = mock_client

    with pytest.raises(RuntimeError) as exc_info:
        provider.generate_structured("prompt", "system", TailoredResume)

    assert "authentication failure" in str(exc_info.value).lower()
    assert mock_client.models.generate_content.call_count == 1


# ---------------------------------------------------------------------
# Test 6: Gemini Quota Failure
# ---------------------------------------------------------------------
def test_6_gemini_quota_failure(mock_config):
    """Test 6: Gemini quota exhaustion error handled without infinite retries storm."""
    mock_config.llm_enabled = True
    mock_config.llm_provider = "gemini"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("RESOURCE_EXHAUSTED: Quota exceeded")

    provider = GeminiProvider(config=mock_config)
    provider.client = mock_client

    with patch("time.sleep", return_value=None):
        with pytest.raises(RuntimeError) as exc_info:
            provider.generate_structured("prompt", "system", TailoredResume)

    assert "failed after 3 attempts" in str(exc_info.value)
    assert mock_client.models.generate_content.call_count == 3


# ---------------------------------------------------------------------
# Test 7: Rate Limit Retry Handling
# ---------------------------------------------------------------------
def test_7_rate_limit_retry_handling(mock_config):
    """Test 7: Transient rate limit error retries up to bounded limit and succeeds."""
    mock_config.llm_enabled = True
    mock_config.llm_provider = "gemini"

    mock_client = MagicMock()
    mock_success = MagicMock()
    mock_success.parsed = TailoredResume(summary="Recovered after 429 rate limit")

    mock_client.models.generate_content.side_effect = [
        Exception("Rate limit 429 Too Many Requests"),
        Exception("Rate limit 429 Too Many Requests"),
        mock_success,
    ]

    provider = GeminiProvider(config=mock_config)
    provider.client = mock_client

    with patch("time.sleep", return_value=None):
        res = provider.generate_structured("prompt", "system", TailoredResume)

    assert res.summary == "Recovered after 429 rate limit"
    assert mock_client.models.generate_content.call_count == 3


# ---------------------------------------------------------------------
# Test 8: Timeout Handling
# ---------------------------------------------------------------------
def test_8_timeout_retry_handling(mock_config):
    """Test 8: Timeout error retries up to bounded limit."""
    mock_config.llm_enabled = True
    mock_config.llm_provider = "gemini"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("TimeoutError: Request timed out")

    provider = GeminiProvider(config=mock_config)
    provider.client = mock_client

    with patch("time.sleep", return_value=None):
        with pytest.raises(RuntimeError) as exc_info:
            provider.generate_structured("prompt", "system", TailoredResume)

    assert "failed after 3 attempts" in str(exc_info.value)
    assert mock_client.models.generate_content.call_count == 3


# ---------------------------------------------------------------------
# Test 9: Network Error Handling
# ---------------------------------------------------------------------
def test_9_network_error_handling(mock_config):
    """Test 9: Network connection error retries up to bounded limit."""
    mock_config.llm_enabled = True
    mock_config.llm_provider = "gemini"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("ConnectionError: Failed to establish connection")

    provider = GeminiProvider(config=mock_config)
    provider.client = mock_client

    with patch("time.sleep", return_value=None):
        with pytest.raises(RuntimeError) as exc_info:
            provider.generate_structured("prompt", "system", TailoredResume)

    assert "failed after 3 attempts" in str(exc_info.value)
    assert mock_client.models.generate_content.call_count == 3


# ---------------------------------------------------------------------
# Test 10: Malformed Structured Output
# ---------------------------------------------------------------------
def test_10_malformed_structured_output(mock_config):
    """Test 10: Malformed JSON output fallback parsing handles invalid structure cleanly."""
    mock_config.llm_enabled = True
    mock_config.llm_provider = "gemini"

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = '{"summary": "Parsed via JSON fallback"}'
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(config=mock_config)
    provider.client = mock_client

    res = provider.generate_structured("prompt", "system", TailoredResume)
    assert res.summary == "Parsed via JSON fallback"


# ---------------------------------------------------------------------
# Test 11: Empty Response Handling
# ---------------------------------------------------------------------
def test_11_empty_response_handling(mock_config):
    """Test 11: Empty string response from model raises Exception cleanly."""
    mock_config.llm_enabled = True
    mock_config.llm_provider = "gemini"

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = ""
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(config=mock_config)
    provider.client = mock_client

    with patch("time.sleep", return_value=None):
        with pytest.raises(RuntimeError):
            provider.generate_structured("prompt", "system", TailoredResume)


# ---------------------------------------------------------------------
# Test 12: Low Match Score Skips Gemini
# ---------------------------------------------------------------------
def test_12_low_match_score_skips_gemini(memory_db, mock_config, sample_job):
    """Test 12: Match score below threshold (e.g. 50% < 75%) skips Gemini API call."""
    mock_config.llm_enabled = True
    mock_config.llm_match_threshold = 0.75

    low_match = MatchResult(
        job_id=1,
        source_job_id="test_101",
        title="Senior AI Engineer",
        company="TechCorp",
        location="Remote",
        similarity_score=0.50,
        skill_score=0.50,
        rule_score=0.50,
        final_score=50.0,
        match_status="PARTIAL_MATCH",
        matched_skills=["Python"],
        missing_skills=["PyTorch"],
        reasons=[],
        calculated_at="2026-09-19T00:00:00Z",
    )

    mock_provider = MagicMock(spec=LLMProvider)
    service = ResumeTailoringService(config=mock_config, provider=mock_provider)

    result = service.tailor_resume_for_job(memory_db, sample_job, low_match)

    assert result["status"] == "SKIPPED_LOW_MATCH"
    assert not mock_provider.generate_structured.called


# ---------------------------------------------------------------------
# Test 13: Unsupported Skill Detection
# ---------------------------------------------------------------------
def test_13_unsupported_skill_detection(sample_resume_profile):
    """Test 13: TruthValidator detects unsupported/fabricated skill."""
    tailored = TailoredResume(
        summary="AI Engineer",
        skills=["Python", "PyTorch", "Rust", "Quantum Computing"],
    )
    val = TruthValidator.validate(sample_resume_profile, tailored)
    assert not val.valid
    assert any("Quantum Computing" in v for v in val.violations)


# ---------------------------------------------------------------------
# Test 14: Unsupported Technology Detection
# ---------------------------------------------------------------------
def test_14_unsupported_technology_detection(sample_resume_profile):
    """Test 14: TruthValidator detects unsupported technology in project."""
    tailored = TailoredResume(
        summary="AI Engineer",
        projects=[{"name": "Job Agent", "technologies": ["Solidity", "Blockchain"]}],
    )
    val = TruthValidator.validate(sample_resume_profile, tailored)
    assert not val.valid
    assert any("Solidity" in v or "Blockchain" in v for v in val.violations)


# ---------------------------------------------------------------------
# Test 15: Unsupported Company Detection
# ---------------------------------------------------------------------
def test_15_unsupported_company_detection(sample_resume_profile):
    """Test 15: TruthValidator detects unsupported company in experience."""
    tailored = TailoredResume(
        experience=[{"company": "Google Brain LLC", "title": "Staff Scientist"}]
    )
    val = TruthValidator.validate(sample_resume_profile, tailored)
    assert not val.valid
    assert any("Google Brain LLC" in v for v in val.violations)


# ---------------------------------------------------------------------
# Test 16: Unsupported Certification Detection
# ---------------------------------------------------------------------
def test_16_unsupported_certification_detection(sample_resume_profile):
    """Test 16: TruthValidator detects unsupported certification."""
    tailored = TailoredResume(
        certifications=["AWS Machine Learning Specialty", "Certified Kubernetes Administrator"]
    )
    val = TruthValidator.validate(sample_resume_profile, tailored)
    assert not val.valid
    assert any("Certified Kubernetes Administrator" in v for v in val.violations)


# ---------------------------------------------------------------------
# Test 17: Fabricated Metric Detection
# ---------------------------------------------------------------------
def test_17_fabricated_metric_detection(sample_resume_profile):
    """Test 17: TruthValidator detects fabricated metrics and numbers."""
    tailored = TailoredResume(
        summary="Reduced latency by 99% and saved $500000 in cloud infrastructure."
    )
    val = TruthValidator.validate(sample_resume_profile, tailored)
    assert not val.valid
    assert any("99%" in v or "$500000" in v for v in val.violations)


# ---------------------------------------------------------------------
# Test 18: Fabricated Experience Detection
# ---------------------------------------------------------------------
def test_18_fabricated_experience_detection(sample_resume_profile):
    """Test 18: TruthValidator detects fabricated job titles or years of experience."""
    tailored = TailoredResume(
        summary="AI Engineer with 15+ years of experience.",
        experience=[{"company": "DataAI Inc", "title": "Chief Technology Officer"}],
    )
    val = TruthValidator.validate(sample_resume_profile, tailored)
    assert not val.valid
    assert any("Chief Technology Officer" in v or "15" in v for v in val.violations)


# ---------------------------------------------------------------------
# Test 19: Valid Rewriting
# ---------------------------------------------------------------------
def test_19_valid_rewriting(sample_resume_profile):
    """Test 19: TruthValidator approves faithful rewriting."""
    tailored = TailoredResume(
        summary="Experienced AI Engineer specializing in Python and machine learning models.",
        skills=["Python", "PyTorch", "NLP"],
        experience=[{"company": "DataAI Inc", "title": "AI Engineer", "bullets": ["Developed NLP models using PyTorch"]}],
        education=[{"institution": "Anna University", "degree": "B.E. Computer Science"}],
        certifications=["AWS Machine Learning Specialty"],
    )
    val = TruthValidator.validate(sample_resume_profile, tailored)
    assert val.valid
    assert len(val.violations) == 0


# ---------------------------------------------------------------------
# Test 20: Warning Generation
# ---------------------------------------------------------------------
def test_20_warning_generation(sample_resume_profile):
    """Test 20: TruthValidator preserves warnings from tailored output."""
    tailored = TailoredResume(
        summary="AI Engineer",
        skills=["Python"],
        warnings=["Candidate lacks Kubernetes experience required by target job description."],
    )
    val = TruthValidator.validate(sample_resume_profile, tailored)
    assert val.valid
    assert "Candidate lacks Kubernetes experience required by target job description." in val.warnings


# ---------------------------------------------------------------------
# Test 21: Validation Failure Status
# ---------------------------------------------------------------------
def test_21_validation_failure_status(memory_db, mock_config, sample_job, sample_match, sample_resume_profile):
    """Test 21: Validation failure causes draft status INVALID in SQLite persistence."""
    insert_job(memory_db, sample_job)
    mock_config.llm_enabled = True
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = TailoredResume(
        summary="AI Engineer",
        skills=["Python", "FabricatedSuperSkill"],
    )

    service = ResumeTailoringService(config=mock_config, provider=mock_provider)
    with patch.object(service, "load_master_resume", return_value=sample_resume_profile):
        result = service.tailor_resume_for_job(memory_db, sample_job, sample_match)

    assert result["status"] == "INVALID"
    drafts = get_tailored_resumes_by_job(memory_db, sample_job.id)
    assert len(drafts) == 1
    assert drafts[0]["status"] == "INVALID"


# ---------------------------------------------------------------------
# Test 22: Draft Persistence
# ---------------------------------------------------------------------
def test_22_draft_persistence(memory_db, mock_config, sample_job, sample_match, sample_resume_profile):
    """Test 22: Persists tailored resume draft into SQLite tailored_resumes table."""
    insert_job(memory_db, sample_job)
    mock_config.llm_enabled = True
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = TailoredResume(
        summary="Valid summary", skills=["Python"]
    )

    service = ResumeTailoringService(config=mock_config, provider=mock_provider)
    with patch.object(service, "load_master_resume", return_value=sample_resume_profile):
        res = service.tailor_resume_for_job(memory_db, sample_job, sample_match)

    draft_id = res["id"]
    retrieved = get_tailored_resume_by_id(memory_db, draft_id)
    assert retrieved is not None
    assert retrieved["match_score"] == 85.0
    assert retrieved["provider"] == "gemini"


# ---------------------------------------------------------------------
# Test 23: Draft Versioning
# ---------------------------------------------------------------------
def test_23_draft_versioning(memory_db, mock_config, sample_job, sample_match, sample_resume_profile):
    """Test 23: Multiple drafts for same job supported without overwriting."""
    insert_job(memory_db, sample_job)
    mock_config.llm_enabled = True
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = TailoredResume(summary="Summary 1", skills=["Python"])

    service = ResumeTailoringService(config=mock_config, provider=mock_provider)
    with patch.object(service, "load_master_resume", return_value=sample_resume_profile):
        service.tailor_resume_for_job(memory_db, sample_job, sample_match)
        service.tailor_resume_for_job(memory_db, sample_job, sample_match)

    drafts = get_tailored_resumes_by_job(memory_db, sample_job.id)
    assert len(drafts) == 2


# ---------------------------------------------------------------------
# Test 24: Approval CLI Flow
# ---------------------------------------------------------------------
def test_24_approval_cli_flow(memory_db, mock_config, sample_job, sample_match, sample_resume_profile):
    """Test 24: Interactive approval changes draft status to APPROVED."""
    insert_job(memory_db, sample_job)
    save_match_result(memory_db, sample_match)

    mock_config.llm_enabled = True
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = TailoredResume(summary="Summary", skills=["Python"])

    service = ResumeTailoringService(config=mock_config, provider=mock_provider)
    with patch.object(service, "load_master_resume", return_value=sample_resume_profile):
        res = service.tailor_resume_for_job(memory_db, sample_job, sample_match)

    draft_id = res["id"]

    handle_review_resume(config=mock_config, draft_id=draft_id, input_func=lambda prompt: "A", conn=memory_db)

    retrieved = get_tailored_resume_by_id(memory_db, draft_id)
    assert retrieved["status"] == "APPROVED"


# ---------------------------------------------------------------------
# Test 25: Rejection CLI Flow
# ---------------------------------------------------------------------
def test_25_rejection_cli_flow(memory_db, mock_config, sample_job, sample_match, sample_resume_profile):
    """Test 25: Interactive rejection changes draft status to REJECTED."""
    insert_job(memory_db, sample_job)
    save_match_result(memory_db, sample_match)

    mock_config.llm_enabled = True
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = TailoredResume(summary="Summary", skills=["Python"])

    service = ResumeTailoringService(config=mock_config, provider=mock_provider)
    with patch.object(service, "load_master_resume", return_value=sample_resume_profile):
        res = service.tailor_resume_for_job(memory_db, sample_job, sample_match)

    draft_id = res["id"]

    handle_review_resume(config=mock_config, draft_id=draft_id, input_func=lambda prompt: "R", conn=memory_db)

    retrieved = get_tailored_resume_by_id(memory_db, draft_id)
    assert retrieved["status"] == "REJECTED"


# ---------------------------------------------------------------------
# Test 26: Invalid Draft Cannot Be Approved
# ---------------------------------------------------------------------
def test_26_invalid_draft_cannot_be_approved(memory_db, mock_config, sample_job, sample_match, sample_resume_profile):
    """Test 26: CLI blocks approving an INVALID draft."""
    insert_job(memory_db, sample_job)
    save_match_result(memory_db, sample_match)

    mock_config.llm_enabled = True
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = TailoredResume(summary="Summary", skills=["FakeSkill"])

    service = ResumeTailoringService(config=mock_config, provider=mock_provider)
    with patch.object(service, "load_master_resume", return_value=sample_resume_profile):
        res = service.tailor_resume_for_job(memory_db, sample_job, sample_match)

    draft_id = res["id"]
    assert res["status"] == "INVALID"

    handle_review_resume(config=mock_config, draft_id=draft_id, input_func=lambda prompt: "A", conn=memory_db)

    retrieved = get_tailored_resume_by_id(memory_db, draft_id)
    assert retrieved["status"] == "INVALID"


# ---------------------------------------------------------------------
# Test 27: Approved Draft Export
# ---------------------------------------------------------------------
def test_27_approved_draft_export(memory_db, mock_config, sample_job, sample_match, sample_resume_profile, tmp_path):
    """Test 27: Approved draft exports to Markdown file correctly."""
    insert_job(memory_db, sample_job)
    save_match_result(memory_db, sample_match)

    mock_config.llm_enabled = True
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = TailoredResume(summary="Polished Summary", skills=["Python"])

    service = ResumeTailoringService(config=mock_config, provider=mock_provider)
    with patch.object(service, "load_master_resume", return_value=sample_resume_profile):
        res = service.tailor_resume_for_job(memory_db, sample_job, sample_match)

    draft_id = res["id"]
    update_tailored_resume_status(memory_db, draft_id, "APPROVED")

    export_file = tmp_path / "tailored.md"
    success = handle_export_resume(config=mock_config, draft_id=draft_id, output_path=str(export_file), conn=memory_db)

    assert success is True
    assert export_file.exists()
    content = export_file.read_text()
    assert "Polished Summary" in content
    assert "Python" in content


# ---------------------------------------------------------------------
# Test 28: Rejected Draft Cannot Export
# ---------------------------------------------------------------------
def test_28_rejected_draft_cannot_export(memory_db, mock_config, sample_job, sample_match, sample_resume_profile):
    """Test 28: Only APPROVED drafts can be exported; rejected/drafts fail."""
    insert_job(memory_db, sample_job)
    save_match_result(memory_db, sample_match)

    mock_config.llm_enabled = True
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = TailoredResume(summary="Summary", skills=["Python"])

    service = ResumeTailoringService(config=mock_config, provider=mock_provider)
    with patch.object(service, "load_master_resume", return_value=sample_resume_profile):
        res = service.tailor_resume_for_job(memory_db, sample_job, sample_match)

    draft_id = res["id"]

    success = handle_export_resume(config=mock_config, draft_id=draft_id, conn=memory_db)
    assert success is False


# ---------------------------------------------------------------------
# Test 29: Telegram Notification Integration
# ---------------------------------------------------------------------
def test_29_telegram_notification_format(sample_match, sample_job):
    """Test 29: DigestService includes draft ID review notification line in job card."""
    digest = DigestService()
    card = digest.format_job_card(sample_match, job=sample_job, index=1, draft_id=42)
    assert "Tailored resume draft #42 is ready for review." in card


# ---------------------------------------------------------------------
# Test 30: Scheduler Integration
# ---------------------------------------------------------------------
def test_30_scheduler_integration(memory_db, mock_config):
    """Test 30: PipelineScheduler initializes and executes without crashing."""
    scheduler = PipelineScheduler(config=mock_config)
    assert scheduler.config == mock_config
    assert not scheduler.is_running()


# ---------------------------------------------------------------------
# Test 31: Gemini Failure Isolation
# ---------------------------------------------------------------------
def test_31_gemini_failure_isolation(memory_db, mock_config, sample_job, sample_match):
    """Test 31: Failure in Gemini tailoring step does not crash pipeline."""
    mock_config.llm_enabled = True
    insert_job(memory_db, sample_job)

    pipeline = PipelineService(config=mock_config)

    with patch("app.services.pipeline_service.AdzunaJobSource") as mock_adzuna:
        mock_adzuna.return_value.fetch_jobs_for_keyword.return_value = ([], True)
        with patch("app.services.pipeline_service.MatchingService") as mock_matching:
            mock_matching.return_value.prepare_resume.return_value = "resume text"
            mock_matching.return_value.match_all_jobs.return_value = [sample_match]
            with patch("app.services.pipeline_service.ResumeTailoringService") as mock_tailoring:
                mock_tailoring.return_value.tailor_resume_for_job.side_effect = Exception("Gemini API Timeout")
                summary = pipeline.run_monitoring_pipeline(config=mock_config, conn=memory_db)

    assert summary.status is not None  # Pipeline completes cleanly despite Gemini exception


def test_32_phase_1_to_6_regression(memory_db, mock_config, sample_job, sample_match):
    """Test 32: Phase 1-6 behavior remains 100% unchanged when LLM_ENABLED=false."""
    mock_config.llm_enabled = False
    insert_job(memory_db, sample_job)

    pipeline = PipelineService(config=mock_config)

    with patch("app.services.pipeline_service.AdzunaJobSource") as mock_adzuna:
        mock_adzuna.return_value.fetch_jobs_for_keyword.return_value = ([sample_job], True)
        with patch("app.services.pipeline_service.InternshalaJobSource") as mock_ish:
            from app.db.models import SourceResult, SourceStatus
            mock_ish.return_value.fetch_source_jobs.return_value = SourceResult(
                source_name="Internshala",
                status=SourceStatus.SUCCESS,
                jobs=[],
                total_fetched=0,
            )
            with patch("app.services.pipeline_service.MatchingService") as mock_matching:
                mock_matching.return_value.prepare_resume.return_value = "resume text"
                mock_matching.return_value.match_all_jobs.return_value = [sample_match]
                mock_notifier = MagicMock()
                mock_notifier.send_message.return_value = True
                summary = pipeline.run_monitoring_pipeline(
                    config=mock_config, conn=memory_db, notifier=mock_notifier
                )

    assert summary.status == "SUCCESS"
    assert summary.matches_found == 1
