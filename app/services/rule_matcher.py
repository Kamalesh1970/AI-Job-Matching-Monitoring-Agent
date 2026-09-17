"""
Rule-based matching engine for evaluating experience and location compatibility.
Distinguishes HARD CONSTRAINTS from SOFT MATCH SIGNALS and handles UNKNOWN states.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

COMPATIBLE_EXPERIENCE_PATTERNS = [
    r"\binternship\b",
    r"\bintern\b",
    r"\bfresher\b",
    r"\bgraduate\b",
    r"\bentry\s*level\b",
    r"\bjunior\b",
    r"\b0\s*[-–\s]\s*1\s*year",
    r"\b0\s*years?\b",
    r"\b1\s*year\b",
]

INCOMPATIBLE_EXPERIENCE_TITLE_PATTERNS = [
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\blead\b",
    r"\bprincipal\b",
    r"\bmanager\b",
    r"\barchitect\b",
    r"\bdirector\b",
    r"\bhead\s+of\b",
    r"\bvp\b",
]

INCOMPATIBLE_EXPERIENCE_YEARS_PATTERNS = [
    r"\b[5-9]\s*\+?\s*years?\b",
    r"\b1[0-9]\s*\+?\s*years?\b",
    r"\b5\s*[-–\s]\s*10\s*years?\b",
]


@dataclass
class RuleEvaluation:
    """Evaluation output from rule matching logic."""

    experience_status: str  # MATCH, MISMATCH, UNKNOWN
    location_status: str    # MATCH, MISMATCH, UNKNOWN
    rule_score: float       # 0.0 to 1.0
    is_hard_filtered: bool
    reasons: List[str] = field(default_factory=list)


def evaluate_experience(title: str, description: str) -> Tuple[str, Optional[str]]:
    """
    Evaluates job title and description against experience rules.

    Returns:
        Tuple[str, Optional[str]]: (experience_status, reason_if_mismatch)
    """
    title_lower = title.lower() if title else ""
    desc_lower = description.lower() if description else ""

    # Check title for senior/lead keywords (High confidence mismatch)
    for pattern in INCOMPATIBLE_EXPERIENCE_TITLE_PATTERNS:
        if re.search(pattern, title_lower):
            return "MISMATCH", "Job title indicates a senior, lead, or management level role."

    # Check description for 5+ years requirement
    for pattern in INCOMPATIBLE_EXPERIENCE_YEARS_PATTERNS:
        if re.search(pattern, desc_lower):
            return "MISMATCH", "Job description requires 5+ years of experience, exceeding fresher target."

    # Check for compatible entry-level keywords in title or description
    for pattern in COMPATIBLE_EXPERIENCE_PATTERNS:
        if re.search(pattern, title_lower) or re.search(pattern, desc_lower):
            return "MATCH", None

    # If neither explicit entry-level nor senior requirements are detected
    return "UNKNOWN", None


def evaluate_location(
    location: str, preferred_locations: List[str]
) -> Tuple[str, Optional[str]]:
    """
    Evaluates job location against user preferred locations.

    Returns:
        Tuple[str, Optional[str]]: (location_status, reason_if_mismatch)
    """
    if not location or not location.strip():
        return "UNKNOWN", None

    loc_lower = location.lower().strip()
    pref_lowers = [p.lower().strip() for p in preferred_locations if p.strip()]

    # Check if location contains any preferred location substring (e.g. Remote, India, Bengaluru)
    for pref in pref_lowers:
        if pref in loc_lower or loc_lower in pref:
            return "MATCH", None

    # If preferred locations list includes "india" and location is in India or Remote
    if "india" in pref_lowers and ("in" in loc_lower or "india" in loc_lower or "remote" in loc_lower):
        return "MATCH", None

    return "MISMATCH", f"Location '{location}' does not match preferred locations list."


def evaluate_rules(
    title: str, description: str, location: str, preferred_locations: List[str]
) -> RuleEvaluation:
    """
    Executes rule-based matching evaluation.

    Returns:
        RuleEvaluation: Container with statuses, composite rule score, and filter decisions.
    """
    exp_status, exp_reason = evaluate_experience(title, description)
    loc_status, loc_reason = evaluate_location(location, preferred_locations)

    reasons = []
    is_hard_filtered = False

    # Hard Filter Condition: Experience Mismatch (Senior / 5+ yrs requirement for fresher)
    if exp_status == "MISMATCH":
        is_hard_filtered = True
        if exp_reason:
            reasons.append(exp_reason)

    if loc_status == "MISMATCH" and loc_reason:
        reasons.append(loc_reason)

    # Calculate rule score (0.0 to 1.0)
    # Experience weight: 0.6, Location weight: 0.4
    exp_score = 1.0 if exp_status == "MATCH" else (0.5 if exp_status == "UNKNOWN" else 0.0)
    loc_score = 1.0 if loc_status == "MATCH" else (0.5 if loc_status == "UNKNOWN" else 0.0)

    composite_rule_score = (exp_score * 0.6) + (loc_score * 0.4)

    return RuleEvaluation(
        experience_status=exp_status,
        location_status=loc_status,
        rule_score=composite_rule_score,
        is_hard_filtered=is_hard_filtered,
        reasons=reasons,
    )
