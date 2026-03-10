"""
Article endpoints: listing, approval, enhancement, clustering, similarity search.
M2: Added filtering/sorting, auto-approve/reject, duplicate detection.
"""
import json
import logging
import numpy as np
from typing import List, Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from psycopg2.extras import execute_values
from groq import Groq
from sentence_transformers import SentenceTransformer

from database import get_db_connection
from config import VALID_CATEGORIES_SET
from models import (
    Article, StatusUpdate, BatchStatusUpdate, CategoryUpdate,
    ManualArticleSubmission, EnhanceRequest,
    ClusterAnalysisRequest, ClusterAnalysisResponse,
    AutoApproveRequest, AutoRejectRequest,
    SmartSimilarArticle,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Models are loaded once at module level (shared with main app)
embedding_model: SentenceTransformer = None
groq_client: Groq = None


def init_models(embed_model: SentenceTransformer, groq: Groq):
    """Called from main.py to inject shared model instances."""
    global embedding_model, groq_client
    embedding_model = embed_model
    groq_client = groq


def call_groq(headline: str, content: str) -> dict:
    system_prompt = f"""
You are a top-tier geopolitical analyst for 'GeoMemo'.
The user is manually submitting an article. Categorize it and return a valid JSON object:
{{"headline_en": "...", "summary": "...", "category": "..."}}
"""
    user_prompt = f'Headline: "{headline}"\nContent Snippet: "{content}"'
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        processed_data = json.loads(chat_completion.choices[0].message.content)
        processed_data['headline_en'] = processed_data.get('headline_en', headline)
        processed_data['summary'] = processed_data.get('summary', 'No summary provided.')
        processed_data['category'] = processed_data.get('category', 'Other')
        if processed_data['category'] not in VALID_CATEGORIES_SET:
            processed_data['category'] = 'Other'
        return processed_data
    except Exception as e:
        logger.error(f"Groq call failed: {e}")
        raise HTTPException(status_code=500, detail=f"Groq error: {e}")


# --- Article Columns (shared across queries) ---
ARTICLE_COLUMNS = """
    id, url, headline AS headline_original, headline_en AS headline,
    summary, category, status, publication_name, author, scraped_at,
    is_top_story, confidence_score, parent_id,
    source_id, relevance_score, repetition_score, auto_approval_score,
    country_codes, region, og_image, embedded_tweets, website_tweets
"""


def _group_by_topic(articles: list, threshold: float = 0.70) -> list:
    """
    Greedy topic grouping: assign each article to an existing group if cosine
    similarity >= threshold, otherwise create a new group.  Returns a flat list
    with `topic_group` (int) and `topic_group_size` (int) fields added.
    Groups are sorted by the highest score in each group (DESC).
    Within a group, articles are sorted by auto_approval_score DESC.
    """
    if not articles:
        return []

    # Build embedding matrix (skip articles without embeddings)
    groups = []          # list of lists of article indices
    group_centroids = [] # representative embedding for each group

    for art in articles:
        emb = art.get('embedding')
        if emb is None:
            # No embedding — put in its own singleton group
            groups.append([art])
            group_centroids.append(None)
            continue

        emb_arr = np.array(emb, dtype=np.float32)
        norm = np.linalg.norm(emb_arr)
        if norm > 0:
            emb_arr = emb_arr / norm

        best_group = -1
        best_sim = threshold

        for gi, centroid in enumerate(group_centroids):
            if centroid is None:
                continue
            sim = float(np.dot(emb_arr, centroid))
            if sim >= best_sim:
                best_sim = sim
                best_group = gi

        if best_group >= 0:
            groups[best_group].append(art)
            # Update centroid as running average
            n = len(groups[best_group])
            group_centroids[best_group] = (
                group_centroids[best_group] * (n - 1) + emb_arr
            ) / n
            c_norm = np.linalg.norm(group_centroids[best_group])
            if c_norm > 0:
                group_centroids[best_group] = group_centroids[best_group] / c_norm
        else:
            groups.append([art])
            group_centroids.append(emb_arr)

    # Sort groups by highest auto_approval_score in each group
    def group_max_score(group):
        return max((a.get('auto_approval_score') or 0) for a in group)

    groups.sort(key=group_max_score, reverse=True)

    # Flatten with topic_group and topic_group_size fields
    result = []
    for gi, group in enumerate(groups):
        # Sort within group by score descending
        group.sort(key=lambda a: (a.get('auto_approval_score') or 0), reverse=True)
        for art in group:
            art.pop('embedding', None)  # Don't send embeddings to frontend
            art['topic_group'] = gi
            art['topic_group_size'] = len(group)
            result.append(art)

    return result


# --- Article Listing (M2: with filtering/sorting) ---

@router.get("/articles")
def get_articles(
    sort_by: str = "scraped_at",
    order: str = "desc",
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    days: int = 7,
    limit: Optional[int] = None,
    offset: int = 0,
    target_date: Optional[str] = None,
):
    """
    List articles with optional filtering, sorting, and pagination.
    Backwards compatible: no limit param = returns flat list (web version).
    With limit param = returns {articles, total, limit, offset} (mobile version).
    With target_date = filters to specific date (YYYY-MM-DD format).
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # Whitelist allowed sort columns to prevent SQL injection
        ALLOWED_SORT_COLS = {
            "scraped_at", "auto_approval_score", "confidence_score",
            "repetition_score", "publication_name", "topic_group",
        }
        is_topic_grouped = (sort_by == "topic_group")
        if sort_by not in ALLOWED_SORT_COLS:
            sort_by = "scraped_at"
        if order.lower() not in ("asc", "desc"):
            order = "desc"

        params = []

        # Date filtering: specific date OR rolling window
        if target_date:
            where_clauses = ["scraped_at::date = %s"]
            params.append(target_date)
        else:
            where_clauses = [f"scraped_at >= NOW() - INTERVAL '{int(days)} days'"]

        if min_score is not None:
            where_clauses.append("auto_approval_score >= %s")
            params.append(min_score)
        if max_score is not None:
            where_clauses.append("auto_approval_score <= %s")
            params.append(max_score)
        if category:
            where_clauses.append("category = %s")
            params.append(category)
        if status:
            where_clauses.append("status = %s")
            params.append(status)

        where_sql = " AND ".join(where_clauses)

        # Pagination support
        if limit is not None:
            safe_limit = max(1, min(int(limit), 500))
            safe_offset = max(0, int(offset))

            # Get total count for pagination metadata
            count_query = f"SELECT COUNT(*) FROM articles WHERE {where_sql}"
            cursor.execute(count_query, tuple(params))
            total_count = cursor.fetchone()[0]

            query = f"""
                SELECT {ARTICLE_COLUMNS}
                FROM articles
                WHERE {where_sql}
                ORDER BY {sort_by} {order}
                LIMIT {safe_limit} OFFSET {safe_offset}
            """
            cursor.execute(query, tuple(params))
            articles = [dict(row) for row in cursor.fetchall()]

            return {
                "articles": articles,
                "total": total_count,
                "limit": safe_limit,
                "offset": safe_offset,
            }
        else:
            if is_topic_grouped:
                # Topic-grouped view: fetch articles with embeddings, cluster by similarity
                query = f"""
                    SELECT {ARTICLE_COLUMNS}, embedding
                    FROM articles
                    WHERE {where_sql}
                    ORDER BY auto_approval_score DESC NULLS LAST, scraped_at DESC
                """
                cursor.execute(query, tuple(params))
                articles = [dict(row) for row in cursor.fetchall()]
                return _group_by_topic(articles)
            else:
                # Original behavior: return flat list (backward compatible)
                query = f"""
                    SELECT {ARTICLE_COLUMNS}
                    FROM articles
                    WHERE {where_sql}
                    ORDER BY {sort_by} {order}
                """
                cursor.execute(query, tuple(params))
                return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.get("/articles/archive", response_model=List[Article])
def get_archived_articles():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(f"""
            SELECT {ARTICLE_COLUMNS}
            FROM articles
            WHERE scraped_at < NOW() - INTERVAL '7 days'
            ORDER BY scraped_at DESC
            LIMIT 500
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Archive fetch error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.get("/articles/website-feed")
def get_website_feed():
    """
    Live website feed — disconnected from the newsletter.
    Returns structured JSON with three sections:
    - top_stories: is_top_story=true from last published newsletter + score>=90 from 24h
    - main_stories: score 75+ from 48h, topic-deduplicated, with related_sources
    - more_news: score 65-74 from 48h, max 14 items
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # 1. Find last published newsletter date
        cursor.execute("""
            SELECT date FROM daily_briefs
            WHERE published = TRUE OR newsletter_html IS NOT NULL
            ORDER BY date DESC LIMIT 1
        """)
        last_newsletter_row = cursor.fetchone()
        last_newsletter_date = str(last_newsletter_row['date']) if last_newsletter_row else None

        # 2. TOP STORIES: is_top_story=true from last 72h + high scorers (>=90) from 72h
        top_stories = []

        # 2a. All top-story-marked articles from last 72 hours (immediate reflection)
        cursor.execute(f"""
            SELECT {ARTICLE_COLUMNS}
            FROM articles
            WHERE status = 'approved'
              AND is_top_story = TRUE
              AND scraped_at >= NOW() - INTERVAL '72 hours'
            ORDER BY scraped_at DESC
        """)
        top_stories = [dict(row) for row in cursor.fetchall()]

        # 2b. Also include any score>=90 from last 24h that aren't already top stories
        top_story_ids = {a['id'] for a in top_stories}
        cursor.execute(f"""
            SELECT {ARTICLE_COLUMNS}
            FROM articles
            WHERE status = 'approved'
              AND auto_approval_score >= 90
              AND scraped_at >= NOW() - INTERVAL '72 hours'
            ORDER BY auto_approval_score DESC, scraped_at DESC
            LIMIT 5
        """)
        for row in cursor.fetchall():
            art = dict(row)
            if art['id'] not in top_story_ids:
                top_stories.append(art)
                top_story_ids.add(art['id'])

        # 3. MAIN STORIES: score 70+ from 72h, topic-deduplicated
        cursor.execute(f"""
            SELECT {ARTICLE_COLUMNS}, embedding
            FROM articles
            WHERE status = 'approved'
              AND auto_approval_score >= 70
              AND scraped_at >= NOW() - INTERVAL '72 hours'
            ORDER BY auto_approval_score DESC, scraped_at DESC
        """)
        main_candidates = [dict(row) for row in cursor.fetchall()]

        # Exclude articles already in top_stories
        main_candidates = [a for a in main_candidates if a['id'] not in top_story_ids]

        # Topic-deduplicate using existing _group_by_topic
        grouped = _group_by_topic(main_candidates, threshold=0.70)

        # Build main_stories: pick highest scorer per group, collect related_sources
        main_stories = []
        seen_groups = {}
        for art in grouped:
            gid = art.get('topic_group', -1)
            if gid not in seen_groups:
                # This is the top article in the group
                art['related_sources'] = []
                seen_groups[gid] = art
                main_stories.append(art)
            else:
                # This is a related article — add as a related source with summary for hover
                parent_art = seen_groups[gid]
                parent_art['related_sources'].append({
                    'publication_name': art.get('publication_name') or 'Unknown',
                    'url': art.get('url', ''),
                    'summary': art.get('summary', ''),
                    'author': art.get('author', ''),
                })

        # Limit to top 20 topic groups for the homepage
        main_stories = main_stories[:20]

        # Clean up topic_group fields from output
        for art in main_stories:
            art.pop('topic_group', None)
            art.pop('topic_group_size', None)

        # 4. MORE NEWS: score 60-69 from 72h, max 20 items
        main_story_ids = {a['id'] for a in main_stories}
        all_used_ids = top_story_ids | main_story_ids
        cursor.execute(f"""
            SELECT {ARTICLE_COLUMNS}
            FROM articles
            WHERE status = 'approved'
              AND auto_approval_score >= 60
              AND auto_approval_score < 70
              AND scraped_at >= NOW() - INTERVAL '72 hours'
            ORDER BY auto_approval_score DESC, scraped_at DESC
            LIMIT 30
        """)
        more_news_candidates = [dict(row) for row in cursor.fetchall()]
        more_news = [a for a in more_news_candidates if a['id'] not in all_used_ids][:20]

        # 5. Attach cached X posts for all sections
        all_feed_articles = top_stories + main_stories + more_news
        _attach_matched_tweets(cursor, all_feed_articles)

        # Clean up raw website_tweets from response (matched_tweets is the formatted version)
        for art in all_feed_articles:
            art.pop('website_tweets', None)
            art.pop('website_tweets_fetched_at', None)

        return {
            "top_stories": top_stories,
            "main_stories": main_stories,
            "more_news": more_news,
            "last_newsletter_date": last_newsletter_date,
        }

    except Exception as e:
        logger.error(f"Website feed error: {e}")
        raise HTTPException(500, f"Feed error: {e}")
    finally:
        cursor.close()
        conn.close()


def _attach_matched_tweets(cursor, articles: list):
    """
    Attach cached website_tweets to articles for the website feed.
    Reads pre-fetched tweets from the website_tweets JSONB column.
    Falls back to empty list if no cached tweets exist.
    """
    if not articles:
        return

    for art in articles:
        cached = art.get('website_tweets')
        if cached and isinstance(cached, list) and len(cached) > 0:
            # Use cached website tweets — format for frontend
            art['matched_tweets'] = [
                {
                    'username': t.get('username', ''),
                    'text': t.get('text', ''),
                    'url': t.get('url', ''),
                }
                for t in cached[:10]
            ]
        else:
            art['matched_tweets'] = []


@router.get("/articles/approved", response_model=List[Article])
def get_approved_articles():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(f"""
            SELECT {ARTICLE_COLUMNS}
            FROM articles
            WHERE status = 'approved'
              AND (scraped_at AT TIME ZONE 'America/New_York')::date
                  = (NOW() AT TIME ZONE 'America/New_York')::date
            ORDER BY is_top_story DESC, scraped_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Fetch approved error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.get("/articles/newest-updates", response_model=List[Article])
def get_newest_updates():
    """
    Auto-populated feed of high-scoring articles from the most recent cron run.
    Returns articles with auto_approval_score >= 75, sorted by score DESC.
    Limited to 20 items.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(f"""
            SELECT {ARTICLE_COLUMNS}
            FROM articles
            WHERE auto_approval_score >= 75
              AND scraped_at >= NOW() - INTERVAL '6 hours'
            ORDER BY auto_approval_score DESC, scraped_at DESC
            LIMIT 20
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Fetch newest updates error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


# --- M5: Map Layer Endpoint (all scraped articles for WorldMonitor fork) ---

# Capital city coordinates for country code → lat/lon mapping
COUNTRY_COORDS = {
    "US": [-77.04, 38.90], "GB": [-0.12, 51.51], "FR": [2.35, 48.86], "DE": [13.38, 52.52],
    "CN": [116.40, 39.90], "RU": [37.62, 55.76], "JP": [139.69, 35.69], "IN": [77.21, 28.61],
    "BR": [-47.88, -15.79], "AU": [149.13, -35.28], "CA": [-75.70, 45.42], "KR": [126.98, 37.57],
    "MX": [-99.13, 19.43], "ID": [106.85, -6.21], "TR": [32.87, 39.93], "SA": [46.72, 24.69],
    "ZA": [28.19, -25.75], "AR": [-58.38, -34.60], "EG": [31.24, 30.04], "NG": [7.49, 9.06],
    "PK": [73.05, 33.69], "IL": [35.22, 31.77], "IR": [51.39, 35.69], "IQ": [44.37, 33.31],
    "UA": [30.52, 50.45], "PL": [21.01, 52.23], "IT": [12.50, 41.90], "ES": [-3.70, 40.42],
    "NL": [4.90, 52.37], "BE": [4.35, 50.85], "SE": [18.07, 59.33], "NO": [10.75, 59.91],
    "FI": [24.94, 60.17], "DK": [12.57, 55.68], "CH": [7.45, 46.95], "AT": [16.37, 48.21],
    "PT": [-9.14, 38.74], "GR": [23.73, 37.97], "CZ": [14.42, 50.08], "RO": [26.10, 44.43],
    "HU": [19.04, 47.50], "TH": [100.50, 13.76], "VN": [105.83, 21.03], "PH": [120.98, 14.60],
    "MY": [101.69, 3.14], "SG": [103.82, 1.35], "TW": [121.57, 25.03], "HK": [114.17, 22.32],
    "NZ": [174.78, -41.29], "CL": [-70.65, -33.45], "CO": [-74.08, 4.71], "PE": [-77.04, -12.05],
    "VE": [-66.92, 10.49], "CU": [-82.38, 23.11], "KE": [36.82, -1.29], "ET": [38.75, 9.02],
    "GH": [-0.19, 5.56], "TZ": [39.27, -6.81], "MA": [-6.84, 34.02], "DZ": [3.06, 36.75],
    "TN": [10.17, 36.81], "LY": [13.18, 32.90], "SD": [32.53, 15.59], "AE": [54.37, 24.45],
    "QA": [51.53, 25.29], "KW": [47.98, 29.37], "OM": [58.39, 23.61], "BH": [50.58, 26.23],
    "JO": [35.95, 31.95], "LB": [35.50, 33.89], "SY": [36.29, 33.51], "YE": [44.21, 15.35],
    "AF": [69.17, 34.53], "MM": [96.17, 16.87], "KP": [125.75, 39.02], "BD": [90.39, 23.81],
    "LK": [79.86, 6.93], "NP": [85.32, 27.72], "KH": [104.92, 11.55], "LA": [102.63, 17.97],
    "PS": [35.23, 31.90], "GE": [44.78, 41.72], "AM": [44.51, 40.18], "AZ": [49.87, 40.41],
    "KZ": [71.43, 51.13], "UZ": [69.28, 41.31], "RS": [20.47, 44.80], "HR": [15.98, 45.81],
    "BA": [18.41, 43.86], "XK": [21.17, 42.67], "ME": [19.26, 42.44], "MK": [21.43, 42.00],
    "BG": [23.32, 42.70], "SK": [17.11, 48.15], "SI": [14.51, 46.06], "LT": [25.28, 54.69],
    "LV": [24.11, 56.95], "EE": [24.75, 59.44], "IE": [-6.26, 53.35], "IS": [-21.90, 64.14],
    "CY": [33.38, 35.17], "MT": [14.51, 35.90], "LU": [6.13, 49.61],
}


@router.get("/api/articles/map")
def get_map_articles(days: int = Query(7, ge=1, le=30)):
    """
    Return all scraped articles with country data for the map layer.
    No curation filter — ALL articles regardless of status.
    Returns GeoJSON FeatureCollection.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id, url, headline_en, summary, summary_long, category,
                   publication_name, scraped_at, confidence_score, country_codes
            FROM articles
            WHERE scraped_at >= NOW() - %s::int * INTERVAL '1 day'
              AND country_codes IS NOT NULL
              AND array_length(country_codes, 1) > 0
            ORDER BY scraped_at DESC
            LIMIT 500
        """, (days,))

        features = []
        for row in cursor.fetchall():
            article = dict(row)
            # Use summary_long if available, fall back to summary
            display_summary = article.get('summary_long') or article.get('summary') or ''

            # Create one feature per country code
            for code in (article.get('country_codes') or []):
                code_upper = code.upper().strip()
                coords = COUNTRY_COORDS.get(code_upper)
                if not coords:
                    continue

                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": coords  # [lon, lat]
                    },
                    "properties": {
                        "id": article['id'],
                        "headline": article.get('headline_en') or '',
                        "summary": display_summary,
                        "category": article.get('category') or 'Other',
                        "source": article.get('publication_name') or '',
                        "url": article.get('url') or '',
                        "timestamp": article['scraped_at'].isoformat() if article.get('scraped_at') else '',
                        "confidence": article.get('confidence_score') or 0,
                        "country": code_upper,
                    }
                })

        return {
            "type": "FeatureCollection",
            "features": features
        }

    except Exception as e:
        logger.error(f"Map articles error: {e}")
        raise HTTPException(500, "Failed to fetch map articles")
    finally:
        cursor.close()
        conn.close()


@router.get("/api/articles/regional-feed")
def get_regional_feed(hours: int = Query(24, ge=1, le=72)):
    """
    Flat JSON array of recent articles for WorldMonitor regional panels.
    Returns ALL articles (with or without country_codes) from the last N hours,
    sorted newest-first.  Unlike /map, this is not GeoJSON — just a plain list.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id, url, headline_en, summary, category,
                   publication_name, scraped_at, confidence_score, country_codes
            FROM articles
            WHERE scraped_at >= NOW() - %s * INTERVAL '1 hour'
            ORDER BY scraped_at DESC
            LIMIT 500
        """, (hours,))

        articles = []
        for row in cursor.fetchall():
            article = dict(row)
            articles.append({
                "id": article["id"],
                "headline": article.get("headline_en") or "",
                "summary": article.get("summary") or "",
                "category": article.get("category") or "Other",
                "source": article.get("publication_name") or "",
                "url": article.get("url") or "",
                "scraped_at": article["scraped_at"].isoformat() if article.get("scraped_at") else "",
                "confidence": article.get("confidence_score") or 0,
                "country_codes": [c.upper().strip() for c in (article.get("country_codes") or [])],
            })

        return articles

    except Exception as e:
        logger.error(f"Regional feed error: {e}")
        raise HTTPException(500, "Failed to fetch regional feed")
    finally:
        cursor.close()
        conn.close()


# --- Article Actions ---

@router.post("/articles/manual-submission", status_code=201)
def manual_article_submission(article: ManualArticleSubmission):
    try:
        processed = call_groq(article.headline, article.content)
        text_to_embed = f"Headline: {article.headline}\nSummary: {article.content}"
        embed = embedding_model.encode(text_to_embed).tolist()
        conn = get_db_connection()
        cursor = conn.cursor()
        pub_name = article.publication_name if article.publication_name and article.publication_name.strip() else "Manual"
        auth_name = article.author if article.author and article.author.strip() else None
        cursor.execute(
            """INSERT INTO articles (url, headline, publication_name, author, headline_en, summary, category, status, scraped_at, embedding, is_top_story)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW(), %s, %s) RETURNING id""",
            (article.url, article.headline, pub_name, auth_name,
             processed['headline_en'], processed['summary'], processed['category'],
             embed, article.is_top_story),
        )
        nid = cursor.fetchone()[0]
        conn.commit()
        return {"message": "Saved", "article_id": nid}
    except Exception as e:
        logger.error(f"Manual error: {e}")
        raise HTTPException(500, f"Error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()


@router.post("/articles/{article_id}/enhance")
def enhance_article_summary(article_id: int, request: EnhanceRequest):
    text_input = request.summary
    if not text_input:
        raise HTTPException(400, "No text provided")
    try:
        # Use differentiated prompt for child articles (when parent context is provided)
        if request.parent_summary:
            system_msg = (
                "You are a senior geopolitical analyst. A parent article already covers this story "
                "with this summary:\n\n"
                f'"{request.parent_summary}"\n\n'
                "Rewrite the article below as a 50-word MAX summary highlighting what is NEW or DIFFERENT "
                "from the parent — a unique angle, new facts, or contrarian view. Do NOT repeat the parent. "
                "Professional analytical tone. Include specific names/figures/countries. English only."
            )
        else:
            system_msg = (
                "Rewrite this as a professional 50-word MAX news summary for investment bankers and policymakers. "
                "Lead with the core development and why it matters. Authoritative analytical tone. "
                "Include specific names/figures/countries. Use facts from the provided content. "
                "English only. Do NOT exceed 50 words."
            )
        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": text_input},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
        )
        new_summary = chat.choices[0].message.content.strip()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch headline_en so embedding matches scraper format: "Headline: ... Summary: ..."
        cursor.execute("SELECT headline_en, headline FROM articles WHERE id = %s", (article_id,))
        row = cursor.fetchone()
        headline_en = (row[0] or row[1] or '') if row else ''
        text_to_embed = f"Headline: {headline_en}\nSummary: {new_summary}"
        embedding = embedding_model.encode(text_to_embed).tolist()

        sql = "UPDATE articles SET summary = %s, embedding = %s, status = 'pending'"
        params = [new_summary, embedding]
        if request.publication_name and request.publication_name.strip():
            sql += ", publication_name = %s"
            params.append(request.publication_name)
        if request.author and request.author.strip():
            sql += ", author = %s"
            params.append(request.author)
        sql += " WHERE id = %s"
        params.append(article_id)
        cursor.execute(sql, tuple(params))
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Enhanced", "new_summary": new_summary}
    except Exception as e:
        logger.error(f"Enhance error: {e}")
        raise HTTPException(500, f"Error: {e}")


@router.post("/articles/{article_id}/status")
def update_article_status(article_id: int, status_update: StatusUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE articles SET status = %s WHERE id = %s", (status_update.status, article_id))

        # Milestone E: Update source credibility on approve/reject
        if status_update.status in ('approved', 'rejected'):
            try:
                cursor.execute("SELECT source_id FROM articles WHERE id = %s", (article_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    source_id = row[0]
                    cursor.execute("""
                        UPDATE sources SET credibility_score = (
                            SELECT CASE
                                WHEN (approved + rejected) > 0
                                THEN ROUND((approved::numeric / (approved + rejected)) * 100, 1)
                                ELSE 50
                            END
                            FROM (
                                SELECT
                                    COUNT(*) FILTER (WHERE status = 'approved') AS approved,
                                    COUNT(*) FILTER (WHERE status = 'rejected') AS rejected
                                FROM articles WHERE source_id = %s
                            ) counts
                        )
                        WHERE id = %s
                    """, (source_id, source_id))
            except Exception as cred_err:
                logger.warning(f"Credibility update failed for source: {cred_err}")

        conn.commit()
        return {"message": "Updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/articles/{article_id}/category")
def update_article_category(article_id: int, category_update: CategoryUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE articles SET category = %s WHERE id = %s", (category_update.category, article_id))
        conn.commit()
        return {"message": "Updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/articles/{article_id}/toggle-top")
def toggle_top_story(article_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE articles SET is_top_story = NOT is_top_story WHERE id = %s RETURNING is_top_story", (article_id,))
        conn.commit()
        new_state = cursor.fetchone()[0]
        return {"message": "Updated", "is_top_story": new_state}
    except Exception as e:
        conn.rollback()
        logger.error(f"Toggle top error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/articles/batch-update")
def batch_update_article_status(update_data: BatchStatusUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        execute_values(
            cursor,
            "UPDATE articles SET status = data.status FROM (VALUES %s) AS data(status, id) WHERE articles.id = data.id",
            [(update_data.status, aid) for aid in update_data.ids],
        )

        # Milestone E: Batch credibility update for affected sources
        if update_data.status in ('approved', 'rejected'):
            try:
                placeholders = ','.join(['%s'] * len(update_data.ids))
                cursor.execute(f"""
                    UPDATE sources SET credibility_score = sub.new_score
                    FROM (
                        SELECT s.id, ROUND(
                            COUNT(*) FILTER (WHERE a.status = 'approved')::numeric /
                            NULLIF(COUNT(*) FILTER (WHERE a.status IN ('approved', 'rejected')), 0) * 100, 1
                        ) AS new_score
                        FROM sources s
                        JOIN articles a ON a.source_id = s.id
                        WHERE s.id IN (SELECT DISTINCT source_id FROM articles WHERE id IN ({placeholders}) AND source_id IS NOT NULL)
                        GROUP BY s.id
                    ) sub
                    WHERE sources.id = sub.id AND sub.new_score IS NOT NULL
                """, tuple(update_data.ids))
            except Exception as cred_err:
                logger.warning(f"Batch credibility update failed: {cred_err}")

        conn.commit()
        return {"message": "Batch updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


# --- M2: Auto-Approve / Auto-Reject ---

@router.post("/articles/auto-approve")
def auto_approve_articles(request: AutoApproveRequest = AutoApproveRequest()):
    """Approve all pending articles with auto_approval_score >= threshold."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE articles SET status = 'approved'
               WHERE status = 'pending' AND auto_approval_score >= %s
               RETURNING id""",
            (request.threshold,)
        )
        approved_ids = [row[0] for row in cursor.fetchall()]
        conn.commit()
        return {
            "message": f"Auto-approved {len(approved_ids)} articles",
            "count": len(approved_ids),
            "ids": approved_ids,
            "threshold": request.threshold,
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.post("/articles/auto-reject")
def auto_reject_articles(request: AutoRejectRequest = AutoRejectRequest()):
    """Reject all pending articles with auto_approval_score <= threshold."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE articles SET status = 'rejected'
               WHERE status = 'pending' AND auto_approval_score <= %s
               RETURNING id""",
            (request.threshold,)
        )
        rejected_ids = [row[0] for row in cursor.fetchall()]
        conn.commit()
        return {
            "message": f"Auto-rejected {len(rejected_ids)} articles",
            "count": len(rejected_ids),
            "ids": rejected_ids,
            "threshold": request.threshold,
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


# --- Similarity, Duplicates & Clustering ---

@router.get("/articles/{article_id}/similar", response_model=List[Article])
def get_similar_articles(article_id: int, days: int = 2, threshold: float = 0.65):
    """
    Find similar articles within a time window.
    M2 upgrade: 48h window (not just same day), similarity threshold,
    excludes same-source dupes and already-clustered articles.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(
            "SELECT embedding, scraped_at, publication_name FROM articles WHERE id = %s",
            (article_id,),
        )
        target = cursor.fetchone()
        if not target:
            raise HTTPException(404, "Not found")
        if target['embedding'] is None:
            raise HTTPException(400, "Article has no embedding")

        cursor.execute(
            f"""SELECT {ARTICLE_COLUMNS},
            1 - (embedding <=> %s) AS similarity
            FROM articles
            WHERE id != %s
              AND embedding IS NOT NULL
              AND scraped_at >= %s::timestamp - INTERVAL '{int(days)} days'
              AND parent_id IS NULL
              AND (publication_name IS NULL OR publication_name != %s)
              AND 1 - (embedding <=> %s) >= %s
            ORDER BY similarity DESC
            LIMIT 10""",
            (
                target['embedding'], article_id,
                target['scraped_at'],
                target['publication_name'] or '',
                target['embedding'], threshold,
            ),
        )
        results = [dict(row) for row in cursor.fetchall()]
        # Map similarity to distance field for backward compatibility
        for r in results:
            r['distance'] = r.pop('similarity', None)
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sim error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.get("/articles/{article_id}/duplicates", response_model=List[Article])
def get_duplicate_articles(article_id: int, threshold: float = 0.85):
    """Find near-duplicate articles (cosine similarity >= threshold)."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT embedding FROM articles WHERE id = %s", (article_id,))
        target = cursor.fetchone()
        if not target or not target['embedding']:
            raise HTTPException(404, "Article not found or has no embedding")

        cursor.execute(
            f"""SELECT {ARTICLE_COLUMNS},
            1 - (embedding <=> %s) AS distance
            FROM articles
            WHERE id != %s AND embedding IS NOT NULL
            AND 1 - (embedding <=> %s) >= %s
            ORDER BY distance DESC
            LIMIT 20""",
            (target['embedding'], article_id, target['embedding'], threshold)
        )
        return [dict(row) for row in cursor.fetchall()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Duplicates error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/articles/{article_id}/smart-similar", response_model=List[SmartSimilarArticle])
def get_smart_similar_articles(article_id: int, days: int = 2, threshold: float = 0.65):
    """
    Find similar articles and use Groq to classify each article's relationship
    to the original: ADDS_DETAIL, DIFFERENT_ANGLE, CONTRARIAN, DUPLICATE, or RELATED.
    Returns only articles that add editorial value (filters out DUPLICATE and RELATED).
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # 1. Get original article
        cursor.execute(
            "SELECT embedding, scraped_at, publication_name, headline_en, summary FROM articles WHERE id = %s",
            (article_id,),
        )
        target = cursor.fetchone()
        if not target:
            raise HTTPException(404, "Not found")
        if target['embedding'] is None:
            raise HTTPException(400, "Article has no embedding")

        # 2. Find similar articles (same logic as GET /similar)
        cursor.execute(
            f"""SELECT {ARTICLE_COLUMNS},
            1 - (embedding <=> %s) AS similarity
            FROM articles
            WHERE id != %s
              AND embedding IS NOT NULL
              AND scraped_at >= %s::timestamp - INTERVAL '{int(days)} days'
              AND parent_id IS NULL
              AND (publication_name IS NULL OR publication_name != %s)
              AND 1 - (embedding <=> %s) >= %s
            ORDER BY similarity DESC
            LIMIT 10""",
            (
                target['embedding'], article_id,
                target['scraped_at'],
                target['publication_name'] or '',
                target['embedding'], threshold,
            ),
        )
        similar_rows = [dict(row) for row in cursor.fetchall()]

        if not similar_rows:
            return []

        # 3. Build Groq prompt to classify relationships
        candidates_txt = ""
        for i, row in enumerate(similar_rows):
            candidates_txt += (
                f"{i+1}. ID:{row['id']} | "
                f"Source: {row.get('publication_name') or 'Unknown'} | "
                f"Headline: {row.get('headline') or row.get('headline_original') or 'N/A'} | "
                f"Summary: {(row.get('summary') or 'N/A')[:200]}\n"
            )

        classify_prompt = f"""You are an editorial intelligence assistant. Given a MAIN article and several CANDIDATE articles, classify each candidate's relationship to the main article.

MAIN ARTICLE:
Headline: {target['headline_en'] or 'N/A'}
Summary: {(target['summary'] or 'N/A')[:300]}

CANDIDATES:
{candidates_txt}

For each candidate, respond with ONLY a JSON array (no other text):
[
  {{"id": 123, "relationship": "ADDS_DETAIL", "reason": "Brief reason"}},
  ...
]

Relationship types:
- DUPLICATE: Same story, same facts, no new information worth including
- ADDS_DETAIL: Same story but includes additional facts, data, or context
- DIFFERENT_ANGLE: Same topic but from a notably different editorial perspective
- CONTRARIAN: Disagrees with or challenges the main article's framing
- RELATED: Tangentially related but essentially a different story

Be strict: only classify as ADDS_DETAIL/DIFFERENT_ANGLE/CONTRARIAN if the article genuinely provides value beyond the main. Most similar articles are DUPLICATE."""

        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You classify article relationships. Respond with valid JSON only."},
                {"role": "user", "content": classify_prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
        )

        raw_response = chat.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw_response.startswith("```"):
            raw_response = raw_response.split("\n", 1)[1] if "\n" in raw_response else raw_response[3:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3].strip()

        try:
            classifications = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.warning(f"Smart-similar: Groq returned invalid JSON, falling back. Response: {raw_response[:200]}")
            # Fallback: return all similar articles as ADDS_DETAIL
            results = []
            for row in similar_rows:
                row['relationship'] = 'ADDS_DETAIL'
                row['reason'] = 'AI classification unavailable'
                row['distance'] = row.pop('similarity', 0.0)
                results.append(row)
            return results

        # 4. Build classification map — return ALL articles with labels (don't filter)
        #    Let the frontend pre-check valuable ones and uncheck duplicates.
        class_map = {}
        for c in classifications:
            class_map[c.get('id')] = {
                'relationship': c.get('relationship', 'DUPLICATE'),
                'reason': c.get('reason', ''),
            }

        results = []
        for row in similar_rows:
            info = class_map.get(row['id'], {'relationship': 'DUPLICATE', 'reason': ''})
            row['relationship'] = info['relationship']
            row['reason'] = info['reason']
            row['distance'] = row.pop('similarity', 0.0)
            results.append(row)

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Smart-similar error: {e}")
        raise HTTPException(500, f"Error: {e}")
    finally:
        cursor.close()
        conn.close()


@router.post("/cluster/approve", response_model=ClusterAnalysisResponse)
async def analyze_and_approve_cluster(request: ClusterAnalysisRequest):
    original_id = request.original_article_id
    cluster_ids = request.cluster_ids
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        all_ids = [original_id] + cluster_ids
        q_placeholders = ','.join(['%s'] * len(all_ids))
        cursor.execute(
            f"SELECT id, headline_en, summary, publication_name, url, category FROM articles WHERE id IN ({q_placeholders})",
            tuple(all_ids),
        )
        articles = {row['id']: dict(row) for row in cursor.fetchall()}

        # Build structured input for Groq
        orig = articles.get(original_id, {})
        related_txt = ""
        for i, aid in enumerate(cluster_ids):
            rel = articles.get(aid, {})
            related_txt += (
                f"--- RELATED {i+1} (Source: {rel.get('publication_name') or 'Unknown'}) ---\n"
                f"Headline: {rel.get('headline_en')}\n"
                f"Summary: {rel.get('summary')}\n\n"
            )

        cluster_system_prompt = """You are a senior geopolitical analyst writing for an intelligence newsletter read by investment bankers and policymakers.

Rewrite ONLY the MAIN article's summary as a professional news brief. Requirements:
1. Lead with the core development — what happened and why it matters
2. Include specific numbers, names, and countries
3. Keep the tone professional and analytical — no editorializing
4. 50 words MAX. Do NOT exceed 50 words.
5. Use facts from the provided content. Do not speculate.
6. English only. Do NOT include dates."""

        cluster_user_prompt = (
            f"--- MAIN ARTICLE (Source: {orig.get('publication_name') or 'Unknown'}) ---\n"
            f"Headline: {orig.get('headline_en')}\n"
            f"Summary: {orig.get('summary')}\n"
        )

        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": cluster_system_prompt},
                {"role": "user", "content": cluster_user_prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
        )
        new_sum = chat.choices[0].message.content

        cursor.execute(
            "UPDATE articles SET status = 'approved', summary = %s, is_top_story = %s WHERE id = %s",
            (new_sum, request.make_top_story, original_id),
        )
        # Inherit parent's category for all children
        parent_category = orig.get('category')

        if cluster_ids:
            # Milestone D: Generate differentiated summaries for each child
            for aid in cluster_ids:
                child_art = articles.get(aid, {})
                try:
                    child_system_prompt = (
                        "You are a senior geopolitical analyst. A parent article already covers this story "
                        "with this summary:\n\n"
                        f'"{new_sum}"\n\n'
                        "Now rewrite the CHILD article below as a 50-word MAX summary that highlights what is "
                        "NEW, DIFFERENT, or UNIQUE compared to the parent — a different angle, new facts, "
                        "additional detail, or a contrarian view. Do NOT repeat what the parent already says. "
                        "Lead with the unique contribution. Professional analytical tone. "
                        "Include specific names/figures/countries. English only."
                    )
                    diff_chat = groq_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": child_system_prompt},
                            {"role": "user", "content": (
                                f"Headline: {child_art.get('headline_en', 'N/A')}\n"
                                f"Summary: {child_art.get('summary', 'N/A')}\n"
                                f"Source: {child_art.get('publication_name', 'Unknown')}"
                            )},
                        ],
                        model="llama-3.3-70b-versatile",
                        temperature=0.3,
                    )
                    child_summary = diff_chat.choices[0].message.content.strip()
                    cursor.execute(
                        "UPDATE articles SET status = 'approved', parent_id = %s, summary = %s, category = %s WHERE id = %s",
                        (original_id, child_summary, parent_category, aid),
                    )
                except Exception as child_err:
                    logger.warning(f"Child summary generation failed for {aid}: {child_err}")
                    cursor.execute(
                        "UPDATE articles SET status = 'approved', parent_id = %s, category = %s WHERE id = %s",
                        (original_id, parent_category, aid),
                    )
        conn.commit()
        return ClusterAnalysisResponse(
            new_summary=new_sum,
            approved_id=original_id,
            parent_id=original_id,
            child_ids=cluster_ids,
            is_top_story=request.make_top_story,
        )
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


# --- Cluster Management: uncluster + promote ---

@router.post("/articles/{article_id}/uncluster")
def uncluster_article(article_id: int):
    """Remove a child article from its cluster (set parent_id = NULL)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE articles SET parent_id = NULL WHERE id = %s", (article_id,))
        conn.commit()
        return {"message": "Article removed from cluster", "article_id": article_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.post("/articles/{article_id}/promote-to-parent")
def promote_to_parent(article_id: int):
    """Promote a child article to be the new parent of its cluster.
    - The old parent becomes a child
    - All other children now point to the new parent
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # Get the current child article and its parent
        cursor.execute("SELECT id, parent_id, category FROM articles WHERE id = %s", (article_id,))
        child = cursor.fetchone()
        if not child or not child['parent_id']:
            raise HTTPException(400, "Article is not a child of any cluster")

        old_parent_id = child['parent_id']
        new_parent_id = article_id

        # 1. Move all children of old parent → new parent
        cursor.execute(
            "UPDATE articles SET parent_id = %s WHERE parent_id = %s AND id != %s",
            (new_parent_id, old_parent_id, new_parent_id),
        )

        # 2. Old parent becomes child of new parent
        cursor.execute(
            "UPDATE articles SET parent_id = %s WHERE id = %s",
            (new_parent_id, old_parent_id),
        )

        # 3. New parent is no longer a child
        cursor.execute(
            "UPDATE articles SET parent_id = NULL WHERE id = %s",
            (new_parent_id,),
        )

        conn.commit()
        return {
            "message": "Promoted to parent",
            "new_parent_id": new_parent_id,
            "old_parent_id": old_parent_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


# --- Website X Posts: batch-fetch tweets for approved articles ---

@router.post("/articles/fetch-website-tweets")
def fetch_website_tweets(
    min_score: float = Query(75, description="Minimum auto_approval_score"),
    hours: int = Query(48, description="Look back N hours"),
    limit: int = Query(30, description="Max articles to process"),
    force: bool = Query(False, description="Re-fetch even if already cached"),
):
    """
    Background job: fetch X posts for website-eligible articles.
    Uses dual search (headline + keywords) via the X API, caches results
    in website_tweets JSONB column. Skips articles already fetched unless force=True.

    Call periodically (every 30-60 min) or after article approval.
    """
    import time
    import json as _json

    try:
        from services.social.twitter import fetch_tweets_for_article, is_configured as twitter_is_configured
    except ImportError:
        raise HTTPException(500, "Twitter service not available")

    if not twitter_is_configured():
        raise HTTPException(400, "X/Twitter API not configured. Set TWITTER_BEARER_TOKEN in .env")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # Find website-eligible articles that need tweet fetching
        if force:
            cursor.execute("""
                SELECT id, headline_en, summary
                FROM articles
                WHERE status = 'approved'
                  AND auto_approval_score >= %s
                  AND scraped_at >= NOW() - make_interval(hours => %s)
                ORDER BY auto_approval_score DESC, scraped_at DESC
                LIMIT %s
            """, (min_score, hours, limit))
        else:
            cursor.execute("""
                SELECT id, headline_en, summary
                FROM articles
                WHERE status = 'approved'
                  AND auto_approval_score >= %s
                  AND scraped_at >= NOW() - make_interval(hours => %s)
                  AND (website_tweets IS NULL OR website_tweets_fetched_at IS NULL
                       OR website_tweets_fetched_at < NOW() - INTERVAL '6 hours')
                ORDER BY auto_approval_score DESC, scraped_at DESC
                LIMIT %s
            """, (min_score, hours, limit))

        articles = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Fetching tweets for {len(articles)} articles (min_score={min_score}, hours={hours})")

        results = {"processed": 0, "fetched": 0, "skipped": 0, "errors": 0, "details": []}

        for art in articles:
            article_id = art['id']
            headline = art.get('headline_en') or ''
            summary = art.get('summary') or ''

            if not headline:
                results['skipped'] += 1
                continue

            try:
                tweets = fetch_tweets_for_article(headline, summary, max_results=10)
                results['processed'] += 1

                if tweets:
                    cursor.execute("""
                        UPDATE articles
                        SET website_tweets = %s::jsonb,
                            website_tweets_fetched_at = NOW()
                        WHERE id = %s
                    """, (_json.dumps(tweets), article_id))
                    conn.commit()
                    results['fetched'] += 1
                    results['details'].append({
                        'article_id': article_id,
                        'headline': headline[:80],
                        'tweets_found': len(tweets),
                    })
                else:
                    # Mark as fetched (empty) so we don't retry immediately
                    cursor.execute("""
                        UPDATE articles
                        SET website_tweets = '[]'::jsonb,
                            website_tweets_fetched_at = NOW()
                        WHERE id = %s
                    """, (article_id,))
                    conn.commit()
                    results['skipped'] += 1

                # Rate-limit politeness: pause between API calls
                time.sleep(2)

            except Exception as e:
                conn.rollback()
                results['errors'] += 1
                logger.warning(f"Tweet fetch failed for article {article_id}: {e}")
                continue

        return results

    except Exception as e:
        logger.error(f"Batch tweet fetch error: {e}")
        raise HTTPException(500, f"Batch tweet fetch error: {e}")
    finally:
        cursor.close()
        conn.close()
