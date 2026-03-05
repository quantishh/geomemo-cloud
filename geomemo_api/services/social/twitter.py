"""
X/Twitter API client for GeoMemo.
Handles tweet posting and tweet search (for Techmeme-style X post embedding).

Requires: pip install tweepy>=4.14.0
API: X Basic tier ($200/month) — 100 posts/month, tweet search included.
"""
import logging
import re
from datetime import datetime, timezone

import tweepy

from config import (
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET,
    TWITTER_BEARER_TOKEN,
)

logger = logging.getLogger(__name__)

# Lazy-initialized clients (only created when first needed)
_client_v2 = None


def is_configured() -> bool:
    """Check if X/Twitter credentials are set (need at least API key + secret + access tokens)."""
    return bool(
        TWITTER_API_KEY
        and TWITTER_API_SECRET
        and TWITTER_ACCESS_TOKEN
        and TWITTER_ACCESS_TOKEN_SECRET
    )


def _get_client_v2() -> tweepy.Client:
    """Get or create the tweepy v2 Client (lazy init)."""
    global _client_v2
    if _client_v2 is None:
        if not is_configured():
            raise ValueError(
                "X/Twitter not configured. Set TWITTER_API_KEY, TWITTER_API_SECRET, "
                "TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET in .env"
            )
        _client_v2 = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN or None,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True,
        )
    return _client_v2


def _sanitize_x_search_query(raw_query: str) -> str:
    """
    Sanitize a headline/text for use as an X API v2 search query.
    Handles all known causes of 400 errors:
    - Reserved operators: AND, OR, NOT (case-insensitive)
    - Colons (reserved for operators like from:, is:, lang:)
    - Parentheses (reserved for grouping — unmatched = 400)
    - Quotes (reserved for exact match — unmatched = 400)
    - Apostrophes/single quotes (token delimiter, causes parse errors)
    - Hyphens (token delimiter; leading hyphen = negation operator)
    - Hash/at/dollar signs (reserved for hashtag/mention/cashtag operators)
    - Limits to 8 keywords to avoid complexity errors
    """
    query = raw_query.strip()

    # 1. Remove reserved boolean operators as standalone words
    query = re.sub(r'\b(?:AND|OR|NOT)\b', ' ', query, flags=re.IGNORECASE)

    # 2. Strip all problematic punctuation and special characters
    #    Colons, parens, quotes, apostrophes, hyphens, operators, etc.
    query = re.sub(
        r"[:()\"\'\u2018\u2019\u201c\u201d\-#$@!?;/\\|{}\[\]<>*+^~`]",
        ' ',
        query,
    )

    # 3. Collapse multiple spaces
    query = re.sub(r'\s+', ' ', query).strip()

    # 4. Remove very short words (1-2 chars) that add noise
    words = [w for w in query.split() if len(w) > 2]

    # 5. Limit to 8 keywords to avoid X API complexity errors
    words = words[:8]

    query = ' '.join(words)

    # 6. Ensure query is not empty after cleaning
    if not query or len(query) < 3:
        # Fallback: extract first few alphanumeric words from original
        fallback_words = re.findall(r'[a-zA-Z]{3,}', raw_query)
        query = ' '.join(fallback_words[:5])

    return query


def post_tweet(text: str) -> dict:
    """
    Post a single tweet. Returns dict with tweet_id.
    Max 280 chars for Basic tier.
    """
    client = _get_client_v2()
    response = client.create_tweet(text=text)
    tweet_id = response.data['id']
    logger.info(f"Tweet posted: {tweet_id}")
    return {"tweet_id": tweet_id}


def search_recent_tweets(query: str, max_results: int = 10) -> list:
    """
    Search recent tweets matching a query.
    Used for the "Find X Posts" feature (Techmeme-style).

    Returns list of dicts with: id, text, author_username, author_name,
    like_count, retweet_count, created_at, url.

    The query is auto-filtered to exclude retweets and replies for cleaner results.
    """
    if not TWITTER_BEARER_TOKEN:
        raise ValueError("TWITTER_BEARER_TOKEN required for tweet search.")

    client = _get_client_v2()

    # Sanitize the query for X API search
    clean_query = _sanitize_x_search_query(query)

    # Filter out retweets and replies, require English
    search_query = f'({clean_query}) -is:retweet -is:reply lang:en'

    # Truncate query to X API limit (512 chars for recent search)
    if len(search_query) > 512:
        search_query = search_query[:509] + '...'

    try:
        response = client.search_recent_tweets(
            query=search_query,
            max_results=min(max_results, 100),
            tweet_fields=['created_at', 'public_metrics', 'author_id'],
            user_fields=['username', 'name', 'verified'],
            expansions=['author_id'],
            sort_order='relevancy',
        )
    except tweepy.errors.TweepyException as e:
        logger.error(f"Tweet search failed: {e}")
        raise RuntimeError(f"Tweet search failed: {e}")

    if not response.data:
        return []

    # Build author lookup
    users = {}
    if response.includes and 'users' in response.includes:
        for user in response.includes['users']:
            users[user.id] = {
                'username': user.username,
                'name': user.name,
            }

    # Format results, sorted by engagement
    results = []
    for tweet in response.data:
        metrics = tweet.public_metrics or {}
        author = users.get(tweet.author_id, {})
        username = author.get('username', 'unknown')

        results.append({
            'id': str(tweet.id),
            'text': tweet.text,
            'author_username': username,
            'author_name': author.get('name', username),
            'like_count': metrics.get('like_count', 0),
            'retweet_count': metrics.get('retweet_count', 0),
            'reply_count': metrics.get('reply_count', 0),
            'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
            'url': f'https://x.com/{username}/status/{tweet.id}',
            'engagement': metrics.get('like_count', 0) + metrics.get('retweet_count', 0) * 2,
        })

    # Sort by engagement (likes + 2*retweets) descending
    results.sort(key=lambda t: t['engagement'], reverse=True)

    return results


def get_monthly_post_count() -> int:
    """
    Count how many tweets we've posted this month.
    Used to enforce the 100 posts/month Basic tier limit.
    Queries the social_posts table, not the Twitter API.
    """
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now(timezone.utc)
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cursor.execute("""
            SELECT COUNT(*) FROM social_posts
            WHERE platform = 'twitter'
              AND status = 'sent'
              AND posted_at >= %s
        """, (first_of_month,))
        return cursor.fetchone()[0]
    finally:
        cursor.close()
        conn.close()
