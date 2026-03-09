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

# Major news publication accounts to exclude from "Find X Posts" results
# These are excluded to surface individual experts and citizen journalists
MAJOR_NEWS_ACCOUNTS = [
    'CNN', 'BBCWorld', 'BBCBreaking', 'BBCNews', 'nytimes', 'washingtonpost',
    'Reuters', 'AP', 'AFP', 'AJEnglish', 'guardian', 'FT',
    'WSJ', 'business', 'CNBC', 'CBSNews', 'ABCNews', 'NBCNews',
    'FoxNews', 'MSNBC', 'NPR', 'PBS', 'TIME', 'Newsweek',
    'TheEconomist', 'ReutersWorld', 'SkyNews', 'DWNews',
    'France24_en', 'i24NEWS_EN', 'XHNews',
]


class QuoteTweetForbiddenError(Exception):
    """Raised when X API returns 403 for a quote tweet due to author conversation restrictions."""
    pass


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


def post_tweet(text: str, quote_tweet_id: str = None) -> dict:
    """
    Post a single tweet. Returns dict with tweet_id.
    Max 280 chars for Basic tier.

    If quote_tweet_id is provided, the tweet becomes a "Quote Tweet"
    (repost with comment) — the original tweet is embedded below the text.

    Raises QuoteTweetForbiddenError if the original tweet's author restricts
    who can quote their posts (403 from X API).
    """
    client = _get_client_v2()
    kwargs = {"text": text}
    if quote_tweet_id:
        kwargs["quote_tweet_id"] = quote_tweet_id
        logger.info(f"Posting quote tweet of {quote_tweet_id}")
    try:
        response = client.create_tweet(**kwargs)
    except tweepy.errors.Forbidden as e:
        error_msg = str(e).lower()
        if quote_tweet_id and ("not allowed" in error_msg or "not permitted" in error_msg):
            logger.warning(f"Quote tweet blocked by author restrictions: {quote_tweet_id}")
            raise QuoteTweetForbiddenError(
                "Author restricts quote tweets via API. Use X.com to quote manually."
            )
        raise  # Re-raise other 403 errors as-is
    tweet_id = response.data['id']
    logger.info(f"Tweet posted: {tweet_id}" + (f" (quote of {quote_tweet_id})" if quote_tweet_id else ""))
    return {"tweet_id": tweet_id}


def search_recent_tweets(
    query: str,
    max_results: int = 25,
    exclude_publications: bool = True,
    boost_experts: bool = True,
    include_replies: bool = True,
) -> list:
    """
    Search recent tweets with enhanced filtering for expert voices.

    - Fetches more tweets than requested (3x) to allow post-processing
    - Excludes major news publication accounts
    - Boosts individual experts over institutional accounts
    - Scores by engagement rate (relative to followers) not raw engagement
    - include_replies=True: includes replies where expert commentary lives
    """
    if not TWITTER_BEARER_TOKEN:
        raise ValueError("TWITTER_BEARER_TOKEN required for tweet search.")

    client = _get_client_v2()
    clean_query = _sanitize_x_search_query(query)

    # Build exclusion operators for major news accounts
    exclusions = ""
    if exclude_publications:
        # Limit exclusions to keep query under 512 chars
        exclude_accounts = MAJOR_NEWS_ACCOUNTS[:15]
        exclusions = " ".join(f"-from:{acct}" for acct in exclude_accounts)

    # Build query: always exclude retweets (no original content),
    # but INCLUDE replies (expert commentary and opinions live in replies)
    reply_filter = "" if include_replies else " -is:reply"
    search_query = f'({clean_query}) -is:retweet{reply_filter} lang:en {exclusions}'.strip()

    # Truncate to X API limit (512 chars)
    if len(search_query) > 512:
        # Remove exclusions if query is too long, keep core query
        search_query = f'({clean_query}) -is:retweet{reply_filter} lang:en'
        if len(search_query) > 512:
            search_query = search_query[:509] + '...'

    # Fetch 3x the requested amount for post-processing
    fetch_count = min(max_results * 3, 100)

    try:
        response = client.search_recent_tweets(
            query=search_query,
            max_results=fetch_count,
            tweet_fields=['created_at', 'public_metrics', 'author_id', 'in_reply_to_user_id', 'conversation_id'],
            user_fields=['username', 'name', 'verified', 'public_metrics', 'description'],
            expansions=['author_id'],
            sort_order='relevancy',
        )
    except tweepy.errors.TweepyException as e:
        logger.error(f"Tweet search failed: {e}")
        raise RuntimeError(f"Tweet search failed: {e}")

    if not response.data:
        return []

    # Build author lookup with follower data
    users = {}
    if response.includes and 'users' in response.includes:
        for user in response.includes['users']:
            user_metrics = getattr(user, 'public_metrics', None) or {}
            users[user.id] = {
                'username': user.username,
                'name': user.name,
                'followers_count': user_metrics.get('followers_count', 0),
                'description': getattr(user, 'description', '') or '',
            }

    # Process and score each tweet
    results = []
    for tweet in response.data:
        metrics = tweet.public_metrics or {}
        author = users.get(tweet.author_id, {})
        username = author.get('username', 'unknown')
        followers = author.get('followers_count', 0)
        author_desc = author.get('description', '')
        author_name = author.get('name', username)

        likes = metrics.get('like_count', 0)
        retweets = metrics.get('retweet_count', 0)
        reply_count = metrics.get('reply_count', 0)
        raw_engagement = likes + retweets * 2 + reply_count

        # Detect if this tweet is a reply
        is_reply = getattr(tweet, 'in_reply_to_user_id', None) is not None

        # --- RELEVANCE SCORING ALGORITHM ---
        score = 0.0

        # 1. Engagement rate (engagement relative to followers)
        if followers > 0:
            engagement_rate = raw_engagement / followers
            score += min(engagement_rate * 100, 40)  # Cap at 40 points
        else:
            score += min(raw_engagement * 0.5, 20)

        # 2. Expert boost: deprioritize accounts >1M followers (likely media)
        if boost_experts:
            if followers < 100_000:
                score += 15  # Individual expert range
            elif followers < 500_000:
                score += 8   # Mid-tier analysts
            # else: +0 for large institutional accounts

        # 3. Content depth: boost longer tweets (analysis, not headlines)
        tweet_length = len(tweet.text)
        if tweet_length > 200:
            score += 10  # Long analysis
        elif tweet_length > 100:
            score += 5   # Medium analysis

        # 4. Penalize accounts with "News" indicators
        news_indicators = ['news', 'media', 'press', 'daily', 'breaking', 'official']
        name_lower = author_name.lower()
        desc_lower = author_desc.lower()
        is_likely_news = any(ind in name_lower or ind in desc_lower for ind in news_indicators)
        if is_likely_news and followers > 500_000:
            score -= 20  # Strong penalty for large news accounts

        # 5. Minimum engagement floor
        if raw_engagement < 2:
            score -= 10

        # 6. Opinion/commentary boost: replies with high engagement are valuable discourse
        #    A reply that gets 5+ likes usually means the person said something insightful
        if is_reply and likes >= 5:
            score += 8  # High-engagement reply = quality commentary
        elif is_reply and likes >= 2:
            score += 4  # Moderate-engagement reply
        elif is_reply and raw_engagement < 2:
            score -= 5  # Low-engagement reply = noise ("lol", "so true")

        results.append({
            'id': str(tweet.id),
            'text': tweet.text,
            'author_username': username,
            'author_name': author_name,
            'followers_count': followers,
            'like_count': likes,
            'retweet_count': retweets,
            'reply_count': reply_count,
            'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
            'url': f'https://x.com/{username}/status/{tweet.id}',
            'engagement': raw_engagement,
            'relevance_score': round(score, 1),
            'is_likely_news': is_likely_news,
            'is_reply': is_reply,
        })

    # Sort by relevance score descending
    results.sort(key=lambda t: t['relevance_score'], reverse=True)

    # Return top N results
    return results[:max_results]


def fetch_tweets_for_article(headline: str, summary: str = "", max_results: int = 10) -> list:
    """
    Fetch tweets for an article using dual search strategy:
    1. Search by headline (captures direct discussion)
    2. Search by extracted keywords/entities (captures broader commentary)

    Deduplicates, merges, re-ranks by engagement + expert priority.
    Returns list of tweet dicts ready for JSONB storage.
    """
    if not TWITTER_BEARER_TOKEN:
        logger.warning("TWITTER_BEARER_TOKEN not set — skipping tweet fetch")
        return []

    all_tweets = {}  # keyed by tweet ID for dedup

    # --- Search 1: Headline-based (captures direct discussion) ---
    try:
        headline_results = search_recent_tweets(
            query=headline,
            max_results=15,
            exclude_publications=True,
            boost_experts=True,
            include_replies=True,
        )
        for t in headline_results:
            all_tweets[t['id']] = t
    except Exception as e:
        logger.warning(f"Headline tweet search failed: {e}")

    # --- Search 2: Keyword/entity extraction (captures broader commentary) ---
    try:
        combined_text = f"{headline} {summary}"
        # Extract proper nouns (names, countries, organizations)
        entities = re.findall(r'\b[A-Z][a-z]{2,}\b', combined_text)
        # Also extract quoted terms or significant phrases
        # Remove common English proper nouns that aren't useful for search
        common_skip = {'The', 'This', 'That', 'They', 'Their', 'There', 'These',
                       'Those', 'What', 'When', 'Where', 'Which', 'While', 'With',
                       'After', 'Before', 'About', 'Over', 'Under', 'Between',
                       'During', 'Through', 'Against', 'According', 'Also', 'More',
                       'Says', 'Said', 'Would', 'Could', 'Should', 'Will', 'Has',
                       'Have', 'Been', 'Being', 'Into', 'From', 'Some', 'Other'}
        unique_entities = []
        seen = set()
        for e in entities:
            if e not in common_skip and e.lower() not in seen:
                seen.add(e.lower())
                unique_entities.append(e)

        # Build keyword query from top entities (max 6 for focused search)
        if len(unique_entities) >= 2:
            keyword_query = ' '.join(unique_entities[:6])
            keyword_results = search_recent_tweets(
                query=keyword_query,
                max_results=15,
                exclude_publications=True,
                boost_experts=True,
                include_replies=True,
            )
            for t in keyword_results:
                if t['id'] not in all_tweets:
                    all_tweets[t['id']] = t
    except Exception as e:
        logger.warning(f"Keyword tweet search failed: {e}")

    if not all_tweets:
        return []

    # Re-rank merged results by relevance_score
    merged = sorted(all_tweets.values(), key=lambda t: t['relevance_score'], reverse=True)

    # Return top N in storage format
    return [
        {
            'username': t['author_username'],
            'text': t['text'],
            'url': t['url'],
            'like_count': t.get('like_count', 0),
            'retweet_count': t.get('retweet_count', 0),
            'reply_count': t.get('reply_count', 0),
            'followers_count': t.get('followers_count', 0),
            'relevance_score': t.get('relevance_score', 0),
            'is_reply': t.get('is_reply', False),
        }
        for t in merged[:max_results]
    ]


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
