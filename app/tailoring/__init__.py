"""
Resume Tailoring package alias for AI Job-Matching & Monitoring Agent.
"""

from app.llm.tailoring_service import ResumeTailoringService
from app.llm.validator import TruthValidator

__all__ = ["ResumeTailoringService", "TruthValidator"]
