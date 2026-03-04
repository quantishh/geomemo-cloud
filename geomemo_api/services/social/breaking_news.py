"""
Breaking news detection and dispatch.
Scans for high-scoring recent approved articles and posts to configured platforms.
Runs as a background task every 15 minutes.
"""
import logging
from datetime import datetime, timedelta, timezone

import psycopg2.extras

from database import get_db_connection
from config import (
    BREAKING_NEWS_MIN_APPROVAL_SCORE,
    BREAKING_NEWS_MIN_CONFIDENCE,
    BREAKING_NEWS_MAX_AGE_MINUTES,
)
from services.social import telegram
from services.social.content_generator import generate_breaking_telegram

logger = logging.getLogger(__name__)


def check_and_post_breaking_news() -> dict:
    """
    Find articles that meet breaking news criteria and haven't been posted yet.
    Posts to all configured platforms.

    Criteria:
    - auto_approval_score >= 85 (configurable)
    - confidence_score >= 80 (configurable)
    - status = 'approved' (must pass curation)
    - scraped_at within last 30 minutes (configurable)
    - Not already in social_posts for that platform (dedup)
    - Not a child article (parent_id IS NULL)

    Returns summary of what was posted.
    """
    results = {"articles_found": 0, "articles_posted": 0, "posts": []}

    if not telegram.is_configured():
        logger.debug("Breaking news check skipped: no platforms configured.")
        return results

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=BREAKING_NEWS_MAX_AGE_MINUTES)

        cursor.execute("""
            SELECT a.id, a.url, a.headline_en, a.headline, a.summary, a.category,
                   a.publication_name, a.auto_approval_score, a.confidence_score,
                   a.country_codes, a.scraped_at
            FROM articles a
            WHERE a.auto_approval_score >= %s
              AND a.confidence_score >= %s
              AND a.scraped_at >= %s
              AND a.status = 'approved'
              AND a.parent_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM social_posts sp
                  WHERE sp.article_id = a.id AND sp.platform = 'telegram'
              )
            ORDER BY a.auto_approval_score DESC
            LIMIT 5
        """, (BREAKING_NEWS_MIN_APPROVAL_SCORE, BREAKING_NEWS_MIN_CONFIDENCE, cutoff))

        articles = [dict(row) for row in cursor.fetchall()]
        results["articles_found"] = len(articles)

        if not articles:
            return results

        for article in articles:
            # --- Telegram ---
            if telegram.is_configured():
                try:
                    text = generate_breaking_telegram(article)
                    tg_result = telegram.send_message(text)

                    cursor.execute("""
                        INSERT INTO social_posts
                            (platform, post_type, platform_post_id, article_id,
                             content_text, status, posted_at)
                        VALUES ('telegram', 'breaking_news', %s, %s, %s, 'sent', NOW())
                        ON CONFLICT (platform, article_id) WHERE article_id IS NOT NULL
                        DO NOTHING
                        RETURNING id
                    """, (str(tg_result['message_id']), article['id'], text))
                    conn.commit()

                    if cursor.rowcount > 0:
                        results["articles_posted"] += 1
                        results["posts"].append({
                            "platform": "telegram",
                            "article_id": article['id'],
                            "headline": article.get('headline_en') or article.get('headline'),
                        })
                        logger.info(f"Breaking news posted to Telegram: article {article['id']}")

                except Exception as e:
                    conn.rollback()
                    logger.error(f"Telegram post failed for article {article['id']}: {e}")
                    # Record the failure
                    try:
                        cursor.execute("""
                            INSERT INTO social_posts
                                (platform, post_type, article_id, content_text,
                                 status, error_message)
                            VALUES ('telegram', 'breaking_news', %s, '', 'failed', %s)
                            ON CONFLICT (platform, article_id) WHERE article_id IS NOT NULL
                            DO NOTHING
                        """, (article['id'], str(e)[:500]))
                        conn.commit()
                    except Exception:
                        conn.rollback()

        return results

    except Exception as e:
        logger.error(f"Breaking news check error: {e}")
        conn.rollback()
        return results
    finally:
        cursor.close()
        conn.close()
