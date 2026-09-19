"""
System and user prompt templates for LLM resume tailoring.
Strictly enforces factual truth and source-of-truth policy.
"""

from typing import Any, Dict, Optional
from app.db.models import Job, MatchResult
from app.llm.schemas import ResumeProfile

SYSTEM_PROMPT = """You are an expert ATS resume editor and career advisor.
Your task is to tailor a candidate's master resume for a specific job description.

CRITICAL FACTUAL CONSTRAINTS — READ CAREFULLY:
1. The supplied Master Resume is the ONLY factual source of truth.
2. You must NEVER invent experience, skills, education, certifications, employment history, job titles, companies, or projects.
3. You must NEVER invent project results, numeric metrics, percentages, or years of experience.
4. You must NEVER claim any skill or technology that is NOT explicitly present in the Master Resume.
5. You may ONLY:
   - Emphasize existing relevant skills and experiences.
   - Reorder experience or bullet points to highlight relevant achievements first.
   - Align terminology with the job description ONLY when it accurately describes existing experience.
   - Improve wording, clarity, and conciseness while strictly preserving factual accuracy.
6. The candidate profile MUST remain 100% truthful to the source resume.

OUTPUT FORMAT:
Return a JSON object matching the requested schema with fields:
- summary: Tailored professional summary (preserving true facts).
- skills: Filtered/ordered list of relevant skills from the master resume.
- experience: Reordered and polished work experience items.
- projects: Reordered and polished project items.
- education: Preserved education details.
- certifications: Preserved certification list.
- changes: List of specific edits made (e.g., "Emphasized Python and PyTorch skills").
- warnings: List of any job requirements that the candidate lacks based on master resume.
"""


def build_user_prompt(
    profile: ResumeProfile,
    job: Job,
    match: Optional[MatchResult] = None,
) -> str:
    """
    Constructs the user prompt containing master resume, job content, match info,
    and tailoring instructions.
    """
    matched_skills = match.matched_skills if match else []
    missing_skills = match.missing_skills if match else []
    score = match.final_score if match else 0.0

    prompt = f"""### MASTER RESUME (SOURCE OF TRUTH)
Candidate Name: {profile.name}
Summary: {profile.summary}

Skills:
{", ".join(profile.skills)}

Experience:
{profile.experience}

Projects:
{profile.projects}

Education:
{profile.education}

Certifications:
{profile.certifications}

Achievements:
{profile.achievements}

---

### TARGET JOB DESCRIPTION
Job Title: {job.title}
Company: {job.company}
Location: {job.location}
Description:
{job.description}

---

### PHASE 2 MATCH INFORMATION
Match Score: {score:.1f}%
Matched Skills: {", ".join(matched_skills) if matched_skills else "None"}
Missing Skills: {", ".join(missing_skills) if missing_skills else "None"}

---

### INSTRUCTIONS
Please tailor the resume for this job following the strict factual rules above.
Output only structured JSON matching the TailoredResume schema.
"""
    return prompt
