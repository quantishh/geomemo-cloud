"""
Automated geopolitical event extraction from scraped articles.
Uses Groq Llama 3.3-70B to identify upcoming events mentioned in news articles.
"""
import json
import logging
import time
from datetime import date, datetime

import psycopg2.extras

from database import get_db_connection

logger = logging.getLogger(__name__)

EVENT_EXTRACTION_PROMPT = """You are a geopolitical event extraction specialist for GeoMemo, a geopolitical intelligence platform.

Analyze this news article and extract ANY upcoming or future events explicitly mentioned.

Types of events to extract:
- Summits and high-level meetings (G7, G20, BRICS, ASEAN, EU Council, etc.)
- International conferences and forums (WEF Davos, Munich Security Conference, etc.)
- Elections and referendums (national elections, EU elections, etc.)
- UN sessions and General Assembly meetings
- Trade summits and economic meetings (WTO, APEC, IMF/World Bank meetings)
- Military exercises and defense exhibitions
- Diplomatic meetings, state visits, treaty signings
- Central bank meetings (Fed, ECB, BOJ policy decisions)

For EACH event found, return:
{
  "title": "Official event name (e.g., 'G7 Summit 2026')",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD or null if single-day or unknown",
  "location": "City, Country (or null if not mentioned)",
  "category": "One of: Summit, Conference, Election, UN Session, Trade Summit, Military, Diplomatic, Other",
  "description": "1-2 sentence description of the event and its geopolitical significance"
}

STRICT RULES:
- Only extract events with a SPECIFIC future date mentioned in the article
- Do NOT extract vague references like "later this year" or "in the coming months"
- Do NOT extract events that have already concluded
- Do NOT invent or hallucinate events — only extract what is explicitly stated
- Include the year in all dates (YYYY-MM-DD format)
- If the exact day is unknown but month/year are given, use the 1st of that month
- If no upcoming events are mentioned, return {"events": []}

Return valid JSON: {"events": [...]}"""


def extract_events_from_article(groq_client, article: dict) -> list:
    """
    Extract structured event data from a single article using Groq LLM.
    Returns a list of event dicts (may be empty).
    """
    headline = article.get("headline_en") or article.get("headline") or ""
    summary = article.get("summary") or ""
    summary_long = article.get("summary_long") or ""

    content = f"Headline: {headline}\nSummary: {summary}"
    if summary_long:
        content += f"\nDetailed Summary: {summary_long}"

    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": EVENT_EXTRACTION_PROMPT},
                {"role": "user", "content": content},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        events = result.get("events", [])

        # Validate each event has required fields
        valid_events = []
        for ev in events:
            if not ev.get("title") or not ev.get("start_date"):
                continue
            # Validate date format
            try:
                datetime.strptime(ev["start_date"], "%Y-%m-%d")
                if ev.get("end_date"):
                    datetime.strptime(ev["end_date"], "%Y-%m-%d")
            except ValueError:
                logger.warning(f"Skipping event with invalid date: {ev}")
                continue
            valid_events.append(ev)

        return valid_events

    except Exception as e:
        logger.error(f"Groq event extraction error for article {article.get('id')}: {e}")
        return []


def _is_duplicate_event(cursor, title: str, start_date: str) -> bool:
    """
    Check if a similar event already exists.
    Matches on same start_date + case-insensitive title overlap.
    Extracts key proper nouns (capitalized multi-word phrases) from the title
    and checks if existing events contain them.
    """
    # Extract significant words (3+ chars, skip common words)
    skip_words = {
        "the", "and", "for", "summit", "conference", "meeting", "session",
        "annual", "world", "global", "international", "2024", "2025", "2026",
        "2027", "day", "week", "forum",
    }
    words = [w for w in title.split() if len(w) >= 3 and w.lower() not in skip_words]

    if not words:
        # Fallback: exact title match on same date
        cursor.execute(
            "SELECT 1 FROM events WHERE start_date = %s AND LOWER(title) = LOWER(%s) LIMIT 1",
            (start_date, title),
        )
        return cursor.fetchone() is not None

    # Check if any existing event on the same date contains at least 2 key words
    # (or 1 if the title only has 1 significant word)
    min_matches = min(2, len(words))
    cursor.execute(
        "SELECT title FROM events WHERE start_date = %s AND status != 'rejected'",
        (start_date,),
    )
    existing = cursor.fetchall()

    for (existing_title,) in existing:
        existing_lower = existing_title.lower()
        matches = sum(1 for w in words if w.lower() in existing_lower)
        if matches >= min_matches:
            return True

    return False


def batch_extract_events(groq_client, min_score: float = 65, hours: int = 48, limit: int = 50) -> dict:
    """
    Scan recent articles for event mentions and insert extracted events as 'pending'.
    Returns stats dict.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    stats = {
        "articles_processed": 0,
        "events_found": 0,
        "events_inserted": 0,
        "duplicates_skipped": 0,
        "errors": 0,
    }

    try:
        # Find articles not yet processed for events
        cursor.execute("""
            SELECT id, headline, headline_en, summary, summary_long, category, url
            FROM articles
            WHERE (events_extracted IS NOT TRUE)
              AND auto_approval_score >= %s
              AND scraped_at >= NOW() - make_interval(hours => %s)
              AND status = 'approved'
            ORDER BY auto_approval_score DESC
            LIMIT %s
        """, (min_score, hours, limit))

        articles = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Event extraction: found {len(articles)} unprocessed articles")

        for article in articles:
            try:
                events = extract_events_from_article(groq_client, article)
                stats["articles_processed"] += 1
                stats["events_found"] += len(events)

                for ev in events:
                    # Skip past events
                    try:
                        event_date = datetime.strptime(ev["start_date"], "%Y-%m-%d").date()
                        if event_date < date.today():
                            continue
                    except ValueError:
                        continue

                    # Dedup check
                    if _is_duplicate_event(cursor, ev["title"], ev["start_date"]):
                        stats["duplicates_skipped"] += 1
                        logger.debug(f"Duplicate event skipped: {ev['title']} on {ev['start_date']}")
                        continue

                    # Insert as pending
                    cursor.execute("""
                        INSERT INTO events (title, url, location, start_date, end_date,
                                            description, category, status, source_article_id, extracted_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, NOW())
                        RETURNING id
                    """, (
                        ev["title"],
                        article.get("url"),
                        ev.get("location"),
                        ev["start_date"],
                        ev.get("end_date"),
                        ev.get("description"),
                        ev.get("category", "Conference"),
                        article["id"],
                    ))
                    conn.commit()
                    stats["events_inserted"] += 1
                    logger.info(f"Extracted event: {ev['title']} ({ev['start_date']})")

                # Mark article as processed
                cursor.execute(
                    "UPDATE articles SET events_extracted = TRUE WHERE id = %s",
                    (article["id"],),
                )
                conn.commit()

                # Rate limit: 2 second pause between Groq calls
                time.sleep(2)

            except Exception as e:
                conn.rollback()
                stats["errors"] += 1
                logger.error(f"Error extracting events from article {article['id']}: {e}")

        logger.info(f"Event extraction complete: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Batch event extraction error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
