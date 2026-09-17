"""
Skill extraction and vocabulary canonicalization service.
Uses deterministic regex boundary matching without relying on LLMs.
"""

import re
from typing import Dict, List, Set, Tuple


# Skill vocabulary mapping canonical skill names to list of matching lower-case aliases/patterns.
SKILL_VOCABULARY: Dict[str, List[str]] = {
    "Python": ["python", "py"],
    "Java": ["java"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "sqlite", "tsql", "plsql"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "dl"],
    "TensorFlow": ["tensorflow", "tf"],
    "PyTorch": ["pytorch", "torch"],
    "Scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Computer Vision": ["computer vision", "cv", "opencv"],
    "NLP": ["nlp", "natural language processing"],
    "Transformers": ["transformers", "huggingface", "hugging face"],
    "LLM": ["llm", "large language model", "large language models"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    "Agentic AI": ["agentic ai", "ai agent", "ai agents", "agentic"],
    "FastAPI": ["fastapi"],
    "Flask": ["flask"],
    "Power BI": ["power bi", "powerbi"],
    "Docker": ["docker", "containerization"],
    "Git": ["git"],
    "GitHub": ["github"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure", "microsoft azure"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Statistics": ["statistics", "statistical analysis", "statistical modeling"],
    "Data Visualization": ["data visualization", "dataviz", "matplotlib", "seaborn"],
}


def build_compiled_skill_patterns() -> List[Tuple[str, re.Pattern]]:
    """
    Compiles regex patterns for each canonical skill to ensure boundary safety.
    Handles special characters in tech names (e.g. c++, scikit-learn).
    """
    patterns = []
    for canonical_name, aliases in SKILL_VOCABULARY.items():
        sorted_aliases = sorted(aliases, key=len, reverse=True)
        escaped_aliases = [re.escape(alias) for alias in sorted_aliases]
        # Regex pattern with word boundaries (using \b where appropriate)
        pattern_str = r"(?i)(?<!\w)(" + "|".join(escaped_aliases) + r")(?!\w)"
        compiled_regex = re.compile(pattern_str)
        patterns.append((canonical_name, compiled_regex))
    return patterns


COMPILED_SKILL_PATTERNS = build_compiled_skill_patterns()


def extract_skills(text: str) -> Set[str]:
    """
    Extracts canonical skills present in the text string.

    Args:
        text: Input text (resume body, job description, title, category).

    Returns:
        Set[str]: Set of canonical skill names matched in the text.
    """
    if not text:
        return set()

    found_skills: Set[str] = set()
    for canonical_name, pattern in COMPILED_SKILL_PATTERNS:
        if pattern.search(text):
            found_skills.add(canonical_name)

    return found_skills


def calculate_skill_overlap(
    resume_skills: Set[str], job_skills: Set[str]
) -> Tuple[Set[str], Set[str], float]:
    """
    Calculates skill overlap metrics between candidate resume skills and job required skills.

    Returns:
        Tuple[Set[str], Set[str], float]:
            - matched_skills: Skills present in both resume and job.
            - missing_skills: Skills required by job but missing from resume.
            - skill_overlap_score: Ratio (0.0 to 1.0) of matched_skills / job_skills.
    """
    if not job_skills:
        # If job specifies no recognizable skills, neutral default score 0.5
        return set(), set(), 0.5

    matched_skills = resume_skills.intersection(job_skills)
    missing_skills = job_skills - resume_skills

    score = len(matched_skills) / len(job_skills)
    return matched_skills, missing_skills, min(1.0, max(0.0, score))
