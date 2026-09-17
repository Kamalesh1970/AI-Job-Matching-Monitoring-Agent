"""
Tests for app/services/deduplication.py.
"""

from app.services.deduplication import (
    generate_fingerprint,
    normalize_text_for_fingerprint,
)


def test_normalize_text_for_fingerprint():
    """Test text normalization for fingerprint consistency."""
    assert normalize_text_for_fingerprint("  Google, Inc. ") == "google inc"
    assert normalize_text_for_fingerprint("Machine-Learning   Engineer!!") == "machine learning engineer"
    assert normalize_text_for_fingerprint(None) == ""


def test_fingerprint_deterministic():
    """Test that identical inputs produce the exact same fingerprint SHA256 hex string."""
    fp1 = generate_fingerprint("Google India", "AI Engineer", "Bengaluru")
    fp2 = generate_fingerprint("Google India", "AI Engineer", "Bengaluru")
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_case_and_punctuation_insensitive():
    """Test that casing, extra spaces, and punctuation variations produce identical fingerprints."""
    fp1 = generate_fingerprint("Google, Inc.", "AI Engineer!", "Bengaluru, India")
    fp2 = generate_fingerprint("google inc", "ai engineer", "bengaluru india")
    fp3 = generate_fingerprint("  GOOGLE INC.  ", "  AI  ENGINEER  ", "Bengaluru  India")

    assert fp1 == fp2
    assert fp2 == fp3


def test_fingerprint_different_jobs_produce_different_hashes():
    """Test that different jobs produce distinct fingerprints."""
    fp1 = generate_fingerprint("Google", "AI Engineer", "Bengaluru")
    fp2 = generate_fingerprint("Google", "Data Scientist", "Bengaluru")
    fp3 = generate_fingerprint("Microsoft", "AI Engineer", "Bengaluru")

    assert fp1 != fp2
    assert fp1 != fp3
    assert fp2 != fp3
