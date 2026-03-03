"""
Source management endpoints — track and score news sources.
"""
import logging
from typing import List

import psycopg2.extras
from fastapi import APIRouter, HTTPException

from database import get_db_connection
from models import Source, SourceUpdate, SourceCreate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=List[Source])
def list_sources():
    """List all news sources with credibility scores."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id, name, domain, credibility_score, tier, country, language,
                   total_articles, approved_count, rejected_count
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
            """INSERT INTO sources (name, domain, credibility_score, tier, country, language)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (source.name, source.domain, source.credibility_score,
             source.tier, source.country, source.language)
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
