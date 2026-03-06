"""
Source management endpoints — track and score news sources.
Includes Google News Intelligence Builder (AI-powered feed generation).
"""
import json
import logging
import urllib.parse
from typing import List

import requests as http_requests
import psycopg2.extras
from fastapi import APIRouter, HTTPException
from groq import Groq

from database import get_db_connection
from models import (
    Source, SourceUpdate, SourceCreate,
    GoogleFeedGenerateRequest, GoogleFeedGenerateResponse, GeneratedFeed,
    FeedPreviewRequest, FeedPreviewResponse, FeedPreviewHeadline,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sources", tags=["sources"])

# Groq client injected from main.py (same pattern as articles.py/newsletter.py)
groq_client: Groq = None


def init_models(groq: Groq):
    """Called from main.py to inject the shared Groq client."""
    global groq_client
    groq_client = groq


@router.get("", response_model=List[Source])
def list_sources():
    """List all news sources with credibility scores."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id, name, domain, credibility_score, tier, country, language,
                   total_articles, approved_count, rejected_count,
                   rss_feed_url, twitter_handle
            FROM sources
            ORDER BY total_articles DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


@router.put("/{source_id}")
def update_source(source_id: int, update: SourceUpdate):
    """Update a source's credibility score, tier, country, or language."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sets = []
        params = []
        if update.credibility_score is not None:
            sets.append("credibility_score = %s")
            params.append(update.credibility_score)
        if update.tier is not None:
            sets.append("tier = %s")
            params.append(update.tier)
        if update.country is not None:
            sets.append("country = %s")
            params.append(update.country)
        if update.language is not None:
            sets.append("language = %s")
            params.append(update.language)
        if update.rss_feed_url is not None:
            sets.append("rss_feed_url = %s")
            params.append(update.rss_feed_url)
        if update.twitter_handle is not None:
            sets.append("twitter_handle = %s")
            params.append(update.twitter_handle)
        if not sets:
            raise HTTPException(400, "No fields to update")
        params.append(source_id)
        cursor.execute(f"UPDATE sources SET {', '.join(sets)} WHERE id = %s", tuple(params))
        conn.commit()
        return {"message": "Source updated"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.post("/seed")
def seed_sources():
    """Auto-populate sources table from existing article publication_names."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Insert distinct publication names that don't already exist
        cursor.execute("""
            INSERT INTO sources (name)
            SELECT DISTINCT publication_name
            FROM articles
            WHERE publication_name IS NOT NULL
              AND publication_name != ''
              AND publication_name NOT IN (SELECT name FROM sources)
            ORDER BY publication_name
        """)
        inserted = cursor.rowcount

        # Update total_articles and approved/rejected counts
        cursor.execute("""
            UPDATE sources s SET
                total_articles = sub.total,
                approved_count = sub.approved,
                rejected_count = sub.rejected
            FROM (
                SELECT publication_name,
                       COUNT(*) as total,
                       COUNT(*) FILTER (WHERE status = 'approved') as approved,
                       COUNT(*) FILTER (WHERE status = 'rejected') as rejected
                FROM articles
                WHERE publication_name IS NOT NULL
                GROUP BY publication_name
            ) sub
            WHERE s.name = sub.publication_name
        """)

        # Backfill source_id on articles
        cursor.execute("""
            UPDATE articles a SET source_id = s.id
            FROM sources s
            WHERE a.publication_name = s.name
              AND a.source_id IS NULL
        """)
        backfilled = cursor.rowcount

        conn.commit()
        return {
            "message": f"Seeded {inserted} new sources, backfilled {backfilled} articles",
            "new_sources": inserted,
            "articles_linked": backfilled,
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"Seed error: {e}")
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.post("/recalculate")
def recalculate_source_scores():
    """Recalculate credibility scores based on approve/reject history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Update counts
        cursor.execute("""
            UPDATE sources s SET
                total_articles = sub.total,
                approved_count = sub.approved,
                rejected_count = sub.rejected
            FROM (
                SELECT publication_name,
                       COUNT(*) as total,
                       COUNT(*) FILTER (WHERE status = 'approved') as approved,
                       COUNT(*) FILTER (WHERE status = 'rejected') as rejected
                FROM articles
                WHERE publication_name IS NOT NULL
                GROUP BY publication_name
            ) sub
            WHERE s.name = sub.publication_name
        """)

        # Auto-calculate credibility based on approval rate
        # Score = base 50, adjusted by approval ratio (0-100)
        # Only adjust if source has 10+ articles reviewed
        cursor.execute("""
            UPDATE sources SET
                credibility_score = LEAST(100, GREATEST(10,
                    CASE
                        WHEN (approved_count + rejected_count) >= 10
                        THEN ROUND(100.0 * approved_count / NULLIF(approved_count + rejected_count, 0))
                        ELSE credibility_score
                    END
                ))
            WHERE total_articles > 0
        """)
        updated = cursor.rowcount
        conn.commit()
        return {"message": f"Recalculated scores for {updated} sources"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


# --- M2: Source CRUD ---

@router.post("", status_code=201)
def create_source(source: SourceCreate):
    """Create a new source manually."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO sources (name, domain, credibility_score, tier, country, language,
                                    rss_feed_url, twitter_handle)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (source.name, source.domain, source.credibility_score,
             source.tier, source.country, source.language,
             source.rss_feed_url, source.twitter_handle)
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        return {"message": "Source created", "id": new_id}
    except Exception as e:
        conn.rollback()
        if "duplicate key" in str(e).lower():
            raise HTTPException(409, f"Source '{source.name}' already exists")
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.delete("/{source_id}")
def delete_source(source_id: int):
    """Delete a source. Nullifies source_id on linked articles first."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Nullify source_id on articles first
        cursor.execute("UPDATE articles SET source_id = NULL WHERE source_id = %s", (source_id,))
        cursor.execute("DELETE FROM sources WHERE id = %s", (source_id,))
        if cursor.rowcount == 0:
            raise HTTPException(404, "Source not found")
        conn.commit()
        return {"message": "Source deleted"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


# =========================================
# GOOGLE NEWS INTELLIGENCE BUILDER
# =========================================

@router.post("/generate-google-feeds", response_model=GoogleFeedGenerateResponse)
def generate_google_feeds(request: GoogleFeedGenerateRequest):
    """Use AI to generate optimized Google News RSS search URLs from a natural language description."""
    if not groq_client:
        raise HTTPException(503, "AI service not available")

    region_hint = f"\nRegional focus: {request.region}" if request.region else ""
    focus_hint = f"\nSubject focus: {request.focus}" if request.focus else ""
    freshness = request.freshness or "1d"

    system_prompt = """You are a Google News search expert for a geopolitical intelligence platform called GeoMemo.
Your job is to generate optimized Google News RSS search queries using Boolean operators.

Rules for query construction:
- Use AND to require multiple concepts appear together
- Use OR to capture synonyms/alternatives (group with parentheses)
- Use quotes for exact phrases: "supply chain"
- Keep queries specific enough to avoid noise but broad enough to catch relevant stories
- Prioritize geopolitical, economic, and market-impact angles
- Each query should target a slightly different angle of the same topic
- Use + instead of spaces between words within the query

Return a JSON object with a "feeds" array containing exactly 3 objects, each with:
- "label": Short human-readable name (2-5 words)
- "query": The Boolean query string (WITHOUT when:Xd — that gets added automatically). Use + for spaces.
- "rationale": One sentence explaining what this query captures"""

    user_prompt = f"""Generate 3 Google News search queries for:
"{request.description}"{region_hint}{focus_hint}

The queries should cover different angles: one broad, one focused on economic/market impact, and one focused on key actors/policy."""

    try:
        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = json.loads(chat.choices[0].message.content)
        feeds = []
        for f in raw.get("feeds", []):
            query = f.get("query", "")
            full_query = f"{query}+when:{freshness}"
            rss_url = f"https://news.google.com/rss/search?q={full_query}&hl=en-US&gl=US&ceid=US:en"
            feeds.append(GeneratedFeed(
                label=f.get("label", "Unnamed Feed"),
                query=query,
                rss_url=rss_url,
                rationale=f.get("rationale", ""),
            ))
        return GoogleFeedGenerateResponse(feeds=feeds)
    except Exception as e:
        logger.error(f"Google feed generation error: {e}")
        raise HTTPException(500, f"AI generation failed: {e}")


@router.post("/preview-feed", response_model=FeedPreviewResponse)
def preview_feed(request: FeedPreviewRequest):
    """Fetch an RSS URL and return sample headlines for preview."""
    try:
        resp = http_requests.get(request.rss_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; GeoMemo/1.0)'
        })
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch feed: {e}")

    try:
        from lxml import etree
        root = etree.fromstring(resp.content)
        items = root.findall('.//item')
        feed_title = root.findtext('.//channel/title', default=None)

        headlines = []
        for item in items[:5]:
            title = item.findtext('title', default='').strip()
            source_el = item.find('source')
            source_name = source_el.text.strip() if source_el is not None and source_el.text else None
            link = item.findtext('link', default='').strip()
            pub_date = item.findtext('pubDate', default='').strip()
            if title:
                headlines.append(FeedPreviewHeadline(
                    title=title,
                    source=source_name,
                    url=link,
                    published=pub_date,
                ))
        return FeedPreviewResponse(
            headlines=headlines,
            total_items=len(items),
            feed_title=feed_title,
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to parse RSS feed: {e}")


@router.post("/migrate-google-feeds")
def migrate_hardcoded_google_feeds():
    """One-time migration: move hardcoded Google News RSS feeds into the sources DB."""
    hardcoded_feeds = [
        ("GNews: Geopolitics", "https://news.google.com/rss/search?q=geopolitics+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: International Relations", "https://news.google.com/rss/search?q=international+relations+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: Global Economy", "https://news.google.com/rss/search?q=global+economy+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: World Conflict", "https://news.google.com/rss/search?q=world+conflict+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: Foreign Policy", "https://news.google.com/rss/search?q=foreign+policy+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: Geopolitical Conflict + Trade", "https://news.google.com/rss/search?q=(geopolitical+conflict+OR+war+OR+sanctions+OR+embargo)+AND+(trade+OR+%22market+impact%22+OR+%22supply+chain%22+OR+financial+impact)+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: Climate + Geopolitics", "https://news.google.com/rss/search?q=(%22climate+change%22+OR+%22natural+disaster%22+OR+drought+OR+flood)+AND+(geopolitics+OR+%22economic+impact%22+OR+%22resource+scarcity%22+OR+migration)+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: Stock Markets Outlook", "https://news.google.com/rss/search?q=(%22stock+market%22+OR+%22major+indices%22+OR+Sensex+OR+Nifty+OR+Nikkei+OR+%22Hang+Seng%22+OR+FTSE+OR+DAX+OR+%22ASX+200%22+OR+Bovespa+OR+JSE)+AND+(forecast+OR+performance+OR+outlook)+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: AI + Labor + Geopolitics", "https://news.google.com/rss/search?q=(AI+OR+%22Artificial+Intelligence%22)+AND+(labor+OR+displacement+OR+unemployment+OR+%22economic+revolution%22+OR+regulation)+AND+(geopolitics+OR+global)+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: Global Economy by Region", "https://news.google.com/rss/search?q=(%22global+economy%22+OR+GDP+OR+recession+OR+inflation+OR+%22central+bank%22)+AND+(Asia+OR+India+OR+Europe+OR+%22South+America%22+OR+Africa+OR+Australia)+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: US Foreign Policy", "https://news.google.com/rss/search?q=(%22foreign+policy%22+OR+%22international+relations%22+OR+diplomacy)+AND+(%22United+States%22+OR+US)+AND+(impact+OR+implication+OR+effect)+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: Think Tank Analysis", "https://news.google.com/rss/search?q=(%22think+tank%22+OR+%22policy+brief%22+OR+%22strategic+analysis%22)+AND+(geopolitics+OR+global)+when:1d&hl=en-US&gl=US&ceid=US:en"),
        ("GNews: Americas Market Indices", "https://news.google.com/rss/search?q=(%22S%26P+500%22+OR+Nasdaq+OR+%22Dow+Jones%22+OR+%22Russell+2000%22+OR+%22TSX+Composite%22)+AND+(forecast+OR+performance+OR+outlook)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ]

    conn = get_db_connection()
    cursor = conn.cursor()
    migrated = 0
    skipped = 0
    try:
        for name, url in hardcoded_feeds:
            cursor.execute(
                """INSERT INTO sources (name, domain, credibility_score, tier, country, language, rss_feed_url)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (name) DO NOTHING""",
                (name, "news.google.com", 50, 2, "Global", "en", url)
            )
            if cursor.rowcount > 0:
                migrated += 1
            else:
                skipped += 1
        conn.commit()
        return {
            "message": f"Migrated {migrated} Google News feeds, skipped {skipped} (already exist)",
            "migrated": migrated,
            "skipped": skipped,
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()
