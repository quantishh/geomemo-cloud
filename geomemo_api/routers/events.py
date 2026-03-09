"""
Events endpoints: CRUD for geopolitical events calendar + automated extraction.
"""
import logging
from datetime import date
from typing import List, Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_db_connection

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Groq client (injected from main.py) ---
_groq_client = None


def init_models(groq_client):
    global _groq_client
    _groq_client = groq_client


class EventCreate(BaseModel):
    title: str
    url: Optional[str] = None
    location: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    description: Optional[str] = None
    category: str = "Conference"
    register_url: Optional[str] = None
    is_featured: bool = False


class EventUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    category: Optional[str] = None
    register_url: Optional[str] = None
    is_featured: Optional[bool] = None


class EventResponse(BaseModel):
    id: int
    title: str
    url: Optional[str] = None
    location: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    description: Optional[str] = None
    category: str
    register_url: Optional[str] = None
    is_featured: bool = False
    status: str = "approved"
    source_article_id: Optional[int] = None
    extracted_at: Optional[str] = None
    created_at: Optional[str] = None


EVENT_COLUMNS = """id, title, url, location, start_date, end_date,
                   description, category, register_url,
                   COALESCE(is_featured, FALSE) AS is_featured,
                   COALESCE(status, 'approved') AS status,
                   source_article_id,
                   extracted_at::text,
                   created_at::text"""


@router.get("/events", response_model=List[EventResponse])
def list_events(
    past: bool = Query(False, description="Include past events"),
    status: str = Query("approved", description="Filter by status: approved, pending, rejected, all"),
):
    """List events. Defaults to upcoming approved events only."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        conditions = []
        params = []

        # Status filter
        if status != "all":
            conditions.append("COALESCE(status, 'approved') = %s")
            params.append(status)

        # Date filter
        if not past:
            conditions.append(
                "(start_date >= CURRENT_DATE OR (end_date IS NOT NULL AND end_date >= CURRENT_DATE))"
            )

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cursor.execute(f"""
            SELECT {EVENT_COLUMNS}
            FROM events
            {where}
            ORDER BY start_date ASC
        """, tuple(params))

        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"List events error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/events", response_model=EventResponse)
def create_event(event: EventCreate):
    """Add a new event to the calendar (auto-approved)."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(f"""
            INSERT INTO events (title, url, location, start_date, end_date,
                                description, category, register_url, is_featured, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            RETURNING {EVENT_COLUMNS}
        """, (
            event.title, event.url, event.location,
            event.start_date, event.end_date,
            event.description, event.category,
            event.register_url, event.is_featured,
        ))
        conn.commit()
        return dict(cursor.fetchone())
    except Exception as e:
        conn.rollback()
        logger.error(f"Create event error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.put("/events/{event_id}", response_model=EventResponse)
def update_event(event_id: int, event: EventUpdate):
    """Update an existing event."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # Build dynamic update query
        updates = []
        values = []
        if event.title is not None:
            updates.append("title = %s")
            values.append(event.title)
        if event.url is not None:
            updates.append("url = %s")
            values.append(event.url)
        if event.location is not None:
            updates.append("location = %s")
            values.append(event.location)
        if event.start_date is not None:
            updates.append("start_date = %s")
            values.append(event.start_date)
        if event.end_date is not None:
            updates.append("end_date = %s")
            values.append(event.end_date)
        if event.description is not None:
            updates.append("description = %s")
            values.append(event.description)
        if event.category is not None:
            updates.append("category = %s")
            values.append(event.category)
        if event.register_url is not None:
            updates.append("register_url = %s")
            values.append(event.register_url)
        if event.is_featured is not None:
            updates.append("is_featured = %s")
            values.append(event.is_featured)

        if not updates:
            raise HTTPException(400, "No fields to update")

        values.append(event_id)
        cursor.execute(f"""
            UPDATE events SET {', '.join(updates)}
            WHERE id = %s
            RETURNING {EVENT_COLUMNS}
        """, tuple(values))
        conn.commit()

        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Event not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Update event error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.put("/events/{event_id}/approve", response_model=EventResponse)
def approve_event(event_id: int):
    """Approve a pending event so it appears on the public website."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(f"""
            UPDATE events SET status = 'approved'
            WHERE id = %s
            RETURNING {EVENT_COLUMNS}
        """, (event_id,))
        conn.commit()
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Event not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Approve event error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.put("/events/{event_id}/reject", response_model=EventResponse)
def reject_event(event_id: int):
    """Reject a pending event."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(f"""
            UPDATE events SET status = 'rejected'
            WHERE id = %s
            RETURNING {EVENT_COLUMNS}
        """, (event_id,))
        conn.commit()
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Event not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Reject event error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/events/extract-from-articles")
def extract_events_from_articles(
    min_score: float = Query(65, description="Minimum article auto_approval_score"),
    hours: int = Query(48, description="Look back N hours for articles"),
    limit: int = Query(50, description="Max articles to process"),
):
    """Scan recent articles for event mentions using Groq LLM."""
    if not _groq_client:
        raise HTTPException(500, "Groq client not initialized")

    from services.event_extractor import batch_extract_events
    stats = batch_extract_events(_groq_client, min_score=min_score, hours=hours, limit=limit)
    return stats


@router.delete("/events/{event_id}")
def delete_event(event_id: int):
    """Delete an event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM events WHERE id = %s RETURNING id", (event_id,))
        conn.commit()
        if cursor.fetchone() is None:
            raise HTTPException(404, "Event not found")
        return {"message": "Event deleted", "id": event_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete event error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()
