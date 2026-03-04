"""
Content generation for social media posts.
Template-based formatting per platform — no Groq calls for speed.
Uses existing article data (headline_en, summary, category, etc.).
"""
import re
import logging

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
# TWITTER/X (280 char limit) — Ready for Phase 2
# ============================================================

def generate_breaking_tweet(article: dict) -> str:
    """
    Generate a tweet for a breaking news article.
    280 char limit. URL counts as 23 chars (t.co wrapping).
    """
    headline = _strip_html(article.get('headline_en') or article.get('headline') or 'Breaking')
    url = article.get('url') or ''
    category = article.get('category') or ''
    countries = article.get('country_codes') or []

    emoji = CATEGORY_EMOJI.get(category, '🔴')
    tags = '#GeoMemo'
    if countries:
        tags += f' #{countries[0]}'

    prefix = f"{emoji} BREAKING: "
    suffix = f"\n\n{url}\n\n{tags}"
    # t.co URL = 23 chars; leave buffer
    max_headline = 280 - len(prefix) - 23 - len(f"\n\n\n\n{tags}") - 5
    if len(headline) > max_headline:
        headline = headline[:max_headline - 3] + '...'

    return f"{prefix}{headline}{suffix}"


def generate_newsletter_thread(brief: dict, articles: list) -> list:
    """
    Generate a Twitter thread (list of tweets) for the daily newsletter.
    Returns list of strings, each <= 280 chars.
    Kept to 3-4 tweets to conserve the 100 posts/month Basic tier quota.
    """
    date_str = str(brief.get('date', ''))
    subject = _strip_html(brief.get('subject_line') or 'Daily Intelligence')

    top_stories = [a for a in articles if a.get('is_top_story') and not a.get('parent_id')]
    other_stories = [a for a in articles if not a.get('is_top_story') and not a.get('parent_id')]

    thread = []

    # Tweet 1: Intro
    intro = f"🌐 GeoMemo Daily Intelligence — {date_str}\n\n{subject[:200]}\n\n🧵 Thread 👇"
    thread.append(intro[:280])

    # Tweets 2-3: Top stories
    for a in (top_stories + other_stories)[:2]:
        headline = _strip_html(a.get('headline_en') or a.get('headline') or '')
        url = a.get('url') or ''
        source = a.get('publication_name') or ''
        category = a.get('category') or ''
        emoji = CATEGORY_EMOJI.get(category, '📰')

        tweet = f"{emoji} {headline[:180]}"
        if source:
            tweet += f"\n\n— {source}"
        tweet += f"\n{url}"
        thread.append(tweet[:280])

    # Closing tweet
    closing = ("📩 Get the full daily brief: geomemo.news\n\n"
               "Subscribe for free — intelligence for decision makers.\n\n"
               "#Geopolitics #GeoMemo #DailyBrief")
    thread.append(closing[:280])

    return thread
