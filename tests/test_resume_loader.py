"""
Tests for app/services/resume_loader.py.
"""

import pytest

from app.db.models import Resume
from app.services.resume_loader import load_base_resume_text, load_resume


def test_load_base_resume_text_success(tmp_path):
    """Test loading and normalizing a valid resume text file."""
    resume_file = tmp_path / "resume.txt"
    resume_file.write_text("   John Doe\n\n\nSkills: Python,  SQL\t\tDeep Learning   \n\n")

    text = load_base_resume_text(str(resume_file))
    assert "John Doe" in text
    assert "Skills: Python, SQL Deep Learning" in text
    assert "\n\n\n" not in text  # Multiple blank lines collapsed


def test_load_base_resume_text_missing_file_raises_error():
    """Test that missing resume file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_base_resume_text("non_existent_resume_file.txt")
    assert "Base resume file not found" in str(exc_info.value)


def test_load_base_resume_text_empty_file_raises_error(tmp_path):
    """Test that empty resume file raises ValueError."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("   \n\t  ")

    with pytest.raises(ValueError) as exc_info:
        load_base_resume_text(str(empty_file))
    assert "is empty" in str(exc_info.value)


def test_load_resume_object(tmp_path):
    """Test initializing Resume object from loader."""
    resume_file = tmp_path / "resume.txt"
    resume_file.write_text("Python Developer")

    res = load_resume(str(resume_file))
    assert isinstance(res, Resume)
    assert res.raw_text == "Python Developer"
    assert res.normalized_text == "python developer"
