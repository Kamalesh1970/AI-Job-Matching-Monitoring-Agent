"""
Phase 11 Web UI & API integration tests.
Tests API routes, dashboard metrics, jobs filtering, job details, companies, applications,
gmail intelligence, interviews, skills, resumes, analytics, settings, and error states.
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.db.database import (
    initialize_database,
    insert_job,
    save_match_result,
    save_tailored_resume,
)
from app.db.models import Job, MatchResult


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_jobs.db")


@pytest.fixture
def client(test_db_path, monkeypatch):
    conn = initialize_database(test_db_path)

    # Insert sample test jobs
    j1 = Job(
        id=1,
        source="Adzuna",
        source_job_id="job-101",
        title="Junior Machine Learning Engineer",
        company="AI Core Tech",
        location="Bangalore",
        description="Python, PyTorch, ML models.",
        url="https://example.com/job/101",
    )
    j2 = Job(
        id=2,
        source="Internshala",
        source_job_id="job-102",
        title="AI Research Intern",
        company="DeepMind Labs",
        location="Remote",
        description="Deep learning research.",
        url="https://example.com/job/102",
    )
    insert_job(conn, j1)
    insert_job(conn, j2)

    # Insert sample match results
    m1 = MatchResult(
        job_id=1,
        source_job_id="job-101",
        title="Junior Machine Learning Engineer",
        company="AI Core Tech",
        location="Bangalore",
        similarity_score=0.85,
        skill_score=0.80,
        rule_score=0.90,
        final_score=82.5,
        matched_skills=["Python", "PyTorch"],
        missing_skills=["Docker"],
        match_category="STRONG_MATCH",
        role_family="Machine Learning",
        canonical_role="Machine Learning Engineer",
        experience_match="MATCH",
        skill_gaps=["Docker"],
        role_score=85.0,
        experience_score=100.0,
        education_score=100.0,
        location_score=80.0,
        seniority_score=90.0,
    )
    m2 = MatchResult(
        job_id=2,
        source_job_id="job-102",
        title="AI Research Intern",
        company="DeepMind Labs",
        location="Remote",
        similarity_score=0.70,
        skill_score=0.60,
        rule_score=0.70,
        final_score=68.0,
        matched_skills=["Python"],
        missing_skills=["TensorFlow", "Kubernetes"],
        match_category="POTENTIAL_MATCH",
        role_family="AI Research",
        canonical_role="AI Researcher",
        experience_match="POSSIBLE_MATCH",
        skill_gaps=["TensorFlow", "Kubernetes"],
        role_score=70.0,
        experience_score=90.0,
        education_score=100.0,
        location_score=100.0,
        seniority_score=80.0,
    )
    save_match_result(conn, m1)
    save_match_result(conn, m2)

    # Save sample tailored resume
    save_tailored_resume(
        conn=conn,
        job_id=1,
        match_score=82.5,
        provider="Gemini",
        model="gemini-2.5-flash",
        status="DRAFT",
        resume_content={"summary": "Tailored for AI Core Tech", "skills": ["Python", "PyTorch"]},
    )
    conn.close()

    # Mock load_config to point to test_db_path
    def mock_load_config():
        from app.config import Config
        return Config(
            adzuna_app_id="test",
            adzuna_app_key="test",
            db_path=test_db_path,
        )

    monkeypatch.setattr("app.api.app.load_config", mock_load_config)

    app = create_app()
    return TestClient(app)


def test_dashboard_endpoint(client):
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["total_jobs"] == 2
    assert data["strong_matches"] == 1
    assert data["potential_matches"] == 1
    assert "source_distribution" in data
    assert "top_matching_jobs" in data
    assert len(data["top_matching_jobs"]) == 2


def test_jobs_list_and_filters(client):
    res = client.get("/api/jobs")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["jobs"]) == 2

    # Filter by search
    res_search = client.get("/api/jobs?search=Machine")
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 1

    # Filter by match category
    res_cat = client.get("/api/jobs?match_category=STRONG_MATCH")
    assert res_cat.status_code == 200
    assert res_cat.json()["total"] == 1


def test_job_detail_endpoint(client):
    res = client.get("/api/jobs/1")
    assert res.status_code == 200
    data = res.json()
    assert data["job"]["title"] == "Junior Machine Learning Engineer"
    assert data["match"]["match_category"] == "STRONG_MATCH"
    assert data["candidate_profile"]["experience_level"] == "FRESHER"

    # Non-existent job
    res_404 = client.get("/api/jobs/9999")
    assert res_404.status_code == 404


def test_companies_endpoint(client):
    res = client.get("/api/companies")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    company_names = [c["name"] for c in data["companies"]]
    assert "AI Core Tech" in company_names
    assert "DeepMind Labs" in company_names


def test_applications_endpoint(client):
    res = client.get("/api/applications")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["applications"][0]["job_title"] == "Junior Machine Learning Engineer"


def test_gmail_intelligence_endpoint(client):
    res = client.get("/api/gmail")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert "categories" in data


def test_interviews_endpoint(client):
    res = client.get("/api/interviews")
    assert res.status_code == 200
    data = res.json()
    assert data["interviews"] == []
    assert data["status"] == "NO_INTERVIEWS_SCHEDULED"


def test_skills_endpoint(client):
    res = client.get("/api/skills")
    assert res.status_code == 200
    data = res.json()
    assert "candidate_skills" in data
    assert "frequently_requested_skills" in data


def test_resumes_and_status_update(client):
    res = client.get("/api/resumes")
    assert res.status_code == 200
    data = res.json()
    assert data["total_drafts"] == 1
    draft_id = data["tailored_drafts"][0]["id"]

    # Update draft status
    res_update = client.post(f"/api/resumes/{draft_id}/status", json={"status": "APPROVED"})
    assert res_update.status_code == 200
    assert res_update.json()["new_status"] == "APPROVED"

    # Invalid status error test
    res_bad = client.post(f"/api/resumes/{draft_id}/status", json={"status": "INVALID_STATUS"})
    assert res_bad.status_code == 400


def test_analytics_endpoint(client):
    res = client.get("/api/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "match_category_distribution" in data
    assert "experience_status_distribution" in data
    assert "jobs_by_source" in data


def test_settings_endpoint(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["candidate_status"] == "FINAL_YEAR_STUDENT"
    assert "GEMINI_API_KEY" not in data
    assert "telegram_bot_token" not in data
