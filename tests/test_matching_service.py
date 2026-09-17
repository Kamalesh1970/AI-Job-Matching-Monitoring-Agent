"""
Tests for app/services/matching_service.py composite score and ranking engine.
"""

from unittest import mock
import numpy as np

from app.config import Config
from app.db.models import Job, Resume
from app.services.matching_service import MatchingService


def get_mock_embedding_service():
    """Helper creating a mock EmbeddingService."""
    mock_service = mock.MagicMock()
    mock_service.encode_text.side_effect = lambda t: np.ones((384,), dtype=np.float32)
    mock_service.encode_batch.side_effect = lambda texts: np.ones((len(texts), 384), dtype=np.float32)
    mock_service.calculate_cosine_similarity.return_value = 0.85
    return mock_service


def test_matching_service_match_job():
    """Test matching a single job against candidate resume."""
    cfg = Config(
        adzuna_app_id="dummy",
        adzuna_app_key="dummy",
        semantic_weight=0.50,
        skill_weight=0.30,
        rule_weight=0.20,
        min_match_score=60.0,
    )
    mock_embed = get_mock_embedding_service()
    service = MatchingService(config=cfg, embedding_service=mock_embed)

    resume = Resume(
        raw_text="Python Developer experienced in SQL and Machine Learning.",
        normalized_text="python developer experienced in sql and machine learning.",
        skills={"Python", "SQL", "Machine Learning"},
        embedding=np.ones((384,), dtype=np.float32),
    )

    job = Job(
        id=1,
        source="Adzuna",
        source_job_id="j101",
        title="Junior Machine Learning Engineer",
        company="AI Corp",
        location="Bengaluru, India",
        description="Looking for entry level ML engineer proficient in Python and SQL.",
        category="IT Jobs",
    )

    result = service.match_job(resume, job)

    assert result.job_id == 1
    assert result.source_job_id == "j101"
    assert result.match_status == "MATCH"
    assert result.final_score > 60.0
    assert "Python" in result.matched_skills
    assert "SQL" in result.matched_skills


def test_matching_service_filtered_senior_role():
    """Test that a senior role gets FILTERED status regardless of semantic similarity."""
    cfg = Config(
        adzuna_app_id="dummy",
        adzuna_app_key="dummy",
    )
    mock_embed = get_mock_embedding_service()
    service = MatchingService(config=cfg, embedding_service=mock_embed)

    resume = Resume(
        raw_text="Python Developer",
        normalized_text="python developer",
        skills={"Python"},
        embedding=np.ones((384,), dtype=np.float32),
    )

    job = Job(
        id=2,
        source="Adzuna",
        source_job_id="j102",
        title="Senior Lead AI Architect",
        description="Requires 10+ years experience.",
    )

    result = service.match_job(resume, job)

    assert result.match_status == "FILTERED"
    assert len(result.reasons) > 0


def test_matching_service_batch_all_jobs_ranking():
    """Test batch matching and ranking order by final_score descending."""
    cfg = Config(
        adzuna_app_id="dummy",
        adzuna_app_key="dummy",
    )
    mock_embed = get_mock_embedding_service()
    # Mock different similarity values
    mock_embed.calculate_cosine_similarity.side_effect = [0.90, 0.40]

    service = MatchingService(config=cfg, embedding_service=mock_embed)

    resume = Resume(
        raw_text="Python SQL Machine Learning Developer",
        normalized_text="python sql machine learning developer",
        skills={"Python", "SQL", "Machine Learning"},
        embedding=np.ones((384,), dtype=np.float32),
    )

    jobs = [
        Job(
            id=1,
            source="Adzuna",
            source_job_id="j1",
            title="Junior Data Scientist",
            description="Entry level python sql role",
            location="Remote",
        ),
        Job(
            id=2,
            source="Adzuna",
            source_job_id="j2",
            title="Software Trainee",
            description="Basic position",
            location="Unknown",
        ),
    ]

    results = service.match_all_jobs(resume, jobs)

    assert len(results) == 2
    assert results[0].final_score >= results[1].final_score
