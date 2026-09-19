"""
Pydantic schemas for master resume source of truth, tailored resume output,
and truth validation results.
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExperienceItem(BaseModel):
    """Structured representation of a single work experience entry."""

    company: str = ""
    title: str = ""
    location: str = ""
    dates: str = ""
    bullets: List[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    """Structured representation of a project entry."""

    name: str = ""
    description: str = ""
    technologies: List[str] = Field(default_factory=list)
    bullets: List[str] = Field(default_factory=list)
    link: str = ""


class EducationItem(BaseModel):
    """Structured representation of an education entry."""

    institution: str = ""
    degree: str = ""
    field_of_study: str = ""
    dates: str = ""
    gpa: str = ""


class ResumeProfile(BaseModel):
    """
    Master Resume profile representing the single factual source of truth.
    Nothing outside this profile may be claimed by the LLM.
    """

    name: str = "Candidate"
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)

    @classmethod
    def from_text(cls, text: str) -> "ResumeProfile":
        """
        Parses raw resume text into a structured ResumeProfile.
        Extracts sections based on common headings.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return cls()

        name = lines[0]
        summary_lines = []
        skills = []
        certifications = []
        achievements = []
        experience = []
        projects = []
        education = []

        current_section = "summary"
        section_headers = {
            "summary": ["summary", "profile", "about", "objective"],
            "skills": ["skills", "technical skills", "core competencies"],
            "experience": ["experience", "work experience", "employment history", "professional experience"],
            "projects": ["projects", "personal projects", "key projects"],
            "education": ["education", "academic background"],
            "certifications": ["certifications", "licenses", "certificates"],
            "achievements": ["achievements", "honors", "awards"],
        }

        for line in lines[1:]:
            lower = line.lower().rstrip(":")
            found_header = None
            for sec, headers in section_headers.items():
                if lower in headers or any(lower.startswith(h) for h in headers):
                    found_header = sec
                    break

            if found_header:
                current_section = found_header
                continue

            if current_section == "summary":
                summary_lines.append(line)
            elif current_section == "skills":
                # Split comma-separated or bullet points
                parts = [p.strip(" •-*") for p in re.split(r"[,;•|]", line) if p.strip(" •-*")]
                skills.extend(parts)
            elif current_section == "certifications":
                certifications.append(line.lstrip(" •-*"))
            elif current_section == "achievements":
                achievements.append(line.lstrip(" •-*"))
            elif current_section == "experience":
                if line.startswith("•") or line.startswith("-") or line.startswith("*"):
                    if experience:
                        bullets = experience[-1].get("bullets", [])
                        bullets.append(line.lstrip(" •-*"))
                        experience[-1]["bullets"] = bullets
                    else:
                        experience.append({"title": line.lstrip(" •-*"), "bullets": []})
                else:
                    experience.append({"title": line, "company": "", "bullets": []})
            elif current_section == "projects":
                if line.startswith("•") or line.startswith("-") or line.startswith("*"):
                    if projects:
                        bullets = projects[-1].get("bullets", [])
                        bullets.append(line.lstrip(" •-*"))
                        projects[-1]["bullets"] = bullets
                    else:
                        projects.append({"name": line.lstrip(" •-*"), "bullets": []})
                else:
                    projects.append({"name": line, "bullets": []})
            elif current_section == "education":
                education.append({"institution": line, "degree": ""})

        return cls(
            name=name,
            summary=" ".join(summary_lines),
            skills=skills if skills else [s.strip() for s in text.split("\n") if "python" in s.lower() or "sql" in s.lower()],
            experience=experience,
            projects=projects,
            education=education,
            certifications=certifications,
            achievements=achievements,
        )


class TailoredResume(BaseModel):
    """
    Pydantic schema for the structured response returned by the OpenAI API.
    """

    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    changes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """
    Structured result returned by the deterministic truth validator.
    """

    valid: bool = True
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
