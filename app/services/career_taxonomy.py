"""
Centralized AI Career Role Taxonomy and Role Alias Normalizer.
Provides canonical role family mapping, normalization rules, and AI career relevance checking.
"""

import re
from typing import Dict, List, Optional, Tuple

AI_ROLE_TAXONOMY: Dict[str, Dict[str, List[str]]] = {
    "Machine Learning": {
        "Machine Learning Engineer": [
            "machine learning engineer",
            "ml engineer",
            "ai ml engineer",
            "applied ml engineer",
            "junior ml engineer",
            "machine learning developer",
            "ml developer",
            "associate ml engineer",
        ],
        "Machine Learning Intern": [
            "machine learning intern",
            "ml intern",
            "machine learning trainee",
            "ml engineering intern",
        ],
        "AI Engineer": [
            "ai engineer",
            "artificial intelligence engineer",
            "applied ai engineer",
            "junior ai engineer",
            "ai developer",
            "ai engineer intern",
        ],
        "Deep Learning Engineer": [
            "deep learning engineer",
            "dl engineer",
            "deep learning researcher",
            "deep learning developer",
        ],
    },
    "Data Science": {
        "Data Scientist": [
            "data scientist",
            "junior data scientist",
            "applied data scientist",
            "associate data scientist",
            "data scientist engineer",
        ],
        "Data Science Intern": [
            "data science intern",
            "data scientist intern",
            "data science trainee",
        ],
        "Data Analyst": [
            "data analyst",
            "ai data analyst",
            "junior data analyst",
            "data analytics intern",
        ],
    },
    "Generative AI & LLMs": {
        "Generative AI Engineer": [
            "generative ai engineer",
            "generative ai developer",
            "generative ai architect",
            "gen ai engineer",
            "genai engineer",
            "gen ai developer",
        ],
        "LLM Engineer": [
            "llm engineer",
            "llm application engineer",
            "llm developer",
            "large language model engineer",
        ],
        "AI Agent Engineer": [
            "ai agent engineer",
            "ai agent architect",
            "agentic ai engineer",
            "agentic engineer",
            "ai agents developer",
        ],
        "AI Application Engineer": [
            "ai application engineer",
            "prompt engineer",
            "ai automation engineer",
            "ai integration engineer",
        ],
    },
    "Natural Language Processing": {
        "NLP Engineer": [
            "natural language processing engineer",
            "nlp engineer",
            "nlp scientist",
            "nlp developer",
            "conversational ai engineer",
            "speech ai engineer",
        ],
    },
    "Computer Vision": {
        "Computer Vision Engineer": [
            "computer vision engineer",
            "computer vision developer",
            "vision ai engineer",
            "image processing engineer",
            "cv engineer",
        ],
    },
    "AI Security": {
        "AI Security Engineer": [
            "ai security engineer",
            "ai security analyst",
            "ml security engineer",
            "ai safety engineer",
            "ai cybersecurity engineer",
        ],
    },
    "AI Data Engineering": {
        "AI Data Engineer": [
            "ai data engineer",
            "machine learning data engineer",
            "ml data engineer",
            "data engineer ai ml",
            "data pipeline engineer",
        ],
    },
    "MLOps & AI Infrastructure": {
        "MLOps Engineer": [
            "mlops engineer",
            "ml platform engineer",
            "machine learning platform engineer",
            "ai infrastructure engineer",
            "ai devops engineer",
            "cloud ml engineer",
            "devops engineer",
        ],
    },
    "AI Product & Solutions": {
        "AI Product Manager": [
            "ai product manager",
            "ai product analyst",
            "ai solutions engineer",
            "ai business analyst",
            "ai consultant",
        ],
    },
    "AI Support & Operations": {
        "AI Support Engineer": [
            "ai support analyst",
            "ai technical support engineer",
            "ai operations analyst",
            "ai implementation engineer",
            "ai solutions analyst",
        ],
    },
    "AI Data Annotation": {
        "AI Data Annotator": [
            "ai data labeler",
            "data annotation specialist",
            "ai annotation specialist",
            "machine learning data annotator",
            "ai training data specialist",
        ],
    },
}

# Broad AI/ML keyword patterns for general relevance checking
AI_RELEVANCE_PATTERNS: List[str] = [
    r"\b(machine\s+learning|ml)\b",
    r"\b(artificial\s+intelligence|ai)\b",
    r"\b(deep\s+learning|dl)\b",
    r"\b(data\s+scienc\w*|data\s+analys\w*|data\s+analyst)\b",
    r"\b(nlp|natural\s+language\s+processing)\b",
    r"\b(computer\s+vision|vision\s+ai|opencv)\b",
    r"\b(generative\s+ai|genai|llm|large\s+language\s+model|gpt|transformers?)\b",
    r"\b(agentic|ai\s+agent|langchain|llama\s*index|rag)\b",
    r"\b(mlops|model\s+deployment|model\s+monitoring|feature\s+store)\b",
    r"\b(pytorch|tensorflow|keras|scikit-learn|huggingface)\b",
    r"\b(data\s+annotation|data\s+labeler|data\s+labeling)\b",
]


def normalize_role_title(title: str) -> str:
    """
    Normalizes role titles by unifying case, punctuation, slashes, hyphens, and abbreviations.
    Example: 'AI/ML Engineer - Entry Level' -> 'ai ml engineer entry level'
    """
    if not title:
        return ""

    text = title.lower().strip()
    # Replace slashes, hyphens, underscores with spaces
    text = re.sub(r"[/\\_\-]", " ", text)
    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_ai_career_relevant(title: str, description: str = "") -> bool:
    """
    Determines whether a job listing is relevant to AI/ML/Data career taxonomy.
    """
    text = (title or "") + " " + (description or "")
    if not text.strip():
        return False

    text_lower = text.lower()
    for pattern in AI_RELEVANCE_PATTERNS:
        if re.search(pattern, text_lower):
            return True

    norm_t = normalize_role_title(title)
    if any(
        norm_t == normalize_role_title(alias)
        or re.search(r"\b" + re.escape(normalize_role_title(alias)) + r"\b", norm_t)
        for family in AI_ROLE_TAXONOMY.values()
        for aliases in family.values()
        for alias in aliases
    ):
        return True

    return False


def classify_role_family(title: str, description: str = "") -> Tuple[Optional[str], Optional[str], float]:
    """
    Classifies a job title and description into a canonical role family and role name.

    Returns:
        Tuple[Optional[str], Optional[str], float]: (role_family, canonical_role, role_score)
    """
    norm_title = normalize_role_title(title)
    norm_desc = normalize_role_title(description[:500]) if description else ""

    # Build flat list of (norm_alias, family_name, canonical_role) sorted by len(norm_alias) DESC
    alias_entries = []
    for family_name, roles in AI_ROLE_TAXONOMY.items():
        for canonical_role, aliases in roles.items():
            for alias in aliases:
                norm_alias = normalize_role_title(alias)
                alias_entries.append((norm_alias, family_name, canonical_role))

    alias_entries.sort(key=lambda x: len(x[0]), reverse=True)

    # First attempt exact / substring alias match on title (longest alias first)
    for norm_alias, family_name, canonical_role in alias_entries:
        if norm_alias == norm_title or re.search(r"\b" + re.escape(norm_alias) + r"\b", norm_title):
            return family_name, canonical_role, 1.0

    # Second attempt fuzzy alias match on description
    for norm_alias, family_name, canonical_role in alias_entries:
        if norm_desc and re.search(r"\b" + re.escape(norm_alias) + r"\b", norm_desc):
            return family_name, canonical_role, 0.75

    # Check for general AI relevance if no specific taxonomy match
    if is_ai_career_relevant(title, description):
        return "General AI/ML", "AI/ML Role", 0.50

    return None, None, 0.0
