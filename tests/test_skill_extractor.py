"""
Tests for app/services/skill_extractor.py.
"""

from app.services.skill_extractor import (
    calculate_skill_overlap,
    extract_skills,
)


def test_extract_skills_canonicalization_and_case_insensitivity():
    """Test extracting skills with lower case, aliases, and synonyms."""
    text = "We require strong PYTHON, PyTorch, sklearn, and Experience with postgresql and Docker."
    skills = extract_skills(text)

    assert "Python" in skills
    assert "PyTorch" in skills
    assert "Scikit-learn" in skills
    assert "SQL" in skills
    assert "Docker" in skills


def test_extract_skills_false_positive_protection():
    """Test word boundaries to avoid matching random substrings like 'r' or 'cv' inside words."""
    text = "Our company offers a great workplace environment with competitive salaries."
    skills = extract_skills(text)

    # Ensure 'R' or 'CV' or 'AI' inside 'workplace' or 'salaries' are not falsely matched
    assert "RAG" not in skills
    assert "Computer Vision" not in skills


def test_calculate_skill_overlap():
    """Test skill overlap metrics calculation."""
    resume_skills = {"Python", "SQL", "PyTorch", "OpenCV"}
    job_skills = {"Python", "SQL", "PyTorch", "TensorFlow", "Docker"}

    matched, missing, score = calculate_skill_overlap(resume_skills, job_skills)

    assert matched == {"Python", "SQL", "PyTorch"}
    assert missing == {"TensorFlow", "Docker"}
    assert round(score, 2) == 0.60  # 3 matched / 5 total = 0.60


def test_calculate_skill_overlap_empty_job_skills():
    """Test default score when job specifies no recognizable skills."""
    resume_skills = {"Python", "SQL"}
    job_skills = set()

    matched, missing, score = calculate_skill_overlap(resume_skills, job_skills)

    assert matched == set()
    assert missing == set()
    assert score == 0.5
