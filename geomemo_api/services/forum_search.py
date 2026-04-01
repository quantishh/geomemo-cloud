"""
Phase 5: Google Discussions & Forums Search via SerpAPI
Fetches Reddit, Quora, and other forum discussions about geopolitical topics.
"""
import json
import logging
import os
import requests
from urllib.parse import quote_plus
from datetime import datetime

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")


def search_forum_discussions(query: str, max_results: int = 10) -> list:
    """
    Search Google Discussions & Forums for a query.
    Returns structured list of forum posts from Reddit, Quora, etc.
    """
    if not SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not set, skipping forum search")
        return []

    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "tbm": "dsc",  # Discussions tab
                "gl": "us",
                "hl": "en",
                "num": max_results,
                "api_key": SERPAPI_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        discussions = []
        for item in data.get("discussions_and_forums", [])[:max_results]:
            discussions.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "source": item.get("source", ""),
                "snippet": item.get("snippet", ""),
                "date": item.get("date", ""),
                "comments": item.get("comments", 0),
                "platform": _detect_platform(item.get("link", "")),
            })

        # Also check organic results for discussions
        for item in data.get("organic_results", [])[:max_results]:
            link = item.get("link", "")
            if _is_forum_url(link):
                discussions.append({
                    "title": item.get("title", ""),
                    "link": link,
                    "source": item.get("source", ""),
                    "snippet": item.get("snippet", ""),
                    "date": item.get("date", ""),
                    "comments": 0,
                    "platform": _detect_platform(link),
                })

        # Dedup by URL
        seen = set()
        unique = []
        for d in discussions:
            if d["link"] not in seen:
                seen.add(d["link"])
                unique.append(d)

        logger.info(f"Forum search for '{query[:50]}': {len(unique)} results")
        return unique[:max_results]

    except requests.exceptions.RequestException as e:
        logger.error(f"SerpAPI forum search error: {e}")
        return []
    except Exception as e:
        logger.error(f"Forum search unexpected error: {e}")
        return []


def search_forums_for_article(headline: str, countries: list = None,
                               max_results: int = 5) -> list:
    """
    Search forums for discussions about a specific article/topic.
    Builds a targeted query from headline + country context.
    """
    # Build search query
    # Take key terms from headline (remove common words)
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on',
                  'at', 'to', 'for', 'of', 'with', 'and', 'or', 'but', 'not',
                  'has', 'have', 'had', 'will', 'would', 'could', 'should',
                  'this', 'that', 'these', 'those', 'from', 'by', 'as', 'it',
                  'its', 'be', 'been', 'being', 'do', 'does', 'did', 'says',
                  'said', 'new', 'over', 'after', 'about', 'into', 'up'}

    words = headline.split()
    key_terms = [w for w in words if w.lower().strip('.,!?:;') not in stop_words
                 and len(w) > 2][:8]
    query = ' '.join(key_terms)

    if countries and len(countries) <= 2:
        query += ' ' + ' '.join(countries[:2])

    return search_forum_discussions(query, max_results=max_results)


def fetch_forums_for_top_articles(cursor, article_ids: list,
                                   max_per_article: int = 3) -> dict:
    """
    Fetch forum discussions for multiple articles.
    Returns: {article_id: [discussion_dict, ...]}
    Stores results in forum_discussions table.
    """
    import time

    forum_map = {}
    total_stored = 0

    for article_id in article_ids:
        cursor.execute("""
            SELECT headline_en, headline, country_codes
            FROM articles WHERE id = %s
        """, (article_id,))
        row = cursor.fetchone()
        if not row:
            continue

        headline = row[0] or row[1] or ''
        countries = row[2] or []

        discussions = search_forums_for_article(
            headline, countries, max_results=max_per_article
        )

        if discussions:
            forum_map[article_id] = discussions

            # Store in DB
            for disc in discussions:
                try:
                    cursor.execute("""
                        INSERT INTO forum_discussions
                            (url, title, forum_name, content, platform,
                             upvotes, article_id, scraped_at, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 'approved')
                        ON CONFLICT (url) DO NOTHING
                    """, (
                        disc['link'], disc['title'], disc['source'],
                        disc['snippet'], disc['platform'],
                        disc.get('comments', 0), article_id,
                    ))
                    total_stored += 1
                except Exception as e:
                    logger.debug(f"Forum insert failed: {e}")

        time.sleep(1)  # Rate limit between SERP API calls

    try:
        cursor.connection.commit()
    except Exception:
        cursor.connection.rollback()

    logger.info(f"Forum discussions: {total_stored} stored for {len(forum_map)} articles")
    return forum_map


def _detect_platform(url: str) -> str:
    """Detect which forum platform a URL belongs to."""
    url_lower = url.lower()
    if 'reddit.com' in url_lower:
        return 'reddit'
    elif 'quora.com' in url_lower:
        return 'quora'
    elif 'stackexchange.com' in url_lower or 'stackoverflow.com' in url_lower:
        return 'stackexchange'
    elif 'facebook.com' in url_lower or 'fb.com' in url_lower:
        return 'facebook'
    elif 'news.ycombinator.com' in url_lower:
        return 'hackernews'
    elif 'x.com' in url_lower or 'twitter.com' in url_lower:
        return 'twitter'
    else:
        return 'forum'


def _is_forum_url(url: str) -> bool:
    """Check if a URL is from a known forum/discussion platform."""
    forum_domains = [
        'reddit.com', 'quora.com', 'stackexchange.com',
        'news.ycombinator.com', 'facebook.com/groups',
        'disqus.com', 'discourse.', 'community.',
    ]
    url_lower = url.lower()
    return any(d in url_lower for d in forum_domains)
