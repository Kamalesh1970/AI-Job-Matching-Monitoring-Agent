"""
Unit tests for DigestService message formatting and chunking logic.
"""

from app.db.models import Job, MatchResult
from app.services.digest_service import DigestService


def test_digest_service_filtering_and_sorting():
    """Test that matches below threshold or marked FILTERED are excluded and sorted descending."""
    matches = [
        MatchResult(
            job_id=1, title="Job 1", final_score=65.0, match_status="MATCH"
        ),
        MatchResult(
            job_id=2, title="Job 2", final_score=85.0, match_status="MATCH"
        ),
        MatchResult(
            job_id=3, title="Job 3", final_score=95.0, match_status="FILTERED"
        ),
        MatchResult(
            job_id=4, title="Job 4", final_score=78.5, match_status="MATCH"
        ),
    ]

    service = DigestService(min_score=70.0, max_jobs=10)
    filtered = service.filter_and_sort_matches(matches)

    assert len(filtered) == 2
    assert filtered[0].job_id == 2  # 85.0
    assert filtered[1].job_id == 4  # 78.5


def test_digest_service_max_jobs_limit():
    """Test that max_jobs limit is respected."""
    matches = [
        MatchResult(job_id=i, title=f"Job {i}", final_score=80.0 + i, match_status="MATCH")
        for i in range(1, 15)
    ]

    service = DigestService(min_score=70.0, max_jobs=5)
    filtered = service.filter_and_sort_matches(matches)

    assert len(filtered) == 5
    assert filtered[0].job_id == 14  # highest score


def test_digest_service_format_job_card():
    """Test formatting of a single job card."""
    match = MatchResult(
        job_id=101,
        source_job_id="AD123",
        title="Senior AI Engineer",
        company="Tech Corp",
        location="Bengaluru",
        similarity_score=0.88,
        skill_score=0.75,
        rule_score=1.0,
        final_score=87.4,
        matched_skills=["Python", "PyTorch", "SQL"],
        missing_skills=["Docker"],
        experience_status="MATCH",
        location_status="MATCH",
        match_status="MATCH",
    )
    job = Job(
        id=101,
        source="Adzuna",
        source_job_id="AD123",
        title="Senior AI Engineer",
        company="Tech Corp",
        location="Bengaluru",
        url="https://example.com/jobs/101",
    )

    service = DigestService()
    card = service.format_job_card(match, job=job, index=1)

    assert "1. Senior AI Engineer" in card
    assert "Company: Tech Corp" in card
    assert "Location: Bengaluru" in card
    assert "Match Score: 87.4/100" in card
    assert "Semantic: 0.88" in card
    assert "Skill Match: 75%" in card
    assert "Python, PyTorch, SQL" in card
    assert "Docker" in card
    assert "Experience: MATCH" in card
    assert "Location: MATCH" in card
    assert "Source: Adzuna" in card
    assert "Apply: https://example.com/jobs/101" in card


def test_digest_service_empty_digest_default():
    """Test that empty matches list produces empty chunks by default."""
    service = DigestService(min_score=70.0, send_empty=False)
    chunks = service.build_digest_chunks(matches=[])
    assert chunks == []


def test_digest_service_empty_digest_send_empty_true():
    """Test that send_empty=True produces an empty digest chunk."""
    service = DigestService(min_score=70.0, send_empty=True)
    chunks = service.build_digest_chunks(matches=[])
    assert len(chunks) == 1
    assert "AI JOB DIGEST" in chunks[0].text
    assert chunks[0].job_ids == []


def test_digest_service_message_chunking():
    """Test that oversized digests are cleanly split into multiple chunks while keeping job card boundaries intact."""
    matches = [
        MatchResult(
            job_id=i,
            title=f"AI Engineer Position #{i}",
            company="Example Corp",
            location="Bengaluru",
            similarity_score=0.85,
            skill_score=0.80,
            final_score=85.0,
            matched_skills=["Python", "FastAPI", "PyTorch"],
            missing_skills=["Kubernetes"],
            experience_status="MATCH",
            location_status="MATCH",
            match_status="MATCH",
        )
        for i in range(1, 10)
    ]

    # Use a small max_msg_len to force chunking across multiple messages
    service = DigestService(min_score=70.0, max_jobs=10, max_msg_len=800)
    chunks = service.build_digest_chunks(matches=matches)

    assert len(chunks) > 1

    # Verify that total job IDs across chunks equal total eligible jobs
    all_chunk_job_ids = []
    for chunk in chunks:
        assert len(chunk.text) <= 800
        all_chunk_job_ids.extend(chunk.job_ids)

    assert sorted(all_chunk_job_ids) == list(range(1, 10))

    # Verify header appears in the first chunk
    assert "AI JOB DIGEST" in chunks[0].text
