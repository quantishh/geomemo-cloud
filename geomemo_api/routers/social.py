"""
Social media automation endpoints.
Handles posting to Telegram (Phase 1) and Twitter/X (Phase 2).
"""
import logging
from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query

from database import get_db_connection
from models import SocialPostArticleRequest, SocialPostNewsletterRequest, BreakingNewsCheckResponse
from services.social import telegram
from services.social.content_generator import (
    generate_breaking_telegram,
    generate_newsletter_telegram,
)
from services.social.breaking_news import check_and_post_breaking_news

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/social", tags=["social"])


# ============================================================
# Status & History
# ============================================================

@router.get("/status")
def get_social_status():
    """Check which social platforms are configured and ready."""
    return {
        "telegram": {
            "configured": telegram.is_configured(),
            "description": "Telegram Bot API → channel posting",
        },
        "twitter": {
            "configured": False,  # Phase 2
            "description": "X/Twitter API (not yet configured)",
        },
    }


@router.get("/history")
def get_social_history(
    limit: int = Query(20, ge=1, le=100),
    platform: Optional[str] = Query(None),
    post_type: Optional[str] = Query(None),
):
    """Get recent social media post history."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        conditions = []
        params = []

        if platform:
            conditions.append("sp.platform = %s")
            params.append(platform)
        if post_type:
            conditions.append("sp.post_type = %s")
            params.append(post_type)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        cursor.execute(f"""
            SELECT sp.id, sp.platform, sp.post_type, sp.platform_post_id,
                   sp.article_id, sp.brief_id, sp.content_text,
                   sp.status, sp.error_message, sp.posted_at, sp.created_at,
                   a.headline_en AS article_headline
            FROM social_posts sp
            LEFT JOIN articles a ON sp.article_id = a.id
            {where}
            ORDER BY sp.posted_at DESC
            LIMIT %s
        """, params)

        posts = [dict(row) for row in cursor.fetchall()]
        return {"posts": posts, "count": len(posts)}

    finally:
        cursor.close()
        conn.close()


# ============================================================
# Manual Posting: Single Article
# ============================================================

@router.post("/post/article")
def post_article_to_social(request: SocialPostArticleRequest):
    """
    Manually post a specific article to social media.
    Called from the admin dashboard "Post to Telegram" button.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    results = {"posted": [], "errors": []}

    try:
        # Fetch the article
        cursor.execute("""
            SELECT id, url, headline, headline_en, summary, category,
                   publication_name, country_codes, auto_approval_score,
                   confidence_score
            FROM articles WHERE id = %s
        """, (request.article_id,))
        article = cursor.fetchone()

        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        article = dict(article)

        for platform in request.platforms:
            if platform == "telegram":
                if not telegram.is_configured():
                    results["errors"].append({"platform": "telegram", "error": "Not configured"})
                    continue

                # Check dedup
                cursor.execute("""
                    SELECT id FROM social_posts
                    WHERE platform = 'telegram' AND article_id = %s
                """, (request.article_id,))
                if cursor.fetchone():
                    results["errors"].append({
                        "platform": "telegram",
                        "error": "Already posted to Telegram",
                    })
                    continue

                try:
                    text = generate_breaking_telegram(article)
                    tg_result = telegram.send_message(text)

                    cursor.execute("""
                        INSERT INTO social_posts
                            (platform, post_type, platform_post_id, article_id,
                             content_text, status, posted_at)
                        VALUES ('telegram', 'breaking_news', %s, %s, %s, 'sent', NOW())
                    """, (str(tg_result['message_id']), request.article_id, text))
                    conn.commit()

                    results["posted"].append({
                        "platform": "telegram",
                        "message_id": tg_result['message_id'],
                    })
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Telegram post failed: {e}")
                    results["errors"].append({"platform": "telegram", "error": str(e)})

            # Phase 2: elif platform == "twitter": ...

            else:
                results["errors"].append({
                    "platform": platform,
                    "error": f"Unknown platform: {platform}",
                })

        return results

    finally:
        cursor.close()
        conn.close()


# ============================================================
# Manual Posting: Newsletter Digest
# ============================================================

@router.post("/post/newsletter/{brief_id}")
def post_newsletter_to_social(
    brief_id: int,
    request: SocialPostNewsletterRequest = SocialPostNewsletterRequest(),
):
    """
    Post a newsletter digest to social media.
    Called from the admin dashboard after newsletter generation.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    results = {"posted": [], "errors": []}

    try:
        # Fetch the brief
        cursor.execute("""
            SELECT id, date, summary_text, summary_html, subject_line, word_count
            FROM daily_briefs WHERE id = %s
        """, (brief_id,))
        brief = cursor.fetchone()
        if not brief:
            raise HTTPException(status_code=404, detail="Newsletter brief not found")
        brief = dict(brief)

        # Fetch approved articles for that date
        cursor.execute("""
            SELECT id, url, headline, headline_en, summary, category,
                   publication_name, is_top_story, parent_id, country_codes
            FROM articles
            WHERE status = 'approved'
              AND scraped_at::date = %s
            ORDER BY is_top_story DESC, scraped_at DESC
        """, (brief['date'],))
        articles = [dict(row) for row in cursor.fetchall()]

        for platform in request.platforms:
            if platform == "telegram":
                if not telegram.is_configured():
                    results["errors"].append({"platform": "telegram", "error": "Not configured"})
                    continue

                # Check dedup by brief_id
                cursor.execute("""
                    SELECT id FROM social_posts
                    WHERE platform = 'telegram' AND brief_id = %s
                """, (brief_id,))
                if cursor.fetchone():
                    results["errors"].append({
                        "platform": "telegram",
                        "error": "Newsletter already posted to Telegram",
                    })
                    continue

                try:
                    text = generate_newsletter_telegram(brief, articles)
                    tg_result = telegram.send_message(text, disable_web_page_preview=True)

                    cursor.execute("""
                        INSERT INTO social_posts
                            (platform, post_type, platform_post_id, brief_id,
                             content_text, status, posted_at)
                        VALUES ('telegram', 'newsletter_digest', %s, %s, %s, 'sent', NOW())
                    """, (str(tg_result['message_id']), brief_id, text))
                    conn.commit()

                    results["posted"].append({
                        "platform": "telegram",
                        "message_id": tg_result['message_id'],
                    })
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Telegram newsletter post failed: {e}")
                    results["errors"].append({"platform": "telegram", "error": str(e)})

            # Phase 2: elif platform == "twitter": ...

            else:
                results["errors"].append({
                    "platform": platform,
                    "error": f"Unknown platform: {platform}",
                })

        return results

    finally:
        cursor.close()
        conn.close()


# ============================================================
# Breaking News: Manual Trigger
# ============================================================

@router.post("/breaking-news/check")
def trigger_breaking_news_check():
    """
    Manually trigger a breaking news scan.
    Same logic as the background checker, but on-demand.
    """
    result = check_and_post_breaking_news()
    return result


# ============================================================
# Preview (generate content without posting)
# ============================================================

@router.get("/preview/article/{article_id}")
def preview_article_post(article_id: int, platform: str = "telegram"):
    """Preview what a social media post would look like for an article."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id, url, headline, headline_en, summary, category,
                   publication_name, country_codes
            FROM articles WHERE id = %s
        """, (article_id,))
        article = cursor.fetchone()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        article = dict(article)

        if platform == "telegram":
            text = generate_breaking_telegram(article)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

        return {
            "platform": platform,
            "content": text,
            "char_count": len(text),
        }
    finally:
        cursor.close()
        conn.close()
