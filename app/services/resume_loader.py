"""
Resume loader service for reading and normalizing the user's base resume.
"""

import os
import re
from app.db.models import Resume


def load_base_resume_text(resume_path: str) -> str:
    """
    Reads, validates, and normalizes the raw base resume text from file.

    Args:
        resume_path: Path to the resume text file.

    Returns:
        str: Cleaned, normalized resume text string.

    Raises:
        FileNotFoundError: If the resume file does not exist.
        ValueError: If the resume file is empty or contains only whitespace.
    """
    if not os.path.exists(resume_path):
        raise FileNotFoundError(
            f"Base resume file not found at: '{resume_path}'. "
            "Please ensure your resume file exists."
        )

    with open(resume_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if not content or not content.strip():
        raise ValueError(
            f"Base resume file at '{resume_path}' is empty. "
            "Please provide a valid resume content file."
        )

    # Normalize whitespace: collapse multiple blank lines into two, replace tabs with spaces
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    return normalized.strip()


def load_resume(resume_path: str) -> Resume:
    """
    Loads resume file and initializes an internal Resume object.
    """
    clean_text = load_base_resume_text(resume_path)
    return Resume(
        raw_text=clean_text,
        normalized_text=clean_text.lower(),
        skills=set(),
    )
