"""
Deterministic Truth Validator for generated tailored resumes.
Compares generated output against the master ResumeProfile source of truth
to detect fabricated skills, technologies, companies, job titles, degrees,
certifications, metrics, achievements, and years of experience.
"""

import re
from typing import List, Set
from app.llm.schemas import ResumeProfile, TailoredResume, ValidationResult


class TruthValidator:
    """
    Validates a generated TailoredResume against a master ResumeProfile.
    Returns a ValidationResult indicating whether the draft is valid or invalid.
    """

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"[^\w\s]", "", text.lower()).strip()

    @staticmethod
    def _extract_numbers_and_metrics(text: str) -> Set[str]:
        """Extracts numeric values, percentages, and metrics from text."""
        matches = re.findall(r"(?:\$\d+|\d+%|\d+x|\d+\+|\b\d+\b)", text.lower())
        return set(matches)

    @classmethod
    def validate(
        cls, profile: ResumeProfile, tailored: TailoredResume
    ) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        source_skills_norm = {cls._normalize(s) for s in profile.skills if s.strip()}

        # Flatten source text for general metric & substring checking
        source_text = " ".join(
            [
                profile.name,
                profile.summary,
                " ".join(profile.skills),
                str(profile.experience),
                str(profile.projects),
                str(profile.education),
                " ".join(profile.certifications),
                " ".join(profile.achievements),
                " ".join(profile.links),
            ]
        ).lower()
        source_metrics = cls._extract_numbers_and_metrics(source_text)

        # 1. Check generated skills & technologies against source
        for skill in tailored.skills:
            if not skill or not skill.strip():
                continue
            norm_skill = cls._normalize(skill)
            matched = any(
                norm_skill == src or norm_skill in src or src in norm_skill
                for src in source_skills_norm
            )
            if not matched and norm_skill not in source_text:
                violations.append(f"Unsupported skill claimed: '{skill}'")

        # 2. Check certifications
        source_certs_norm = {
            cls._normalize(c) for c in profile.certifications if c.strip()
        }
        for cert in tailored.certifications:
            if not cert or not cert.strip():
                continue
            norm_cert = cls._normalize(cert)
            matched = any(
                norm_cert in src or src in norm_cert for src in source_certs_norm
            )
            if not matched and norm_cert not in source_text:
                violations.append(f"Unsupported certification claimed: '{cert}'")

        # 3. Check companies & job titles in experience
        source_exp_str = str(profile.experience).lower()
        for exp in tailored.experience:
            if isinstance(exp, dict):
                company = exp.get("company", "").strip()
                title = exp.get("title", "").strip()
            else:
                company = ""
                title = str(exp).strip()

            if company and cls._normalize(company) not in source_exp_str:
                if cls._normalize(company) not in source_text:
                    violations.append(
                        f"Unsupported company claimed in experience: '{company}'"
                    )

            if title and cls._normalize(title) not in source_exp_str:
                words = [
                    w for w in cls._normalize(title).split() if len(w) > 3
                ]
                if not words or not any(word in source_text for word in words):
                    violations.append(
                        f"Unsupported job title claimed in experience: '{title}'"
                    )

        # 4. Check education
        source_edu_str = str(profile.education).lower()
        for edu in tailored.education:
            if isinstance(edu, dict):
                degree = edu.get("degree", "").strip()
                institution = edu.get("institution", "").strip()
            else:
                degree = str(edu).strip()
                institution = ""

            if degree and cls._normalize(degree) not in source_edu_str:
                words = [
                    w for w in cls._normalize(degree).split() if len(w) > 3
                ]
                if not words or not any(word in source_text for word in words):
                    violations.append(
                        f"Unsupported degree claimed in education: '{degree}'"
                    )

            if (
                institution
                and cls._normalize(institution) not in source_edu_str
            ):
                words = [
                    w
                    for w in cls._normalize(institution).split()
                    if len(w) > 3
                ]
                if not words or not any(word in source_text for word in words):
                    violations.append(
                        f"Unsupported educational institution claimed: '{institution}'"
                    )

        # 5. Check technologies in projects
        source_proj_str = str(profile.projects).lower()
        for proj in tailored.projects:
            if isinstance(proj, dict):
                techs = proj.get("technologies", [])
                for tech in techs:
                    norm_tech = cls._normalize(tech)
                    if (
                        norm_tech
                        and norm_tech not in source_skills_norm
                        and norm_tech not in source_text
                    ):
                        violations.append(
                            f"Unsupported technology claimed in project: '{tech}'"
                        )

        # 6. Check numeric metrics and achievements in summary, experience, projects
        tailored_text = " ".join(
            [
                tailored.summary,
                str(tailored.experience),
                str(tailored.projects),
            ]
        ).lower()

        tailored_metrics = cls._extract_numbers_and_metrics(tailored_text)
        unsupported_metrics = tailored_metrics - source_metrics
        for metric in unsupported_metrics:
            if (
                "%" in metric
                or "$" in metric
                or "x" in metric
                or "+" in metric
                or (metric.isdigit() and int(metric) > 5)
            ):
                violations.append(
                    f"Fabricated metric or number claimed: '{metric}'"
                )

        # 7. Check years of experience claims
        yoe_matches = re.findall(
            r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", tailored_text
        )
        source_yoe_matches = re.findall(
            r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", source_text
        )
        if yoe_matches and not source_yoe_matches:
            for yoe in yoe_matches:
                if yoe not in source_metrics:
                    violations.append(
                        f"Fabricated years of experience claimed: '{yoe} years'"
                    )

        # 8. Collect any warnings from tailored resume
        if tailored.warnings:
            warnings.extend(tailored.warnings)

        valid = len(violations) == 0
        return ValidationResult(
            valid=valid, violations=violations, warnings=warnings
        )
