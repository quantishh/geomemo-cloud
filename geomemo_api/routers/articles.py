"""
Article endpoints: listing, approval, enhancement, clustering, similarity search.
"""
import json
import logging
from typing import List

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from psycopg2.extras import execute_values
from groq import Groq
from sentence_transformers import SentenceTransformer

from ..database import get_db_connection
from ..config import VALID_CATEGORIES_SET
from ..models import (
    Article, StatusUpdate, BatchStatusUpdate, CategoryUpdate,
    ManualArticleSubmission, EnhanceRequest,
    ClusterAnalysisRequest, ClusterAnalysisResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Models are loaded once at module level (shared with main app)
embedding_model: SentenceTransformer = None
groq_client: Groq = None


def init_models(embed_model: SentenceTransformer, groq: Groq):
    """Called from main.py to inject shared model instances."""
    global embedding_model, groq_client
    embedding_model = embed_model
    groq_client = groq


def call_groq(headline: str, content: str) -> dict:
    system_prompt = f"""
You are a top-tier geopolitical analyst for 'GeoMemo'.
The user is manually submitting an article. Categorize it and return a valid JSON object:
{{"headline_en": "...", "summary": "...", "category": "..."}}
"""
    user_prompt = f'Headline: "{headline}"\nContent Snippet: "{content}"'
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        processed_data = json.loads(chat_completion.choices[0].message.content)
        processed_data['headline_en'] = processed_data.get('headline_en', headline)
        processed_data['summary'] = processed_data.get('summary', 'No summary provided.')
        processed_data['category'] = processed_data.get('category', 'Other')
        if processed_data['category'] not in VALID_CATEGORIES_SET:
            processed_data['category'] = 'Other'
        return processed_data
    except Exception as e:
        logger.error(f"Groq call failed: {e}")
        raise HTTPException(status_code=500, detail=f"Groq error: {e}")


# --- Article Listing ---

@router.get("/articles", response_model=List[Article])
def get_articles():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id, url, headline AS headline_original, headline_en AS headline,
            summary, category, status, publication_name, author, scraped_at,
            is_top_story, confidence_score, parent_id,
            source_id, relevance_score, repetition_score, auto_approval_score
            FROM articles
            WHERE scraped_at >= NOW() - INTERVAL '7 days'
            ORDER BY scraped_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.get("/articles/archive", response_model=List[Article])
def get_archived_articles():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id, url, headline AS headline_original, headline_en AS headline,
            summary, category, status, publication_name, author, scraped_at,
            is_top_story, confidence_score, parent_id,
            source_id, relevance_score, repetition_score, auto_approval_score
            FROM articles
            WHERE scraped_at < NOW() - INTERVAL '7 days'
            ORDER BY scraped_at DESC
            LIMIT 500
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Archive fetch error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.get("/articles/approved", response_model=List[Article])
def get_approved_articles():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            WITH LatestBatch AS (
                SELECT MAX(scraped_at::date) as max_date
                FROM articles
                WHERE status = 'approved'
            )
            SELECT id, url, headline AS headline_original, headline_en AS headline,
            summary, category, status, publication_name, author, scraped_at,
            is_top_story, confidence_score, parent_id,
            source_id, relevance_score, repetition_score, auto_approval_score
            FROM articles
            WHERE status = 'approved'
            AND scraped_at::date = (SELECT max_date FROM LatestBatch)
            ORDER BY is_top_story DESC, scraped_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Fetch approved error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


# --- Article Actions ---

@router.post("/articles/manual-submission", status_code=201)
def manual_article_submission(article: ManualArticleSubmission):
    try:
        processed = call_groq(article.headline, article.content)
        text_to_embed = f"Headline: {article.headline}\nSummary: {article.content}"
        embed = embedding_model.encode(text_to_embed).tolist()
        conn = get_db_connection()
        cursor = conn.cursor()
        pub_name = article.publication_name if article.publication_name and article.publication_name.strip() else "Manual"
        auth_name = article.author if article.author and article.author.strip() else None
        cursor.execute(
            """INSERT INTO articles (url, headline, publication_name, author, headline_en, summary, category, status, scraped_at, embedding, is_top_story)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW(), %s, %s) RETURNING id""",
            (article.url, article.headline, pub_name, auth_name,
             processed['headline_en'], processed['summary'], processed['category'],
             embed, article.is_top_story),
        )
        nid = cursor.fetchone()[0]
        conn.commit()
        return {"message": "Saved", "article_id": nid}
    except Exception as e:
        logger.error(f"Manual error: {e}")
        raise HTTPException(500, f"Error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()


@router.post("/articles/{article_id}/enhance")
def enhance_article_summary(article_id: int, request: EnhanceRequest):
    text_input = request.summary
    if not text_input:
        raise HTTPException(400, "No text provided")
    try:
        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Summarize/Rewrite this headline/content for a professional news feed in 50 words. English only."},
                {"role": "user", "content": text_input},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
        )
        new_summary = chat.choices[0].message.content.strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        embedding = embedding_model.encode(new_summary).tolist()

        sql = "UPDATE articles SET summary = %s, embedding = %s, status = 'pending'"
        params = [new_summary, embedding]
        if request.publication_name and request.publication_name.strip():
            sql += ", publication_name = %s"
            params.append(request.publication_name)
        if request.author and request.author.strip():
            sql += ", author = %s"
            params.append(request.author)
        sql += " WHERE id = %s"
        params.append(article_id)
        cursor.execute(sql, tuple(params))
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Enhanced", "new_summary": new_summary}
    except Exception as e:
        logger.error(f"Enhance error: {e}")
        raise HTTPException(500, f"Error: {e}")


@router.post("/articles/{article_id}/status")
def update_article_status(article_id: int, status_update: StatusUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE articles SET status = %s WHERE id = %s", (status_update.status, article_id))
        conn.commit()
        return {"message": "Updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/articles/{article_id}/category")
def update_article_category(article_id: int, category_update: CategoryUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE articles SET category = %s WHERE id = %s", (category_update.category, article_id))
        conn.commit()
        return {"message": "Updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/articles/{article_id}/toggle-top")
def toggle_top_story(article_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE articles SET is_top_story = NOT is_top_story WHERE id = %s RETURNING is_top_story", (article_id,))
        conn.commit()
        new_state = cursor.fetchone()[0]
        return {"message": "Updated", "is_top_story": new_state}
    except Exception as e:
        conn.rollback()
        logger.error(f"Toggle top error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/articles/batch-update")
def batch_update_article_status(update_data: BatchStatusUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        execute_values(
            cursor,
            "UPDATE articles SET status = data.status FROM (VALUES %s) AS data(status, id) WHERE articles.id = data.id",
            [(update_data.status, aid) for aid in update_data.ids],
        )
        conn.commit()
        return {"message": "Batch updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


# --- Similarity & Clustering ---

@router.get("/articles/{article_id}/similar", response_model=List[Article])
def get_similar_articles(article_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT embedding, scraped_at, category FROM articles WHERE id = %s", (article_id,))
        target = cursor.fetchone()
        if not target:
            raise HTTPException(404, "Not found")
        cursor.execute(
            """SELECT id, url, headline AS headline_original, headline_en AS headline,
            summary, category, status, publication_name, author, scraped_at,
            is_top_story, parent_id,
            embedding <=> %s AS distance
            FROM articles WHERE id != %s AND embedding IS NOT NULL
            AND scraped_at::date = %s::date AND category = %s
            ORDER BY distance ASC LIMIT 5""",
            (target['embedding'], article_id, target['scraped_at'], target['category']),
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Sim error: {e}")
        raise HTTPException(500, "DB Error")
    finally:
        cursor.close()
        conn.close()


@router.post("/cluster/approve", response_model=ClusterAnalysisResponse)
async def analyze_and_approve_cluster(request: ClusterAnalysisRequest):
    original_id = request.original_article_id
    cluster_ids = request.cluster_ids
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        all_ids = [original_id] + cluster_ids
        q_placeholders = ','.join(['%s'] * len(all_ids))
        cursor.execute(
            f"SELECT id, headline_en, summary, publication_name, url FROM articles WHERE id IN ({q_placeholders})",
            tuple(all_ids),
        )
        articles = {row['id']: dict(row) for row in cursor.fetchall()}

        txt = ""
        orig = articles.get(original_id, {})
        txt += f"--- MAIN ---\nHead: {orig.get('headline_en')}\nSum: {orig.get('summary')}\n\n"
        for i, aid in enumerate(cluster_ids):
            rel = articles.get(aid, {})
            txt += f"--- REL {i+1} ---\nHead: {rel.get('headline_en')}\nSum: {rel.get('summary')}\n\n"

        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Synthesize these into a cohesive summary. Return HTML <p>...</p> only."},
                {"role": "user", "content": txt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
        )
        new_sum = chat.choices[0].message.content

        cursor.execute(
            "UPDATE articles SET status = 'approved', summary = %s, is_top_story = %s WHERE id = %s",
            (new_sum, request.make_top_story, original_id),
        )
        if cluster_ids:
            child_ph = ','.join(['%s'] * len(cluster_ids))
            cursor.execute(
                f"UPDATE articles SET status = 'approved', parent_id = %s WHERE id IN ({child_ph})",
                (original_id, *cluster_ids),
            )
        conn.commit()
        return ClusterAnalysisResponse(
            new_summary=new_sum,
            approved_id=original_id,
            parent_id=original_id,
            child_ids=cluster_ids,
            is_top_story=request.make_top_story,
        )
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()
