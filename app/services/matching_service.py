"""
Matching service orchestrating resume loading, skill extraction, batch embeddings,
cosine similarity, rule-based filtering, and match score ranking.
"""

import logging
from typing import List, Optional

from app.config import Config
from app.db.models import Job, MatchResult, Resume
from app.services.career_taxonomy import classify_role_family, is_ai_career_relevant
from app.services.embedding_service import EmbeddingService
from app.services.resume_loader import load_resume
from app.services.rule_matcher import evaluate_rules
from app.services.skill_extractor import calculate_skill_overlap, extract_skills

logger = logging.getLogger(__name__)


def construct_job_text(job: Job) -> str:
    """
    Constructs a clean, deterministic text representation of a job for embedding.
    """
    parts = []
    if job.title:
        parts.append(job.title)
    if job.category:
        parts.append(f"Category: {job.category}")
    if job.company:
        parts.append(f"Company: {job.company}")
    if job.location:
        parts.append(f"Location: {job.location}")
    if job.description:
        parts.append(job.description)
    return ". ".join(parts)


class MatchingService:
    """
    Engine for matching candidate resume against stored jobs.
    """

    def __init__(self, config: Config, embedding_service: Optional[EmbeddingService] = None):
        self.config = config
        self.embedding_service = (
            embedding_service
            if embedding_service is not None
            else EmbeddingService(model_name=config.embedding_model)
        )

    def prepare_resume(self, resume_path: Optional[str] = None) -> Resume:
        """
        Loads base resume, extracts canonical skills, and pre-computes resume embedding once.
        """
        path = resume_path or self.config.resume_path
        resume = load_resume(path)
        resume.skills = extract_skills(resume.raw_text)

        logger.info(
            "Loaded resume from '%s' (%d skills extracted)", path, len(resume.skills)
        )

        # Pre-compute resume embedding vector once
        resume.embedding = self.embedding_service.encode_text(resume.raw_text)
        return resume

    def match_job(
        self, resume: Resume, job: Job, job_embedding: Optional[list] = None
    ) -> MatchResult:
        """
        Evaluates match between candidate resume and a single job.
        """
        # 1. Job text construction & Skill extraction
        job_text = construct_job_text(job)
        job_skills = extract_skills(job.title + " " + (job.category or "") + " " + job.description)

        # 2. Skill overlap evaluation
        matched_skills, missing_skills, skill_score = calculate_skill_overlap(
            resume_skills=resume.skills, job_skills=job_skills
        )

        # 3. Taxonomy classification & Rule evaluation
        role_family, canonical_role, role_tax_score = classify_role_family(job.title, job.description)
        is_relevant = is_ai_career_relevant(job.title, job.description)
        
        if is_relevant or role_family:
            role_score = 100.0
        else:
            role_score = 30.0

        rule_eval = evaluate_rules(
            title=job.title,
            description=job.description,
            location=job.location,
            preferred_locations=self.config.preferred_locations,
        )

        # 4. Semantic similarity
        if job_embedding is None:
            job_embedding = self.embedding_service.encode_text(job_text)

        if resume.embedding is None:
            resume.embedding = self.embedding_service.encode_text(resume.raw_text)

        similarity_score = self.embedding_service.calculate_cosine_similarity(
            resume.embedding, job_embedding
        )

        # 5. Composite score calculation
        raw_final_score = (
            (similarity_score * self.config.semantic_weight)
            + (skill_score * self.config.skill_weight)
            + (rule_eval.rule_score * self.config.rule_weight)
        ) * 100.0

        final_score = round(max(0.0, min(100.0, raw_final_score)), 1)
        overall_score = final_score

        # 6. Category assignment
        if overall_score >= getattr(self.config, "match_threshold_strong", 75.0):
            match_category = "STRONG_MATCH"
        elif overall_score >= getattr(self.config, "match_threshold_potential", 50.0):
            match_category = "POTENTIAL_MATCH"
        elif overall_score >= getattr(self.config, "match_threshold_low", 30.0):
            match_category = "LOW_MATCH"
        else:
            match_category = "NOT_RELEVANT"

        # Legacy status assignment
        if rule_eval.is_hard_filtered:
            match_status = "FILTERED"
        elif final_score >= self.config.min_match_score:
            match_status = "MATCH"
        else:
            match_status = "PARTIAL_MATCH"

        return MatchResult(
            job_id=job.id,
            source_job_id=job.source_job_id,
            title=job.title,
            company=job.company,
            location=job.location,
            similarity_score=round(similarity_score, 4),
            skill_score=round(skill_score, 4),
            rule_score=round(rule_eval.rule_score, 4),
            final_score=final_score,
            matched_skills=sorted(list(matched_skills)),
            missing_skills=sorted(list(missing_skills)),
            experience_status=rule_eval.experience_status,
            location_status=rule_eval.location_status,
            match_status=match_status,
            reasons=rule_eval.reasons,
            match_category=match_category,
            role_family=role_family,
            canonical_role=canonical_role,
            experience_match=rule_eval.experience_status,
            skill_gaps=sorted(list(missing_skills)),
            role_score=round(role_score, 2),
            experience_score=round(rule_eval.experience_score * 100.0, 2),
            education_score=round(rule_eval.education_score * 100.0, 2),
            location_score=round(rule_eval.location_score * 100.0, 2),
            seniority_score=round(rule_eval.seniority_score * 100.0, 2),
        )

    def match_all_jobs(
        self, resume: Resume, jobs: List[Job]
    ) -> List[MatchResult]:
        """
        Matches resume against a list of jobs using batch embeddings for efficiency.

        Returns:
            List[MatchResult]: Ranked list of match results ordered by final_score DESC.
        """
        if not jobs:
            return []

        logger.info("Generating batch embeddings for %d jobs...", len(jobs))
        job_texts = [construct_job_text(job) for job in jobs]
        job_embeddings = self.embedding_service.encode_batch(job_texts)

        results: List[MatchResult] = []
        for idx, job in enumerate(jobs):
            match_res = self.match_job(
                resume=resume, job=job, job_embedding=job_embeddings[idx]
            )
            results.append(match_res)

        # Rank results by final_score descending
        results.sort(key=lambda r: r.final_score, reverse=True)
        return results
