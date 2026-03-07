"""
Social media automation endpoints.
Handles posting to Telegram (Phase 1), Twitter/X (Phase 2), and Social Queue (Phase 3).
"""
import json
import logging
from typing import Optional, List

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_db_connection
from models import SocialPostArticleRequest, SocialPostNewsletterRequest, BreakingNewsCheckResponse
from services.social import telegram
from services.social.twitter import QuoteTweetForbiddenError
from services.social.content_generator import (
    generate_breaking_telegram,
    generate_newsletter_telegram,
    generate_breaking_tweet,
)
from services.social.breaking_news import check_and_post_breaking_news

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/social", tags=["social"])


# ============================================================
# Request Models
# ============================================================

class TweetPostRequest(BaseModel):
    """Manual tweet posting — user composes/edits text in dashboard."""
    text: str
    article_id: Optional[int] = None
    brief_id: Optional[int] = None
    quote_tweet_id: Optional[str] = None  # If set, posts as a Quote Tweet (repost with comment)


class TweetSearchRequest(BaseModel):
    """Search X for tweets related to a headline."""
    query: str
    max_results: int = 50
    exclude_publications: bool = True
    boost_experts: bool = True
    include_replies: bool = True


class QueueAddRequest(BaseModel):
    """Add article to social posting queue."""
    article_id: int
    platforms: List[str]  # ["telegram", "twitter"] or one of them
    content_override: Optional[str] = None  # Optional pasted article content for better summary


# ============================================================
# Status & History
# ============================================================

@router.get("/status")
def get_social_status():
    """Check which social platforms are configured and ready."""
    from services.social import twitter

    twitter_configured = twitter.is_configured()
    monthly_count = 0
    if twitter_configured:
        try:
            monthly_count = twitter.get_monthly_post_count()
        except Exception:
            pass

    return {
        "telegram": {
            "configured": telegram.is_configured(),
            "description": "Telegram Bot API → channel posting",
        },
        "twitter": {
            "configured": twitter_configured,
            "description": "X/Twitter API → manual posting",
            "monthly_posts": monthly_count,
            "monthly_limit": 100,
        },
    }


@router.get("/history")
def get_social_history(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    platform: Optional[str] = Query(None),
    post_type: Optional[str] = Query(None),
):
    """Get social media post history with pagination."""
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

        # Get total count for pagination
        cursor.execute(f"SELECT COUNT(*) FROM social_posts sp {where}", params)
        total_count = cursor.fetchone()[0]

        # Fetch page
        page_params = params + [limit, offset]
        cursor.execute(f"""
            SELECT sp.id, sp.platform, sp.post_type, sp.platform_post_id,
                   sp.article_id, sp.brief_id, sp.content_text,
                   sp.status, sp.error_message, sp.posted_at, sp.created_at,
                   a.headline_en AS article_headline
            FROM social_posts sp
            LEFT JOIN articles a ON sp.article_id = a.id
            {where}
            ORDER BY sp.posted_at DESC
            LIMIT %s OFFSET %s
        """, page_params)

        posts = [dict(row) for row in cursor.fetchall()]
        return {
            "posts": posts,
            "count": len(posts),
            "total": total_count,
            "offset": offset,
            "limit": limit,
        }

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
    Called from the admin dashboard "Post to Telegram" / "Post to X" buttons.
    """
    from services.social import twitter

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

            elif platform == "twitter":
                if not twitter.is_configured():
                    results["errors"].append({"platform": "twitter", "error": "Not configured. Add X API keys to .env"})
                    continue

                # Check monthly quota
                monthly = twitter.get_monthly_post_count()
                if monthly >= 95:  # Leave 5 buffer
                    results["errors"].append({
                        "platform": "twitter",
                        "error": f"Monthly limit approaching ({monthly}/100). Post manually on x.com.",
                    })
                    continue

                # Check dedup
                cursor.execute("""
                    SELECT id FROM social_posts
                    WHERE platform = 'twitter' AND article_id = %s
                """, (request.article_id,))
                if cursor.fetchone():
                    results["errors"].append({
                        "platform": "twitter",
                        "error": "Already posted to X",
                    })
                    continue

                try:
                    text = generate_breaking_tweet(article)
                    tw_result = twitter.post_tweet(text)

                    cursor.execute("""
                        INSERT INTO social_posts
                            (platform, post_type, platform_post_id, article_id,
                             content_text, status, posted_at)
                        VALUES ('twitter', 'breaking_news', %s, %s, %s, 'sent', NOW())
                    """, (tw_result['tweet_id'], request.article_id, text))
                    conn.commit()

                    results["posted"].append({
                        "platform": "twitter",
                        "tweet_id": tw_result['tweet_id'],
                    })
                except Exception as e:
                    conn.rollback()
                    logger.error(f"X/Twitter post failed: {e}")
                    results["errors"].append({"platform": "twitter", "error": str(e)})

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
# Manual Tweet Posting (custom text)
# ============================================================

@router.post("/post/tweet")
def post_custom_tweet(request: TweetPostRequest):
    """
    Post a manually composed tweet from the dashboard.
    User writes/edits the tweet text before posting.
    """
    from services.social import twitter

    if not twitter.is_configured():
        raise HTTPException(status_code=400, detail="X/Twitter not configured. Add API keys to .env")

    if len(request.text) > 280:
        raise HTTPException(status_code=400, detail=f"Tweet too long ({len(request.text)}/280 chars)")

    # Check monthly quota
    monthly = twitter.get_monthly_post_count()
    if monthly >= 95:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly tweet limit approaching ({monthly}/100). Post manually on x.com."
        )

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        tw_result = twitter.post_tweet(request.text, quote_tweet_id=request.quote_tweet_id)

        post_type = 'quote_tweet' if request.quote_tweet_id else (
            'newsletter_digest' if request.brief_id else 'breaking_news'
        )
        cursor.execute("""
            INSERT INTO social_posts
                (platform, post_type, platform_post_id, article_id, brief_id,
                 content_text, status, posted_at)
            VALUES ('twitter', %s, %s, %s, %s, %s, 'sent', NOW())
        """, (post_type, tw_result['tweet_id'], request.article_id, request.brief_id, request.text))
        conn.commit()

        return {
            "posted": True,
            "tweet_id": tw_result['tweet_id'],
            "is_quote_tweet": bool(request.quote_tweet_id),
            "monthly_count": monthly + 1,
        }
    except QuoteTweetForbiddenError:
        # Author restricts quote tweets — return structured response for frontend fallback
        conn.rollback()
        logger.warning(f"Quote tweet blocked by author restrictions (quote_tweet_id={request.quote_tweet_id})")
        return {
            "posted": False,
            "quote_restricted": True,
            "message": "Author restricts quote tweets via API. Opening X.com for manual posting.",
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"Custom tweet failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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
# X/Twitter: Tweet Search (Techmeme-style "Find X Posts")
# ============================================================

@router.post("/twitter/search")
def search_tweets(request: TweetSearchRequest):
    """
    Search X for tweets related to a headline.
    Returns top tweets ranked by engagement for embedding in the newsletter.
    """
    from services.social import twitter

    if not twitter.is_configured():
        raise HTTPException(status_code=400, detail="X/Twitter not configured. Add API keys to .env")

    try:
        tweets = twitter.search_recent_tweets(
            query=request.query,
            max_results=request.max_results,
            exclude_publications=request.exclude_publications,
            boost_experts=request.boost_experts,
            include_replies=request.include_replies,
        )
        return {
            "query": request.query,
            "count": len(tweets),
            "tweets": tweets,
        }
    except Exception as e:
        logger.error(f"Tweet search failed: {e}")
        raise HTTPException(status_code=502, detail=f"Tweet search failed: {e}")


# ============================================================
# X/Twitter: Save Selected Tweets to Article
# ============================================================

@router.post("/twitter/embed/{article_id}")
def save_tweet_embeds(article_id: int, tweets: list[dict]):
    """
    Save selected tweets to an article for newsletter embedding.
    Accepts full tweet objects [{username, text, url}] so the newsletter
    can render them without re-fetching from X API.
    Stores in articles.embedded_tweets JSONB column.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Validate and normalize tweet objects
        clean_tweets = []
        for t in tweets:
            if isinstance(t, dict):
                clean_tweets.append({
                    "username": t.get("username", ""),
                    "text": t.get("text", ""),
                    "url": t.get("url", ""),
                })
            elif isinstance(t, str):
                # Backwards compatibility: if just a string ID is passed
                clean_tweets.append({"username": "", "text": "", "url": t})

        # Append to existing embedded tweets (don't overwrite)
        cursor.execute(
            "SELECT embedded_tweets FROM articles WHERE id = %s", (article_id,)
        )
        row = cursor.fetchone()
        existing = []
        if row and row[0]:
            existing = row[0] if isinstance(row[0], list) else []

        # Deduplicate by URL
        existing_urls = {t.get('url', '') for t in existing if isinstance(t, dict)}
        for t in clean_tweets:
            if t['url'] not in existing_urls:
                existing.append(t)
                existing_urls.add(t['url'])

        cursor.execute("""
            UPDATE articles
            SET embedded_tweets = %s::jsonb
            WHERE id = %s
        """, (json.dumps(existing), article_id))
        conn.commit()

        return {"saved": True, "article_id": article_id, "tweet_count": len(existing)}
    except Exception as e:
        logger.error(f"Save tweet embeds failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


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
        elif platform == "twitter":
            text = generate_breaking_tweet(article)
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


# ============================================================
# Social Posting Queue
# ============================================================

# Groq client for queue summary generation (injected from main.py)
_groq_client = None

def init_queue_groq(groq_client):
    """Called from main.py to inject Groq client for queue summaries."""
    global _groq_client
    _groq_client = groq_client


@router.post("/queue/add")
def add_to_queue(request: QueueAddRequest):
    """Add article to social posting queue with AI-generated content."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id, url, headline, headline_en, summary, summary_long,
                   category, publication_name, country_codes
            FROM articles WHERE id = %s
        """, (request.article_id,))
        article = cursor.fetchone()
        if not article:
            raise HTTPException(404, "Article not found")
        article = dict(article)

        results = []
        for platform in request.platforms:
            if platform not in ('telegram', 'twitter'):
                continue

            # Generate content: use override if provided, else auto-generate
            if request.content_override and request.content_override.strip():
                # User pasted article content → Groq generates 100-word summary
                content_text = _generate_queue_content(
                    article, platform, request.content_override.strip()
                )
            else:
                # Auto-generate from existing summary
                content_text = _generate_queue_content(article, platform)

            cursor.execute("""
                INSERT INTO social_queue (article_id, platform, content_text, status)
                VALUES (%s, %s, %s, 'queued')
                RETURNING id, queued_at
            """, (request.article_id, platform, content_text))
            row = cursor.fetchone()
            results.append({
                "queue_id": row['id'],
                "platform": platform,
                "content_preview": content_text[:200],
                "queued_at": str(row['queued_at']),
            })

        conn.commit()
        return {"queued": results}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Queue add error: {e}")
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.get("/queue")
def get_queue(
    status: str = Query("queued"),
    limit: int = Query(20, ge=1, le=100),
):
    """List items in the social posting queue."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT q.id, q.article_id, q.platform, q.content_text,
                   q.status, q.queued_at, q.posted_at, q.error_message,
                   a.headline_en AS headline, a.publication_name
            FROM social_queue q
            LEFT JOIN articles a ON a.id = q.article_id
            WHERE q.status = %s
            ORDER BY q.queued_at ASC
            LIMIT %s
        """, (status, limit))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


@router.delete("/queue/{queue_id}")
def cancel_queue_item(queue_id: int):
    """Cancel a queued item."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE social_queue SET status = 'cancelled' WHERE id = %s AND status = 'queued'",
            (queue_id,)
        )
        if cursor.rowcount == 0:
            raise HTTPException(404, "Queue item not found or already processed")
        conn.commit()
        return {"message": "Cancelled"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.post("/queue/{queue_id}/post-now")
def post_queue_item_now(queue_id: int):
    """Immediately post a queued item."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(
            "SELECT * FROM social_queue WHERE id = %s AND status = 'queued'",
            (queue_id,)
        )
        item = cursor.fetchone()
        if not item:
            raise HTTPException(404, "Queue item not found or already processed")
        item = dict(item)

        result = _post_queue_item(item, cursor, conn)
        return result
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


def _generate_queue_content(article: dict, platform: str, content_override: str = None) -> str:
    """Generate social post content for the queue.
    If content_override is provided (user pasted content), generates 100-word summary.
    Otherwise auto-generates from existing article data."""

    if content_override and _groq_client:
        # User pasted content → Groq generates 100-word summary
        try:
            chat = _groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": (
                        "Write a 100-word social media post summarizing this geopolitical news. "
                        "Authoritative, analytical tone. Include key names, figures, countries. "
                        "No hashtags. English only."
                    )},
                    {"role": "user", "content": content_override},
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
            )
            summary = chat.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq queue summary failed: {e}")
            summary = article.get('summary_long') or article.get('summary') or ''
    elif _groq_client:
        # Auto-generate from existing data
        source_text = f"Headline: {article.get('headline_en') or article.get('headline', '')}\nSummary: {article.get('summary', '')}"
        try:
            chat = _groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": (
                        "Expand this into a 100-word social media post about geopolitical news. "
                        "Authoritative, analytical tone. Include key names, figures, countries. "
                        "No hashtags. English only."
                    )},
                    {"role": "user", "content": source_text},
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
            )
            summary = chat.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq queue auto-summary failed: {e}")
            summary = article.get('summary_long') or article.get('summary') or ''
    else:
        summary = article.get('summary_long') or article.get('summary') or ''

    # Format for platform
    pub = article.get('publication_name') or ''
    url = article.get('url') or ''

    if platform == 'telegram':
        category = article.get('category', 'Geopolitics')
        return (
            f"📰 {category}\n\n"
            f"{summary}\n\n"
            f"📌 Source: {pub}\n"
            f'<a href="{url}">Read full article</a>\n\n'
            f"🌐 @GeoMemoIntel"
        )
    else:
        # Twitter: 280 char limit, no links (X penalizes them)
        if len(summary) > 250:
            summary = summary[:247] + '...'
        return f"{summary}\n\n— via {pub}"


def _post_queue_item(item: dict, cursor, conn) -> dict:
    """Post a single queue item to its platform."""
    platform = item['platform']
    content = item['content_text']
    queue_id = item['id']

    try:
        if platform == 'telegram':
            if not telegram.is_configured():
                raise Exception("Telegram not configured")
            result = telegram.send_message(content, disable_web_page_preview=False)
            platform_post_id = str(result.get('message_id', ''))

        elif platform == 'twitter':
            from services.social import twitter
            if not twitter.is_configured():
                raise Exception("Twitter not configured")
            # Twitter content: strip HTML for plain text
            import re
            plain_text = re.sub(r'<[^>]*>', '', content)
            if len(plain_text) > 280:
                plain_text = plain_text[:277] + '...'
            tweet_result = twitter.post_tweet(plain_text)
            platform_post_id = str(tweet_result.get('id', ''))
        else:
            raise Exception(f"Unknown platform: {platform}")

        # Mark as posted
        cursor.execute("""
            UPDATE social_queue SET status = 'posted', posted_at = NOW()
            WHERE id = %s
        """, (queue_id,))

        # Also record in social_posts for history
        cursor.execute("""
            INSERT INTO social_posts (platform, post_type, platform_post_id, article_id, content_text, status, posted_at)
            VALUES (%s, 'queued_post', %s, %s, %s, 'sent', NOW())
        """, (platform, platform_post_id, item.get('article_id'), content))
        conn.commit()

        return {"message": f"Posted to {platform}", "platform_post_id": platform_post_id}

    except Exception as e:
        cursor.execute("""
            UPDATE social_queue SET status = 'failed', error_message = %s
            WHERE id = %s
        """, (str(e)[:500], queue_id))
        conn.commit()
        raise HTTPException(500, f"Post failed: {e}")
