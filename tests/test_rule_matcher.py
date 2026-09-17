"""
Tests for app/services/rule_matcher.py experience and location matching rules.
"""

from app.services.rule_matcher import (
    evaluate_experience,
    evaluate_location,
    evaluate_rules,
)


def test_evaluate_experience_fresher_internship():
    """Test fresher and internship experience detection."""
    status, reason = evaluate_experience(
        title="Machine Learning Intern",
        description="Looking for 0-1 years of experience or fresh graduates.",
    )
    assert status == "MATCH"
    assert reason is None


def test_evaluate_experience_senior_role():
    """Test senior role experience mismatch detection."""
    status, reason = evaluate_experience(
        title="Senior AI Engineer",
        description="Requires 7+ years of experience leading ML teams.",
    )
    assert status == "MISMATCH"
    assert reason is not None


def test_evaluate_location_preferred():
    """Test location evaluation for preferred cities and remote."""
    pref = ["Bengaluru", "Chennai", "Remote", "India"]

    loc1_status, _ = evaluate_location("Bengaluru, Karnataka, India", pref)
    assert loc1_status == "MATCH"

    loc2_status, _ = evaluate_location("Work from Home / Remote", pref)
    assert loc2_status == "MATCH"


def test_evaluate_location_non_preferred():
    """Test location evaluation for non-preferred locations."""
    pref = ["Bengaluru", "Chennai", "Remote"]

    status, reason = evaluate_location("London, United Kingdom", pref)
    assert status == "MISMATCH"
    assert reason is not None


def test_evaluate_rules_hard_filter():
    """Test evaluate_rules setting is_hard_filtered for senior role."""
    eval_res = evaluate_rules(
        title="Lead Machine Learning Engineer",
        description="Must have 8+ years experience.",
        location="Bengaluru, India",
        preferred_locations=["Bengaluru", "Remote"],
    )

    assert eval_res.is_hard_filtered is True
    assert eval_res.experience_status == "MISMATCH"
    assert eval_res.location_status == "MATCH"
    assert len(eval_res.reasons) > 0
