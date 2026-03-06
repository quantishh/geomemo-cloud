"""
Content generation for social media posts.
Template-based formatting per platform — no Groq calls for speed.
Uses existing article data (headline_en, summary, category, etc.).
"""
import re
import logging

from database import get_db_connection

logger = logging.getLogger(__name__)

# Category → emoji mapping (shared across platforms)
CATEGORY_EMOJI = {
    'Geopolitical Conflict': '🔴',
    'Geopolitical Economics': '📊',
    'Global Markets': '📈',
    'Geopolitical Politics': '🏛️',
    'GeoNatDisaster': '🌍',
    'GeoLocal': '📍',
    'Other': '📰',
}

# Publication name → X handle mapping for source attribution in tweets.
# Static lookup — no DB change needed. Expand as needed.
SOURCE_X_HANDLES = {
    'Reuters': '@Reuters',
    'Bloomberg': '@business',
    'The New York Times': '@nytimes',
    'The Washington Post': '@washingtonpost',
    'Financial Times': '@FT',
    'The Wall Street Journal': '@WSJ',
    'BBC': '@BBCWorld',
    'BBC News': '@BBCWorld',
    'Al Jazeera': '@AJEnglish',
    'CNN': '@CNN',
    'CNBC': '@CNBC',
    'The Guardian': '@guardian',
    'The Economist': '@TheEconomist',
    'Associated Press': '@AP',
    'AP News': '@AP',
    'AFP': '@AFP',
    'Politico': '@POLITICOEurope',
    'Foreign Policy': '@ForeignPolicy',
    'Foreign Affairs': '@ForeignAffairs',
    'South China Morning Post': '@SCMPNews',
    'Nikkei Asia': '@NikkeiAsia',
    'The Times of India': '@timesofindia',
    'Hindustan Times': '@htTweets',
    'France24': '@FRANCE24',
    'Sky News': '@SkyNews',
    'NBC News': '@NBCNews',
    'ABC News': '@ABC',
    'Fox News': '@FoxNews',
    'NPR': '@NPR',
    'Axios': '@axios',
    'The Hill': '@thehill',
    'Defense One': '@DefenseOne',
    'Middle East Eye': '@MiddleEastEye',
    'The Japan Times': '@japantimes',
    'Xinhua': '@XHNews',
}


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]*>', '', text or '')


def _escape_html(text: str) -> str:
    """Escape HTML special chars for Telegram HTML parse mode."""
    return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ============================================================
# TELEGRAM (HTML parse mode, max 4096 chars)
# ============================================================

def generate_breaking_telegram(article: dict) -> str:
    """
    Generate a Telegram breaking news message from an article.
    Template-based for speed — no LLM call.
    Target: 200-500 chars for readability.
    """
    headline = _escape_html(article.get('headline_en') or article.get('headline') or 'Breaking')
    summary = _escape_html(_strip_html(article.get('summary') or ''))
    category = article.get('category') or 'Geopolitical'
    url = article.get('url') or ''
    source = _escape_html(article.get('publication_name') or '')
    countries = article.get('country_codes') or []

    emoji = CATEGORY_EMOJI.get(category, '📰')
    country_tags = ' '.join(f'#{c}' for c in countries[:3]) if countries else ''

    parts = [
        f"{emoji} <b>BREAKING</b> | {_escape_html(category)}",
        "",
        f"<b>{headline}</b>",
        "",
        summary[:500],
        "",
    ]
    if source:
        parts.append(f"📰 {source}")
    if country_tags:
        parts.append(country_tags)
    if url:
        parts.append(f'\n<a href="{url}">Read full article</a>')
    parts.append("\n#GeoMemo #Geopolitics")

    return '\n'.join(parts)


def generate_newsletter_telegram(brief: dict, articles: list) -> str:
    """
    Generate a Telegram newsletter digest message.
    Uses existing daily_briefs.summary_text — no extra Groq call.
    Max 4096 chars (Telegram limit).
    """
    brief_text = _strip_html(brief.get('summary_text') or '')
    subject = _escape_html(brief.get('subject_line') or 'Daily Intelligence')
    date_str = str(brief.get('date', ''))

    top_stories = [a for a in articles if a.get('is_top_story') and not a.get('parent_id')]
    other_stories = [a for a in articles if not a.get('is_top_story') and not a.get('parent_id')]

    parts = [
        "🌐 <b>GeoMemo Daily Intelligence</b>",
        f"📅 {_escape_html(date_str)}",
        "",
        f"<b>{subject}</b>",
        "",
    ]

    if brief_text:
        truncated = _escape_html(brief_text[:1500] if len(brief_text) > 1500 else brief_text)
        parts.append(truncated)
        parts.append("")

    if top_stories:
        parts.append("🔴 <b>Top Stories</b>")
        for a in top_stories[:5]:
            headline = _escape_html(_strip_html(a.get('headline_en') or a.get('headline') or ''))
            url = a.get('url') or ''
            parts.append(f'• <a href="{url}">{headline[:120]}</a>')
        parts.append("")

    if other_stories:
        parts.append("📰 <b>Also Today</b>")
        for a in other_stories[:8]:
            headline = _escape_html(_strip_html(a.get('headline_en') or a.get('headline') or ''))
            url = a.get('url') or ''
            parts.append(f'• <a href="{url}">{headline[:100]}</a>')

    parts.append("")
    parts.append("📩 Subscribe: geomemo.news")
    parts.append("#GeoMemo #DailyBrief #Geopolitics")

    result = '\n'.join(parts)
    if len(result) > 4096:
        result = result[:4090] + "\n..."

    return result


# ============================================================
# TWITTER/X (280 char limit)
# IMPORTANT: No external links (X penalizes 30-50% reach).
#            No hashtags (X deprioritizes them).
#            Use summary, not headline. Add source attribution + CTA.
# ============================================================

# CTA line for all tweets (no links — X penalizes them)
TWEET_CTA = '🌐 Follow @GeoMemoNews for daily geopolitical intel'


def _get_source_attribution(publication_name: str) -> str:
    """Get source attribution with X handle if known, otherwise plain name.
    Checks database first for twitter_handle, falls back to hardcoded dict.
    """
    if not publication_name:
        return ''
    # Try database lookup first
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT twitter_handle FROM sources WHERE name = %s AND twitter_handle IS NOT NULL",
            (publication_name,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row and row[0]:
            return f'— via {row[0]}'
    except Exception as e:
        logger.debug(f"DB twitter_handle lookup failed for {publication_name}: {e}")
    # Fall back to hardcoded dict
    handle = SOURCE_X_HANDLES.get(publication_name)
    if handle:
        return f'— via {handle}'
    return f'— via {publication_name}'


def generate_breaking_tweet(article: dict) -> str:
    """
    Generate a tweet for a news article.
    280 char limit. No external links. No hashtags.
    Uses article summary (50-word) for richer content than just a headline.
    Format:
        📊 [summary text]
        — via @SourceHandle
        🌐 Follow @GeoMemoNews for daily geopolitical intel
    """
    summary = _strip_html(article.get('summary') or '')
    headline = _strip_html(article.get('headline_en') or article.get('headline') or '')
    category = article.get('category') or ''
    source = article.get('publication_name') or ''

    emoji = CATEGORY_EMOJI.get(category, '📰')
    attribution = _get_source_attribution(source)

    # Build the fixed footer
    footer_parts = []
    if attribution:
        footer_parts.append(attribution)
    footer_parts.append(TWEET_CTA)
    footer = '\n\n'.join(footer_parts)

    # Calculate max content length
    prefix = f"{emoji} "
    max_content = 280 - len(prefix) - len(f"\n\n{footer}") - 2

    # Prefer summary over headline for richer content
    content = summary if summary else headline
    if len(content) > max_content:
        content = content[:max_content - 3].rsplit(' ', 1)[0] + '...'

    return f"{prefix}{content}\n\n{footer}"


def generate_newsletter_thread(brief: dict, articles: list) -> list:
    """
    Generate a Twitter thread (list of tweets) for the daily newsletter.
    Returns list of strings, each <= 280 chars.
    No external links. No hashtags. Uses source attribution.
    """
    date_str = str(brief.get('date', ''))
    subject = _strip_html(brief.get('subject_line') or 'Daily Intelligence')

    top_stories = [a for a in articles if a.get('is_top_story') and not a.get('parent_id')]
    other_stories = [a for a in articles if not a.get('is_top_story') and not a.get('parent_id')]

    thread = []

    # Tweet 1: Intro
    intro = f"🌐 GeoMemo Daily Intelligence — {date_str}\n\n{subject[:200]}\n\n🧵 Thread 👇"
    thread.append(intro[:280])

    # Tweets 2-3: Top stories (summary-based, no links)
    for a in (top_stories + other_stories)[:2]:
        summary = _strip_html(a.get('summary') or a.get('headline_en') or a.get('headline') or '')
        source = a.get('publication_name') or ''
        category = a.get('category') or ''
        emoji = CATEGORY_EMOJI.get(category, '📰')
        attribution = _get_source_attribution(source)

        tweet = f"{emoji} {summary[:200]}"
        if attribution:
            tweet += f"\n\n{attribution}"
        thread.append(tweet[:280])

    # Closing tweet (no links, no hashtags)
    closing = (f"📩 Follow @GeoMemoNews for the full daily brief\n\n"
               f"Geopolitical intelligence for investors, policymakers and decision-makers")
    thread.append(closing[:280])

    return thread
