"""
Resume Tailoring Service orchestrating threshold checks, prompt construction,
LLM provider calls, truth validation, and SQLite draft persistence.
"""

import os
import sqlite3
from typing import Dict, Any, Optional

from app.config import Config
from app.db.database import save_tailored_resume
from app.db.models import Job, MatchResult
from app.llm.base import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.llm.schemas import ResumeProfile, TailoredResume, ValidationResult
from app.llm.validator import TruthValidator


class ResumeTailoringService:
    """
    Service responsible for managing LLM resume tailoring workflow.
    Ensures zero live calls when disabled or below threshold, validates truthfulness,
    and isolates failures safely.
    """

    def __init__(self, config: Config, provider: Optional[LLMProvider] = None):
        self.config = config
        if provider:
            self.provider = provider
        elif config.llm_enabled:
            if config.llm_provider.lower() == "openai":
                self.provider = OpenAIProvider(config)
            else:
                self.provider = GeminiProvider(config)
        else:
            self.provider = None

    def _get_configured_model(self) -> str:
        """Returns the configured model name based on provider."""
        if self.config.llm_provider.lower() == "openai":
            return self.config.openai_model
        return self.config.gemini_model

    def load_master_resume(self) -> ResumeProfile:
        """Loads master resume file and returns a structured ResumeProfile."""
        resume_path = self.config.resume_path
        if os.path.exists(resume_path):
            with open(resume_path, "r", encoding="utf-8") as f:
                content = f.read()
            return ResumeProfile.from_text(content)
        return ResumeProfile()

    def tailor_resume_for_job(
        self,
        conn: sqlite3.Connection,
        job: Job,
        match: MatchResult,
    ) -> Dict[str, Any]:
        """
        Executes resume tailoring workflow for a specific job and match result.

        Returns:
            Dict containing draft record details including id, status, and validation results.
        """
        model_name = self._get_configured_model()

        # 1. Check if LLM is enabled
        if not self.config.llm_enabled:
            draft_id = save_tailored_resume(
                conn=conn,
                job_id=job.id or 0,
                match_score=match.final_score,
                provider=self.config.llm_provider,
                model=model_name,
                status="SKIPPED_LOW_MATCH",
                changes=["LLM tailoring disabled in configuration."],
            )
            return {"id": draft_id, "status": "SKIPPED_LOW_MATCH", "job_id": job.id}

        # 2. Check match threshold
        raw_threshold = self.config.llm_match_threshold
        effective_threshold = (
            raw_threshold * 100.0 if raw_threshold <= 1.0 else raw_threshold
        )

        if match.final_score < effective_threshold:
            draft_id = save_tailored_resume(
                conn=conn,
                job_id=job.id or 0,
                match_score=match.final_score,
                provider=self.config.llm_provider,
                model=model_name,
                status="SKIPPED_LOW_MATCH",
                changes=[
                    f"Match score {match.final_score:.1f}% below threshold {effective_threshold:.1f}%."
                ],
            )
            return {"id": draft_id, "status": "SKIPPED_LOW_MATCH", "job_id": job.id}

        # 3. Load master resume
        profile = self.load_master_resume()

        # 4. Build prompt
        user_prompt = build_user_prompt(profile=profile, job=job, match=match)

        # 5. Call LLM provider with fault isolation
        try:
            if not self.provider:
                if self.config.llm_provider.lower() == "openai":
                    self.provider = OpenAIProvider(self.config)
                else:
                    self.provider = GeminiProvider(self.config)

            tailored: TailoredResume = self.provider.generate_structured(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                response_model=TailoredResume,
            )

            # 6. Validate response truthfulness
            val_result: ValidationResult = TruthValidator.validate(profile, tailored)
            status = "VALIDATED" if val_result.valid else "INVALID"

            # 7. Persist draft
            draft_id = save_tailored_resume(
                conn=conn,
                job_id=job.id or 0,
                match_score=match.final_score,
                provider=self.config.llm_provider,
                model=model_name,
                status=status,
                resume_content=tailored.model_dump(),
                changes=tailored.changes,
                warnings=tailored.warnings + val_result.warnings,
                validation_result=val_result.model_dump(),
            )

            return {
                "id": draft_id,
                "job_id": job.id,
                "status": status,
                "match_score": match.final_score,
                "resume_content": tailored.model_dump(),
                "validation_result": val_result.model_dump(),
            }

        except Exception as exc:
            # Handle LLM error cleanly without breaking pipeline
            draft_id = save_tailored_resume(
                conn=conn,
                job_id=job.id or 0,
                match_score=match.final_score,
                provider=self.config.llm_provider,
                model=model_name,
                status="FAILED",
                changes=[f"LLM API call failed: {type(exc).__name__}"],
                warnings=[str(exc)],
            )
            return {
                "id": draft_id,
                "status": "FAILED",
                "job_id": job.id,
                "error": str(exc),
            }
