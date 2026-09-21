"""
Tests for Phase 10.6.1 REVISION A — AI Career Discovery & Flexible Fresher Matching.
Proves that experience gaps and non-eligibility do not hide AI jobs, all AI jobs remain stored,
General AI/ML taxonomy fallbacks function, and non-AI jobs are classified as NOT_RELEVANT.
"""

import json
import sqlite3
import pytest

from app.config import Config
from app.db.database import (
    get_connection,
    get_stored_matches,
    initialize_database,
    insert_job,
    save_match_result,
    save_match_results,
)
from app.db.models import Job, MatchResult, Resume
from app.services.career_taxonomy import (
    AI_ROLE_TAXONOMY,
    classify_role_family,
    is_ai_career_relevant,
    normalize_role_title,
)
from app.services.digest_service import DigestService
from app.services.matching_service import MatchingService
from app.services.rule_matcher import evaluate_experience, evaluate_rules


def test_1_fresher_0_year_job_match():
    """1. Fresher with 0 years can match a 0-year job."""
    cat, reason = evaluate_experience("Machine Learning Engineer", "0 years experience / fresh graduates required.")
    assert cat == "MATCH"
    assert reason is None


def test_2_fresher_0_1_year_possible_match():
    """2. Fresher can receive POSSIBLE_MATCH for a 0-1 year or 1-2 year job."""
    cat, _ = evaluate_experience("AI Engineer", "1-2 years experience required in PyTorch.")
    assert cat == "POSSIBLE_MATCH"


def test_3_fresher_experience_gap():
    """3. Fresher can receive EXPERIENCE_GAP for a job requiring 3-4 years experience."""
    cat, reason = evaluate_experience("Data Scientist", "3-4 years experience in Python and SQL.")
    assert cat == "EXPERIENCE_GAP"
    assert reason is not None


def test_4_fresher_not_eligible():
    """4. Fresher can receive NOT_ELIGIBLE for a clearly higher experience requirement (5+ yrs / Senior)."""
    cat, reason = evaluate_experience("Senior ML Architect", "5+ years experience leading MLOps infrastructure.")
    assert cat == "NOT_ELIGIBLE"
    assert reason is not None


def test_5_and_6_experience_gap_and_not_eligible_ai_jobs_stored():
    """5 & 6. EXPERIENCE_GAP and NOT_ELIGIBLE AI jobs remain stored in the database."""
    conn = initialize_database(":memory:")
    job1 = Job(source="adzuna", source_job_id="j-gap", title="AI Researcher", company="Co A", description="3-4 years experience", fetched_at="2026-09-22T00:00:00Z")
    job2 = Job(source="adzuna", source_job_id="j-not", title="Senior AI Architect", company="Co B", description="7+ years experience", fetched_at="2026-09-22T00:00:00Z")
    insert_job(conn, job1)
    insert_job(conn, job2)

    m1 = MatchResult(job_id=job1.id, source_job_id="j-gap", title=job1.title, company=job1.company, final_score=65.0, match_category="POTENTIAL_MATCH", experience_match="EXPERIENCE_GAP", role_family="Machine Learning")
    m2 = MatchResult(job_id=job2.id, source_job_id="j-not", title=job2.title, company=job2.company, final_score=45.0, match_category="LOW_MATCH", experience_match="NOT_ELIGIBLE", role_family="Generative AI & LLMs")

    save_match_results(conn, [m1, m2])
    stored = get_stored_matches(conn)
    assert len(stored) == 2
    statuses = {m.experience_match for m in stored}
    assert "EXPERIENCE_GAP" in statuses
    assert "NOT_ELIGIBLE" in statuses


def test_7_8_9_10_match_category_experience_combinations_stored():
    """7, 8, 9, 10. Prove LOW_MATCH and POTENTIAL_MATCH with EXPERIENCE_GAP and NOT_ELIGIBLE combinations are stored."""
    conn = initialize_database(":memory:")
    jobs = [
        Job(source="src", source_job_id=f"id-{i}", title=f"AI Job {i}", description="AI position", fetched_at="2026-09-22T00:00:00Z")
        for i in range(1, 5)
    ]
    for j in jobs:
        insert_job(conn, j)

    matches = [
        MatchResult(job_id=jobs[0].id, source_job_id="id-1", title="AI Job 1", final_score=45.0, match_category="LOW_MATCH", experience_match="EXPERIENCE_GAP"),
        MatchResult(job_id=jobs[1].id, source_job_id="id-2", title="AI Job 2", final_score=42.0, match_category="LOW_MATCH", experience_match="NOT_ELIGIBLE"),
        MatchResult(job_id=jobs[2].id, source_job_id="id-3", title="AI Job 3", final_score=68.0, match_category="POTENTIAL_MATCH", experience_match="EXPERIENCE_GAP"),
        MatchResult(job_id=jobs[3].id, source_job_id="id-4", title="AI Job 4", final_score=61.0, match_category="POTENTIAL_MATCH", experience_match="NOT_ELIGIBLE"),
    ]

    save_match_results(conn, matches)
    stored = get_stored_matches(conn)
    assert len(stored) == 4
    combos = {(m.match_category, m.experience_match) for m in stored}
    assert ("LOW_MATCH", "EXPERIENCE_GAP") in combos
    assert ("LOW_MATCH", "NOT_ELIGIBLE") in combos
    assert ("POTENTIAL_MATCH", "EXPERIENCE_GAP") in combos
    assert ("POTENTIAL_MATCH", "NOT_ELIGIBLE") in combos


def test_11_general_ai_ml_taxonomy_fallback():
    """11. AI-relevant jobs with unknown specific role use role_family = 'General AI/ML' and canonical_role = 'AI/ML Role'."""
    family, canonical, score = classify_role_family("Emerging Tech Developer", "Working with PyTorch, RAG pipelines, and LLM fine-tuning.")
    assert family == "General AI/ML"
    assert canonical == "AI/ML Role"


def test_12_non_ai_jobs_classified_as_not_relevant():
    """12. Non-AI jobs are classified as NOT_RELEVANT."""
    cfg = Config(adzuna_app_id="dummy", adzuna_app_key="dummy")
    mock_embed = pytest.importorskip("unittest.mock").MagicMock()
    mock_embed.encode_text.return_value = [0.1] * 384
    mock_embed.calculate_cosine_similarity.return_value = 0.20

    service = MatchingService(config=cfg, embedding_service=mock_embed)
    resume = Resume(raw_text="Python", normalized_text="python", skills={"Python"})
    non_ai_job = Job(id=99, source="adzuna", source_job_id="non-ai", title="Civil Site Engineer", description="Construction project management for concrete bridges.")

    result = service.match_job(resume, non_ai_job)
    assert result.match_category == "NOT_RELEVANT"
    assert result.match_status == "FILTERED"


def test_14_notification_behavior_with_experience_gap_cards():
    """14. Notification formatting correctly reflects experience status on job cards."""
    service = DigestService(min_score=30.0)
    low_gap_match = MatchResult(
        job_id=1,
        source_job_id="job-gap-1",
        title="Machine Learning Engineer",
        company="Tech Corp",
        location="Remote",
        final_score=48.5,
        matched_skills=["Python", "SQL"],
        missing_skills=["Kubernetes"],
        experience_status="EXPERIENCE_GAP",
        match_category="LOW_MATCH",
        experience_match="EXPERIENCE_GAP",
        skill_gaps=["Kubernetes"],
    )
    job = Job(source="adzuna", source_job_id="job-gap-1", title="Machine Learning Engineer", company="Tech Corp", url="https://example.com/apply")

    card = service.format_job_card(low_gap_match, job=job)
    assert "LOW AI JOB MATCH" in card
    assert "Role: Machine Learning Engineer" in card
    assert "⚠️ EXPERIENCE GAP" in card
    assert "Apply:\nhttps://example.com/apply" in card
