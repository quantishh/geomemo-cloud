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
