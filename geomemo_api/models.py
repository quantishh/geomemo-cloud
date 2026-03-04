"""
Pydantic models for request/response validation.
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# --- Article Models ---
class Article(BaseModel):
    id: int
    url: str
    headline_original: str | None = None
    headline: str | None = None
    summary: str | None = None
    category: str | None = None
    status: str
    publication_name: str | None = None
    author: str | None = None
    scraped_at: datetime | None = None
    distance: Optional[float] = None
    is_top_story: bool = False
    parent_id: Optional[int] = None
    confidence_score: Optional[int] = 0
    source_id: Optional[int] = None
    relevance_score: Optional[float] = 0
    repetition_score: Optional[float] = 0
    auto_approval_score: Optional[float] = 0
    country_codes: Optional[List[str]] = None
    region: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str


class BatchStatusUpdate(BaseModel):
    ids: List[int]
    status: str


class AutoApproveRequest(BaseModel):
    threshold: float = 80.0


class AutoRejectRequest(BaseModel):
    threshold: float = 30.0


class CategoryUpdate(BaseModel):
    category: str


class ManualArticleSubmission(BaseModel):
    headline: str
    url: str
    author: Optional[str] = None
    publication_name: Optional[str] = None
    content: str
    is_top_story: bool = False


class EnhanceRequest(BaseModel):
    summary: str
    publication_name: Optional[str] = None
    author: Optional[str] = None


# --- Cluster Models ---
class ClusterAnalysisRequest(BaseModel):
    original_article_id: int
    cluster_ids: List[int]
    make_top_story: bool = False


class ClusterAnalysisResponse(BaseModel):
    new_summary: str
    approved_id: int
    parent_id: int
    child_ids: List[int]
    is_top_story: bool


class SmartSimilarArticle(Article):
    """Article with AI-classified relationship to a target article."""
    relationship: str = "ADDS_DETAIL"  # ADDS_DETAIL, DIFFERENT_ANGLE, CONTRARIAN
    reason: str = ""                   # Brief explanation of what this article adds
    similarity: float = 0.0           # Cosine similarity score (0-1)


# --- Content Models ---
class TweetSubmission(BaseModel):
    url: str
    content: Optional[str] = None
    author: Optional[str] = None


class Tweet(BaseModel):
    id: int
    content: str
    url: Optional[str] = None
    image_url: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime


class Sponsor(BaseModel):
    id: int
    company_name: str
    headline: str
    summary: str
    link_url: str
    logo_url: str
    created_at: datetime


class Podcast(BaseModel):
    id: int
    show_name: str
    episode_title: str
    description: str
    link_url: str
    image_url: str
    created_at: datetime


# --- Newsletter Models ---
class NewsletterSignup(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: str
    title: str
    field: str


# --- M3: Newsletter Generation Models ---
class DailyBrief(BaseModel):
    id: int
    date: str
    summary_text: str
    summary_html: Optional[str] = None
    newsletter_html: Optional[str] = None
    subject_line: Optional[str] = None
    word_count: Optional[int] = None
    generated_at: Optional[datetime] = None
    published: bool = False
    beehiiv_post_id: Optional[str] = None


class NewsletterGenerateRequest(BaseModel):
    """Optional overrides for newsletter generation."""
    target_date: Optional[str] = None  # YYYY-MM-DD, defaults to today
    regenerate: bool = False  # If True, overwrites existing brief for this date


class NewsletterPublishResponse(BaseModel):
    message: str
    beehiiv_post_id: str
    brief_id: int


# --- Utility Models ---
class ScrapeRequest(BaseModel):
    url: str


# --- Source Models ---
class Source(BaseModel):
    id: int
    name: str
    domain: Optional[str] = None
    credibility_score: int = 50
    tier: int = 3
    country: Optional[str] = None
    language: str = 'en'
    total_articles: int = 0
    approved_count: int = 0
    rejected_count: int = 0


class SourceUpdate(BaseModel):
    credibility_score: Optional[int] = None
    tier: Optional[int] = None
    country: Optional[str] = None
    language: Optional[str] = None


class SourceCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    credibility_score: int = 50
    tier: int = 3
    country: Optional[str] = None
    language: str = 'en'
