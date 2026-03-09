"""
Google Custom Search event discovery for GeoMemo.
Uses Google Custom Search JSON API to find geopolitical events,
then Groq LLM to extract structured event data.
Events are inserted as 'pending' for admin review.
"""
import json
import logging
import time
from datetime import date, datetime

import psycopg2.extras
import requests

from config import GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX
from database import get_db_connection

logger = logging.getLogger(__name__)

SEARCH_EVENT_PROMPT = """You are a geopolitical event extraction specialist for GeoMemo.

Below are Google search results for the query: "{query}"

Analyze EVERY result and extract ALL upcoming or future geopolitical events with specific dates.

Types of events to extract:
- Summits (G7, G20, BRICS, ASEAN, EU Council, NATO, etc.)
- International conferences and forums (WEF, Munich Security Conference, etc.)
- Elections and referendums
- UN sessions and General Assembly meetings
- Trade summits and economic meetings (WTO, APEC, IMF/World Bank)
- Military exercises and defense exhibitions
- Diplomatic meetings, state visits, treaty signings
- Central bank meetings (Fed, ECB, BOJ policy decisions)

For EACH event found, return:
{{
  "title": "Official event name (e.g., 'G7 Summit 2026')",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD or null if single-day or unknown",
  "location": "City, Country (or null if not mentioned)",
  "category": "Summit|Conference|Election|UN Session|Trade Summit|Military|Diplomatic|Other",
  "description": "1-2 sentence description of the event and its geopolitical significance",
  "url": "URL of the event page if available, or null"
}}

STRICT RULES:
- Only extract events with a SPECIFIC date (at least month + year)
- If only month/year is known, use the 1st of that month
- Do NOT extract past events
- Do NOT invent events — only extract what is explicitly stated in the search results
- Today's date is {today}. Only extract events on or after this date.
- If no events found, return {{"events": []}}

Return valid JSON: {{"events": [...]}}"""


def _google_custom_search(query: str, num_pages: int = 5) -> list:
    """
    Fetch Google search results via Custom Search JSON API.
    Each API call returns 10 results. num_pages controls how many calls (1-5).
    Free tier: 100 queries/day.
    Returns list of {title, snippet, url} dicts.
    """
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        logger.error("Google CSE API key or CX not configured")
        return []

    results = []
    # Custom Search API uses 1-indexed start param (1, 11, 21, ...)
    for page in range(num_pages):
        start = page * 10 + 1

        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": GOOGLE_CSE_API_KEY,
                    "cx": GOOGLE_CSE_CX,
                    "q": query,
                    "start": start,
                },
                timeout=15,
            )

            if resp.status_code == 429:
                logger.warning("Google CSE rate limit reached (100 queries/day)")
                break
            if resp.status_code != 200:
                logger.warning(f"Google CSE page {page+1} returned {resp.status_code}: {resp.text[:200]}")
                break

            data = resp.json()
            items = data.get("items", [])

            if not items:
                logger.info(f"Google CSE page {page+1}: no more results")
                break

            for item in items:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                })

            logger.info(f"Google CSE page {page+1}: {len(items)} results (total: {len(results)})")

        except Exception as e:
            logger.error(f"Google CSE page {page+1} error: {e}")
            break

    return results


def _extract_events_from_search_results(groq_client, results: list, query: str) -> list:
    """
    Use Groq LLM to extract structured events from search results.
    """
    if not results:
        return []

    # Format results for the LLM
    formatted = []
    for i, r in enumerate(results, 1):
        line = f"{i}. [{r['title']}]({r['url']})"
        if r.get("snippet"):
            line += f"\n   {r['snippet']}"
        formatted.append(line)

    results_text = "\n\n".join(formatted)

    prompt = SEARCH_EVENT_PROMPT.format(
        query=query,
        today=date.today().isoformat(),
    )

    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Search results:\n\n{results_text}"},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        events = result.get("events", [])

        # Validate each event
        valid = []
        for ev in events:
            if not ev.get("title") or not ev.get("start_date"):
                continue
            try:
                event_date = datetime.strptime(ev["start_date"], "%Y-%m-%d").date()
                if event_date < date.today():
                    continue
                if ev.get("end_date"):
                    datetime.strptime(ev["end_date"], "%Y-%m-%d")
            except ValueError:
                continue
            valid.append(ev)

        return valid

    except Exception as e:
        logger.error(f"Groq event extraction from search results error: {e}")
        return []


def _is_duplicate_event(cursor, title: str, start_date: str) -> bool:
    """Check if a similar event already exists (reuses logic from event_extractor.py)."""
    skip_words = {
        "the", "and", "for", "summit", "conference", "meeting", "session",
        "annual", "world", "global", "international", "2024", "2025", "2026",
        "2027", "day", "week", "forum",
    }
    words = [w for w in title.split() if len(w) >= 3 and w.lower() not in skip_words]

    if not words:
        cursor.execute(
            "SELECT 1 FROM events WHERE start_date = %s AND LOWER(title) = LOWER(%s) LIMIT 1",
            (start_date, title),
        )
        return cursor.fetchone() is not None

    min_matches = min(2, len(words))
    cursor.execute(
        "SELECT title FROM events WHERE start_date = %s AND status != 'rejected'",
        (start_date,),
    )
    for (existing_title,) in cursor.fetchall():
        existing_lower = existing_title.lower()
        matches = sum(1 for w in words if w.lower() in existing_lower)
        if matches >= min_matches:
            return True

    return False


def search_and_extract_events(groq_client, query: str, num_pages: int = 5) -> dict:
    """
    Full pipeline: Google CSE API → LLM extract → dedup → insert as pending.
    """
    stats = {
        "query": query,
        "results_scraped": 0,
        "events_found": 0,
        "events_inserted": 0,
        "duplicates_skipped": 0,
        "errors": 0,
    }

    # 1. Google Custom Search API
    results = _google_custom_search(query, num_pages)
    stats["results_scraped"] = len(results)

    if not results:
        logger.warning(f"No Google search results for: {query}")
        return stats

    # 2. Extract events via LLM
    events = _extract_events_from_search_results(groq_client, results, query)
    stats["events_found"] = len(events)

    if not events:
        return stats

    # 3. Dedup and insert
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for ev in events:
            if _is_duplicate_event(cursor, ev["title"], ev["start_date"]):
                stats["duplicates_skipped"] += 1
                continue

            cursor.execute("""
                INSERT INTO events (title, url, location, start_date, end_date,
                                    description, category, status, source_query, extracted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, NOW())
                RETURNING id
            """, (
                ev["title"],
                ev.get("url"),
                ev.get("location"),
                ev["start_date"],
                ev.get("end_date"),
                ev.get("description"),
                ev.get("category", "Conference"),
                query,
            ))
            conn.commit()
            stats["events_inserted"] += 1
            logger.info(f"Search event extracted: {ev['title']} ({ev['start_date']})")

    except Exception as e:
        conn.rollback()
        stats["errors"] += 1
        logger.error(f"Event insert error: {e}")
    finally:
        cursor.close()
        conn.close()

    logger.info(f"Google search event extraction complete: {stats}")
    return stats


def run_saved_searches(groq_client) -> dict:
    """
    Run all active saved search queries and return aggregate stats.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    aggregate = {
        "queries_run": 0,
        "total_results_scraped": 0,
        "total_events_found": 0,
        "total_events_inserted": 0,
        "total_duplicates_skipped": 0,
        "errors": 0,
    }

    try:
        cursor.execute(
            "SELECT id, query FROM event_search_queries WHERE is_active = TRUE ORDER BY id"
        )
        queries = cursor.fetchall()
        cursor.close()
        conn.close()

        for q in queries:
            stats = search_and_extract_events(groq_client, q["query"], num_pages=5)
            aggregate["queries_run"] += 1
            aggregate["total_results_scraped"] += stats["results_scraped"]
            aggregate["total_events_found"] += stats["events_found"]
            aggregate["total_events_inserted"] += stats["events_inserted"]
            aggregate["total_duplicates_skipped"] += stats["duplicates_skipped"]

            # Update last_run_at and events_found
            conn2 = get_db_connection()
            cur2 = conn2.cursor()
            cur2.execute(
                "UPDATE event_search_queries SET last_run_at = NOW(), events_found = %s WHERE id = %s",
                (stats["events_found"], q["id"]),
            )
            conn2.commit()
            cur2.close()
            conn2.close()

            # Rate limit between queries
            time.sleep(2)

    except Exception as e:
        aggregate["errors"] += 1
        logger.error(f"Run saved searches error: {e}")

    logger.info(f"Saved searches complete: {aggregate}")
    return aggregate
