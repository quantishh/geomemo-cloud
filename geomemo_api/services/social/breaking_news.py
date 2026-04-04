"""
Article drip feed and breaking news dispatch.

Two modes:
1. DRIP FEED (automatic, background loop):
   - Posts 1 approved article every 30 minutes during business hours (7AM-10PM ET)
   - Picks highest-scoring unposted articles from the last 24 hours
   - Keeps the Telegram channel active throughout the day

2. BREAKING NEWS (manual trigger from admin dashboard):
   - Scans for high-scoring recent articles and posts immediately
   - Same scoring criteria, no time-of-day restriction
"""
import logging
from datetime import datetime, timedelta, timezone

import psycopg2.extras

from database import get_db_connection
from config import (
    DRIP_MIN_APPROVAL_SCORE,
    DRIP_MIN_CONFIDENCE,
    DRIP_ARTICLES_PER_CYCLE,
    DRIP_LOOKBACK_HOURS,
    DRIP_START_HOUR_ET,
    DRIP_END_HOUR_ET,
)
from services.social import telegram
from services.social.content_generator import generate_breaking_telegram

logger = logging.getLogger(__name__)

# Eastern Time offsets
ET_OFFSET_STANDARD = timezone(timedelta(hours=-5))  # EST
ET_OFFSET_DAYLIGHT = timezone(timedelta(hours=-4))   # EDT


def _get_et_hour() -> int:
    """Get the current hour in US Eastern Time (handles EST/EDT roughly)."""
    now_utc = datetime.now(timezone.utc)
    month = now_utc.month
    if 3 < month < 11:
        et_now = now_utc.astimezone(ET_OFFSET_DAYLIGHT)
    elif month == 3:
        et_now = now_utc.astimezone(ET_OFFSET_DAYLIGHT if now_utc.day >= 10 else ET_OFFSET_STANDARD)
    elif month == 11:
        et_now = now_utc.astimezone(ET_OFFSET_STANDARD if now_utc.day >= 3 else ET_OFFSET_DAYLIGHT)
    else:
        et_now = now_utc.astimezone(ET_OFFSET_STANDARD)
    return et_now.hour


def is_within_posting_hours() -> bool:
    """Check if current time is within the configured posting window (Eastern Time)."""
    current_hour = _get_et_hour()
    return DRIP_START_HOUR_ET <= current_hour < DRIP_END_HOUR_ET


def _post_articles_to_telegram(articles: list, conn, cursor) -> dict:
    """
    Shared logic: post a list of articles to Telegram and record in social_posts.
    Returns dict with articles_posted count and posts list.
    """
    results = {"articles_posted": 0, "posts": []}

    for article in articles:
        if not telegram.is_configured():
            break
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
                logger.info(f"Posted to Telegram: article {article['id']}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Telegram post failed for article {article['id']}: {e}")
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


def drip_feed_articles() -> dict:
    """
    Background drip feed: post 1 approved article per cycle during posting hours.

    Called by the background loop every DRIP_INTERVAL_MINUTES (default 30 min).
    Only runs during DRIP_START_HOUR_ET to DRIP_END_HOUR_ET (default 7AM-10PM ET).
    Posts DRIP_ARTICLES_PER_CYCLE articles per call (default: 1).
    Looks back DRIP_LOOKBACK_HOURS for eligible articles (default: 24h).
    """
    results = {"articles_found": 0, "articles_posted": 0, "posts": [], "skipped_reason": None}

    # Check posting hours
    if not is_within_posting_hours():
        current_hour = _get_et_hour()
        results["skipped_reason"] = (
            f"Outside posting hours ({DRIP_START_HOUR_ET}:00-{DRIP_END_HOUR_ET}:00 ET). "
            f"Current ET hour: {current_hour}"
        )
        logger.debug(results["skipped_reason"])
        return results

    if not telegram.is_configured():
        results["skipped_reason"] = "No platforms configured"
        return results

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Advisory lock to prevent duplicate posts from multiple uvicorn workers
        # Lock ID 8675309 is arbitrary — just needs to be consistent
        cursor.execute("SELECT pg_try_advisory_lock(8675309)")
        got_lock = cursor.fetchone()[0]
        if not got_lock:
            results["skipped_reason"] = "Another worker is already running drip feed"
            logger.debug("Drip feed skipped — another worker holds the lock")
            cursor.close()
            conn.close()
            return results

        cutoff = datetime.now(timezone.utc) - timedelta(hours=DRIP_LOOKBACK_HOURS)

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
            LIMIT %s
        """, (DRIP_MIN_APPROVAL_SCORE, DRIP_MIN_CONFIDENCE, cutoff, DRIP_ARTICLES_PER_CYCLE))

        articles = [dict(row) for row in cursor.fetchall()]
        results["articles_found"] = len(articles)

        if not articles:
            results["skipped_reason"] = "No eligible articles to post"
            return results

        post_results = _post_articles_to_telegram(articles, conn, cursor)
        results["articles_posted"] = post_results["articles_posted"]
        results["posts"] = post_results["posts"]

        return results

    except Exception as e:
        logger.error(f"Drip feed error: {e}")
        conn.rollback()
        return results
    finally:
        # Release advisory lock
        try:
            cursor.execute("SELECT pg_advisory_unlock(8675309)")
        except Exception:
            pass
        cursor.close()
        conn.close()


def check_and_post_breaking_news() -> dict:
    """
    Manual trigger: post eligible articles NOW regardless of posting hours.
    Posts up to 5 articles at once (for admin dashboard "Check Breaking News" button).
    """
    results = {"articles_found": 0, "articles_posted": 0, "posts": []}

    if not telegram.is_configured():
        logger.debug("Breaking news check skipped: no platforms configured.")
        return results

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=DRIP_LOOKBACK_HOURS)

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
        """, (DRIP_MIN_APPROVAL_SCORE, DRIP_MIN_CONFIDENCE, cutoff))

        articles = [dict(row) for row in cursor.fetchall()]
        results["articles_found"] = len(articles)

        if not articles:
            return results

        post_results = _post_articles_to_telegram(articles, conn, cursor)
        results["articles_posted"] = post_results["articles_posted"]
        results["posts"] = post_results["posts"]

        return results

    except Exception as e:
        logger.error(f"Breaking news check error: {e}")
        conn.rollback()
        return results
    finally:
        cursor.close()
        conn.close()
