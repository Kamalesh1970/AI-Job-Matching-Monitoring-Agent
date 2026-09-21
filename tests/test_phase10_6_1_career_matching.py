"""
Tests for Phase 10.6.1 — AI Career Discovery & Flexible Fresher Matching.
Covers fresher profile configuration, taxonomy classification, role title normalization,
fresher experience matching, multi-dimensional score breakdown, match categories,
database persistence, and notification formatting.
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
)
from app.db.models import Job, MatchResult
from app.services.career_taxonomy import (
    AI_ROLE_TAXONOMY,
    classify_role_family,
    is_ai_career_relevant,
    normalize_role_title,
)
from app.services.digest_service import DigestService
from app.services.matching_service import MatchingService
from app.services.rule_matcher import evaluate_experience, evaluate_rules


def test_fresher_config_defaults():
    """Verify Config correctly specifies candidate fresher profile and match thresholds."""
    config = Config(adzuna_app_id="dummy", adzuna_app_key="dummy")
    assert config.candidate_experience_level == "FRESHER"
    assert config.candidate_years_experience == 0
    assert config.candidate_status == "FINAL_YEAR_STUDENT"
    assert config.match_threshold_strong == 75.0
    assert config.match_threshold_potential == 50.0
    assert config.match_threshold_low == 30.0


def test_taxonomy_role_normalization():
    """Test normalized role titles and aliases for common AI roles."""
    assert normalize_role_title("ML Engineer") == "ml engineer"
    assert normalize_role_title("AI/ML Engineer!") == "ai ml engineer"
    assert normalize_role_title("Junior-ML-Engineer") == "junior ml engineer"
    assert normalize_role_title("Sr. Generative AI Developer") == "sr generative ai developer"


def test_taxonomy_classification():
    """Test classification of role titles into canonical role families."""
    family, canonical, _ = classify_role_family("Machine Learning Engineer")
    assert family == "Machine Learning"
    assert canonical == "Machine Learning Engineer"

    family, canonical, _ = classify_role_family("ML Engineer")
    assert family == "Machine Learning"

    family, canonical, _ = classify_role_family("Applied ML Engineer")
    assert family == "Machine Learning"

    family, canonical, _ = classify_role_family("Generative AI Engineer")
    assert family == "Generative AI & LLMs"
    assert canonical == "Generative AI Engineer"

    family, canonical, _ = classify_role_family("LLM Developer")
    assert family == "Generative AI & LLMs"

    family, canonical, _ = classify_role_family("AI Agent Engineer")
    assert family == "Generative AI & LLMs"

    family, canonical, _ = classify_role_family("Computer Vision Engineer")
    assert family == "Computer Vision"

    family, canonical, _ = classify_role_family("MLOps Engineer")
    assert family == "MLOps & AI Infrastructure"

    family, canonical, _ = classify_role_family("AI Product Manager")
    assert family == "AI Product & Solutions"

    family, canonical, _ = classify_role_family("AI Data Labeler")
    assert family == "AI Data Annotation"


def test_ai_career_relevance():
    """Test AI career relevance check on job titles and descriptions."""
    assert is_ai_career_relevant("Junior Machine Learning Engineer", "Build PyTorch models")
    assert is_ai_career_relevant("Software Engineer", "Developing LLM applications using LangChain and Python")
    assert not is_ai_career_relevant("Civil Engineer", "Bridge construction management")


def test_fresher_experience_matching():
    """Test flexible experience matching for freshers."""
    # 0 years / entry level / intern -> MATCH
    cat, reason = evaluate_experience("ML Intern", "Looking for final year students / freshers 0-1 years")
    assert cat == "MATCH"

    # 1 year requirement -> MATCH or POSSIBLE_MATCH (not rejected)
    cat, reason = evaluate_experience("Junior AI Engineer", "Requires 1 year of Python experience")
    assert cat in ("MATCH", "POSSIBLE_MATCH")

    # 1-2 years -> POSSIBLE_MATCH
    cat, reason = evaluate_experience("AI Developer", "1-2 years experience in deep learning")
    assert cat == "POSSIBLE_MATCH"

    # 3-4 years -> EXPERIENCE_GAP
    cat, reason = evaluate_experience("Data Scientist", "3-4 years experience in statistics")
    assert cat == "EXPERIENCE_GAP"

    # Senior / Lead / 5+ years -> NOT_ELIGIBLE
    cat, reason = evaluate_experience("Senior ML Engineer", "5+ years experience leading teams")
    assert cat == "NOT_ELIGIBLE"
    assert reason is not None


def test_multi_dimensional_match_result_persistence():
    """Test saving and retrieving MatchResult with Phase 10.6.1 breakdown fields."""
    conn = initialize_database(":memory:")
    job = Job(
        source="adzuna",
        source_job_id="test-101",
        title="Generative AI Engineer",
        company="AI Labs",
        location="Remote",
        description="Looking for fresher or 0-1 years experience in Python, PyTorch, LLMs",
        url="https://example.com/job/101",
        fetched_at="2026-09-21T00:00:00Z",
        first_seen_at="2026-09-21T00:00:00Z",
        last_seen_at="2026-09-21T00:00:00Z",
    )
    insert_job(conn, job)

    match = MatchResult(
        job_id=job.id,
        source_job_id="test-101",
        title=job.title,
        company=job.company,
        location=job.location,
        similarity_score=0.82,
        skill_score=0.75,
        rule_score=0.90,
        final_score=81.5,
        matched_skills=["Python", "PyTorch", "LLMs"],
        missing_skills=["LangGraph", "Docker"],
        experience_status="MATCH",
        location_status="MATCH",
        match_status="MATCH",
        reasons=[],
        match_category="STRONG_MATCH",
        role_family="Generative AI",
        canonical_role="Generative AI Engineer",
        experience_match="MATCH",
        skill_gaps=["LangGraph", "Docker"],
        role_score=100.0,
        experience_score=100.0,
        education_score=100.0,
        location_score=100.0,
        seniority_score=100.0,
    )

    save_match_result(conn, match)

    stored = get_stored_matches(conn)
    assert len(stored) == 1
    m = stored[0]
    assert m.match_category == "STRONG_MATCH"
    assert m.role_family == "Generative AI"
    assert m.canonical_role == "Generative AI Engineer"
    assert m.experience_match == "MATCH"
    assert m.skill_gaps == ["LangGraph", "Docker"]
    assert m.overall_score == 81.5


def test_low_and_potential_match_notification_cards():
    """Test format_job_card for LOW_MATCH and POTENTIAL_MATCH jobs."""
    service = DigestService(min_score=30.0)

    low_match = MatchResult(
        job_id=1,
        source_job_id="job-low-1",
        title="Generative AI Engineer",
        company="Example Company",
        location="Remote",
        similarity_score=0.40,
        skill_score=0.45,
        rule_score=0.50,
        final_score=43.0,
        matched_skills=["Python", "Machine Learning", "Transformers"],
        missing_skills=["LangGraph", "Docker", "AWS"],
        experience_status="MATCH",
        location_status="MATCH",
        match_status="PARTIAL_MATCH",
        reasons=[],
        match_category="LOW_MATCH",
        role_family="Generative AI",
        canonical_role="Generative AI Engineer",
        experience_match="MATCH",
        skill_gaps=["LangGraph", "Docker", "AWS"],
        role_score=100.0,
        experience_score=100.0,
        education_score=100.0,
        location_score=100.0,
        seniority_score=100.0,
    )

    job = Job(
        source="remoteok",
        source_job_id="job-low-1",
        title="Generative AI Engineer",
        company="Example Company",
        location="Remote",
        description="Low match AI role",
        url="https://example.com/apply/43",
        fetched_at="2026-09-21T00:00:00Z",
        first_seen_at="2026-09-21T00:00:00Z",
        last_seen_at="2026-09-21T00:00:00Z",
    )

    card = service.format_job_card(low_match, job=job)

    assert "LOW AI JOB MATCH" in card
    assert "Role: Generative AI Engineer" in card
    assert "Company: Example Company" in card
    assert "Match Score: 43%" in card
    assert "Fresher eligible" in card
    assert "Matched Skills:\nPython\nMachine Learning\nTransformers" in card
    assert "Skill Gaps:\nLangGraph\nDocker\nAWS" in card
    assert "Apply:\nhttps://example.com/apply/43" in card


def test_digest_chunk_includes_low_and_potential_matches():
    """Verify DigestService includes LOW_MATCH and POTENTIAL_MATCH jobs when building chunks."""
    service = DigestService(min_score=30.0)

    matches = [
        MatchResult(
            job_id=1,
            source_job_id="m1",
            title="AI Engineer",
            company="Co A",
            location="Remote",
            similarity_score=0.8,
            skill_score=0.8,
            rule_score=0.8,
            final_score=80.0,
            matched_skills=["Python"],
            missing_skills=[],
            experience_status="MATCH",
            location_status="MATCH",
            match_status="MATCH",
            reasons=[],
            match_category="STRONG_MATCH",
        ),
        MatchResult(
            job_id=2,
            source_job_id="m2",
            title="Data Scientist",
            company="Co B",
            location="Remote",
            similarity_score=0.6,
            skill_score=0.6,
            rule_score=0.6,
            final_score=60.0,
            matched_skills=["Python", "SQL"],
            missing_skills=["Tableau"],
            experience_status="MATCH",
            location_status="MATCH",
            match_status="PARTIAL_MATCH",
            reasons=[],
            match_category="POTENTIAL_MATCH",
        ),
        MatchResult(
            job_id=3,
            source_job_id="m3",
            title="AI Support Analyst",
            company="Co C",
            location="Remote",
            similarity_score=0.4,
            skill_score=0.4,
            rule_score=0.4,
            final_score=40.0,
            matched_skills=["Python"],
            missing_skills=["Linux"],
            experience_status="MATCH",
            location_status="MATCH",
            match_status="PARTIAL_MATCH",
            reasons=[],
            match_category="LOW_MATCH",
        ),
    ]

    jobs_map = {
        1: Job(source="adzuna", source_job_id="m1", title="AI Engineer", company="Co A", location="Remote", description="", url="https://ex.com/1", fetched_at="2026-09-21T00:00:00Z", first_seen_at="2026-09-21T00:00:00Z", last_seen_at="2026-09-21T00:00:00Z"),
        2: Job(source="adzuna", source_job_id="m2", title="Data Scientist", company="Co B", location="Remote", description="", url="https://ex.com/2", fetched_at="2026-09-21T00:00:00Z", first_seen_at="2026-09-21T00:00:00Z", last_seen_at="2026-09-21T00:00:00Z"),
        3: Job(source="adzuna", source_job_id="m3", title="AI Support Analyst", company="Co C", location="Remote", description="", url="https://ex.com/3", fetched_at="2026-09-21T00:00:00Z", first_seen_at="2026-09-21T00:00:00Z", last_seen_at="2026-09-21T00:00:00Z"),
    }

    chunks = service.build_digest_chunks(matches, jobs_map=jobs_map)
    assert len(chunks) > 0
    all_text = "\n".join(chunk.text for chunk in chunks)
    assert "1. AI Engineer" in all_text
    assert "POTENTIAL AI JOB MATCH" in all_text
    assert "LOW AI JOB MATCH" in all_text
    assert 1 in chunks[0].job_ids
    assert 2 in chunks[0].job_ids
    assert 3 in chunks[0].job_ids
