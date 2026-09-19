"""
Digest Service for formatting job matches and generating Telegram daily digests.
Handles filtering, sorting, limiting, message formatting, and boundary-aware chunking.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.config import Config
from app.db.models import Job, MatchResult


@dataclass
class DigestChunk:
    """
    Represents a single formatted Telegram message chunk and its constituent job IDs.
    """

    text: str
    job_ids: List[int] = field(default_factory=list)


class DigestService:
    """
    Service for constructing Telegram job digest messages.
    """

    def __init__(
        self,
        min_score: float = 70.0,
        max_jobs: int = 10,
        send_empty: bool = False,
        max_msg_len: int = 4000,
        config: Optional[Config] = None,
    ):
        """
        Initializes DigestService with thresholds and options.
        """
        if config:
            self.min_score = config.telegram_min_match_score
            self.max_jobs = config.telegram_max_jobs_per_digest
            self.send_empty = config.send_empty_digest
        else:
            self.min_score = min_score
            self.max_jobs = max_jobs
            self.send_empty = send_empty

        self.max_msg_len = max_msg_len

    def filter_and_sort_matches(
        self, matches: List[MatchResult], jobs_map: Optional[Dict[int, Job]] = None
    ) -> List[MatchResult]:
        """
        Filters matches meeting min_score and match_status != 'FILTERED',
        deduplicates cross-source candidates by fingerprint,
        sorted descending by final_score and limited to max_jobs.
        """
        eligible = [
            m
            for m in matches
            if m.final_score >= self.min_score and m.match_status != "FILTERED"
        ]
        eligible.sort(key=lambda m: m.final_score, reverse=True)

        if not jobs_map:
            return eligible[: self.max_jobs]

        deduped: List[MatchResult] = []
        seen_fingerprints = set()

        for match in eligible:
            job = jobs_map.get(match.job_id) if match.job_id else None
            if job and job.fingerprint:
                if job.fingerprint in seen_fingerprints:
                    continue
                seen_fingerprints.add(job.fingerprint)
            deduped.append(match)

        return deduped[: self.max_jobs]


    def format_job_card(
        self, match: MatchResult, job: Optional[Job] = None, index: int = 1, draft_id: Optional[int] = None
    ) -> str:
        """
        Formats a single MatchResult and Job into a standard mobile-friendly readable card.
        """
        title = match.title or (job.title if job else "Unknown Position")
        company = match.company or (job.company if job else "Not specified")
        location = match.location or (job.location if job else "Not specified")
        source = job.source if job else "Adzuna"
        apply_url = (job.url if job and job.url else "") or "N/A"

        matched_skills_str = (
            ", ".join(match.matched_skills) if match.matched_skills else "None"
        )
        missing_skills_str = (
            ", ".join(match.missing_skills) if match.missing_skills else "None"
        )

        skill_pct = int(round(match.skill_score * 100))

        lines = [
            f"{index}. {title}",
            f"Company: {company}",
            f"Location: {location}",
            "",
            f"Match Score: {match.final_score:.1f}/100",
            f"Semantic: {match.similarity_score:.2f}",
            f"Skill Match: {skill_pct}%",
            "",
            "Matched:",
            matched_skills_str,
            "",
            "Missing:",
            missing_skills_str,
            "",
            f"Experience: {match.experience_status}",
            f"Location: {match.location_status}",
            "",
            f"Source: {source}",
            f"Apply: {apply_url}",
        ]
        if draft_id is not None:
            lines.extend([
                "",
                f"Tailored resume draft #{draft_id} is ready for review.",
            ])

        return "\n".join(lines)


    def format_header(self, total_matches: int, date_str: Optional[str] = None) -> str:
        """
        Formats the daily digest header.
        """
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%d %B %Y")

        match_label = "match" if total_matches == 1 else "matches"
        return (
            "AI JOB DIGEST\n"
            f"{date_str}\n\n"
            f"{total_matches} strong {match_label} found.\n\n"
        )

    def build_digest_chunks(
        self,
        matches: List[MatchResult],
        jobs_map: Optional[Dict[int, Job]] = None,
        date_str: Optional[str] = None,
    ) -> List[DigestChunk]:
        """
        Processes matches, formats job cards, and splits them into message chunks
        while preserving job card boundaries and character limits.

        Returns:
            List[DigestChunk]: Formatted message chunks ready for Telegram dispatch.
        """
        if jobs_map is None:
            jobs_map = {}

        filtered = self.filter_and_sort_matches(matches, jobs_map=jobs_map)


        if not filtered:
            if not self.send_empty:
                return []
            header = self.format_header(0, date_str=date_str)
            text = header + "No strong matches meeting threshold were found today."
            return [DigestChunk(text=text, job_ids=[])]

        header = self.format_header(len(filtered), date_str=date_str)
        separator = "\n\n--------------------------------\n\n"

        chunks: List[DigestChunk] = []
        current_text = header
        current_job_ids: List[int] = []

        for idx, match in enumerate(filtered, start=1):
            job = jobs_map.get(match.job_id) if match.job_id else None
            draft_id = getattr(match, "draft_id", None)
            card = self.format_job_card(match, job=job, index=idx, draft_id=draft_id)

            # Check if this is the first job card in the current chunk
            # If current_text already has content beyond header, we add separator
            if current_job_ids:
                addition = separator + card
            else:
                addition = card

            if len(current_text) + len(addition) <= self.max_msg_len:
                current_text += addition
                if match.job_id is not None:
                    current_job_ids.append(match.job_id)
            else:
                # Flush existing chunk if it contains jobs
                if current_job_ids:
                    chunks.append(
                        DigestChunk(text=current_text, job_ids=current_job_ids)
                    )

                # Start new chunk with current card
                current_text = card
                current_job_ids = [match.job_id] if match.job_id is not None else []

        if current_job_ids:
            chunks.append(DigestChunk(text=current_text, job_ids=current_job_ids))

        return chunks
