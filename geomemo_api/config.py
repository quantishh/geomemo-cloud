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

# --- Admin Authentication (HTTP Basic Auth) ---
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# --- CORS Allowed Origins ---
# Comma-separated list of allowed origins. If empty, defaults to same-origin only.
_cors_raw = os.getenv("CORS_ORIGINS", "https://geomemo.news,http://localhost:3000,http://localhost:8000,http://3.147.70.170:3000")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()] if _cors_raw.strip() else []

# --- Directories ---
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploaded_images"
UPLOAD_DIR.mkdir(exist_ok=True)

# --- File Upload Limits ---
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}

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

# --- BrightData Proxy (for Google Search scraping) ---
BRIGHTDATA_PROXY_URL = os.getenv("BRIGHTDATA_PROXY_URL", "")

# --- Social Media: Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

# --- Social Media: Twitter/X (Phase 2) ---
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# --- Social Media: Drip Feed Settings ---
# Minimum scores for articles to be eligible for auto-posting
DRIP_MIN_APPROVAL_SCORE = float(os.getenv("DRIP_MIN_APPROVAL_SCORE", "85"))
DRIP_MIN_CONFIDENCE = float(os.getenv("DRIP_MIN_CONFIDENCE", "80"))

# How many articles to post per drip cycle (1 = one article every interval)
DRIP_ARTICLES_PER_CYCLE = int(os.getenv("DRIP_ARTICLES_PER_CYCLE", "1"))

# Interval between drip posts in minutes
DRIP_INTERVAL_MINUTES = int(os.getenv("DRIP_INTERVAL_MINUTES", "30"))

# Posting hours in Eastern Time (24h format). Bot only posts during this window.
DRIP_START_HOUR_ET = int(os.getenv("DRIP_START_HOUR_ET", "7"))   # 7 AM ET
DRIP_END_HOUR_ET = int(os.getenv("DRIP_END_HOUR_ET", "22"))      # 10 PM ET

# Only post articles scraped within the last N hours (default 24 = today's batch)
DRIP_LOOKBACK_HOURS = int(os.getenv("DRIP_LOOKBACK_HOURS", "24"))

# Auto-post newsletter digest to Telegram after generation
SOCIAL_AUTO_POST_NEWSLETTER = os.getenv("SOCIAL_AUTO_POST_NEWSLETTER", "true").lower() == "true"
