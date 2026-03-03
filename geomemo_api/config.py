"""
Centralized configuration — all credentials loaded from environment variables.
No hardcoded secrets anywhere in the codebase.
"""
import os
from pathlib import Path

# --- Database ---
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "db"),
    "database": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# --- Beehiiv Newsletter ---
BEEHIIV_API_KEY = os.getenv("BEEHIIV_API_KEY", "")
BEEHIIV_PUB_ID = os.getenv("BEEHIIV_PUBLICATION_ID", "")

# --- Groq LLM ---
# Groq client reads GROQ_API_KEY from env automatically

# --- Directories ---
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploaded_images"
UPLOAD_DIR.mkdir(exist_ok=True)

# --- Article Categories ---
VALID_CATEGORIES = [
    'Geopolitical Conflict', 'Geopolitical Economics', 'Global Markets',
    'Geopolitical Politics', 'GeoNatDisaster', 'GeoLocal', 'Other'
]
VALID_CATEGORIES_SET = set(VALID_CATEGORIES)

# --- M2: Auto-Approval Scoring Weights ---
SCORING_WEIGHTS = {
    "confidence": 0.40,      # 40% from Groq confidence_score
    "credibility": 0.30,     # 30% from source credibility_score
    "novelty": 0.15,         # 15% from novelty (1 - max similarity to recent approved)
    "category_bonus": 0.15,  # 15% from category relevance bonus
}

# Category relevance bonuses (0-100 scale)
# Higher = more desirable for the platform's audience
CATEGORY_RELEVANCE_BONUS = {
    "Geopolitical Conflict": 95,
    "Geopolitical Economics": 90,
    "Global Markets": 85,
    "Geopolitical Politics": 80,
    "GeoNatDisaster": 60,
    "GeoLocal": 40,
    "Other": 10,
}

# Repetition detection threshold
REPETITION_THRESHOLD = 0.85

# Auto-approve/reject score thresholds (defaults, overridable via API)
AUTO_APPROVE_THRESHOLD = 80
AUTO_REJECT_THRESHOLD = 30

# Default source credibility for unknown sources
DEFAULT_SOURCE_CREDIBILITY = 50
