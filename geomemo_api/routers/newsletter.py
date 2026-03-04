"""
Newsletter generation and publishing endpoints.
M3: Server-side newsletter generation with AI daily brief and Beehiiv integration.
"""
import json
import logging
import re
from datetime import datetime, date
from typing import List

import psycopg2.extras
import requests
from fastapi import APIRouter, HTTPException, Query
from groq import Groq

from database import get_db_connection
from config import BEEHIIV_API_KEY, BEEHIIV_PUB_ID, VALID_CATEGORIES
from models import DailyBrief, NewsletterGenerateRequest, NewsletterPublishResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/newsletter", tags=["newsletter"])

# Groq client injected from main.py (same pattern as articles.py)
groq_client: Groq = None

FONT_STACK = "'Calibri', 'Segoe UI', Helvetica, Arial, sans-serif"


def init_models(groq: Groq):
    """Called from main.py to inject the shared Groq client."""
    global groq_client
    groq_client = groq


# =========================================
# ENDPOINTS
# =========================================

@router.post("/generate", response_model=DailyBrief)
def generate_newsletter(request: NewsletterGenerateRequest = NewsletterGenerateRequest()):
    """
    Generate today's newsletter: AI brief + full article HTML.
    Saves to daily_briefs table. Returns generated content for preview.
    """
    target = request.target_date or date.today().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # 0. Check if brief already exists (unless regenerate=True)
        if not request.regenerate:
            cursor.execute("SELECT * FROM daily_briefs WHERE date = %s", (target,))
            existing = cursor.fetchone()
            if existing:
                return dict(existing)

        # 1. Fetch approved articles for this date
        cursor.execute("""
            SELECT id, url, headline, headline_en, summary, category,
                   publication_name, author, scraped_at, is_top_story, parent_id
            FROM articles
            WHERE status = 'approved'
              AND scraped_at::date = %s::date
            ORDER BY is_top_story DESC, scraped_at DESC
        """, (target,))
        articles = [dict(row) for row in cursor.fetchall()]

        if not articles:
            raise HTTPException(404, f"No approved articles found for {target}")

        # 2. Separate parents and children
        parents = [a for a in articles if not a['parent_id']]
        children = [a for a in articles if a['parent_id']]
        child_map = {}
        for c in children:
            child_map.setdefault(c['parent_id'], []).append(c)

        top_stories = [a for a in parents if a['is_top_story']]
        other_parents = [a for a in parents if not a['is_top_story']]

        # 3. Generate AI Daily Brief via Groq
        brief_text, brief_html = _generate_ai_brief(parents, top_stories)
        word_count = len(brief_text.split()) if brief_text else 0

        # 4. Build full newsletter HTML
        subject_line = _build_subject_line(top_stories, parents)
        newsletter_html = _build_newsletter_html(
            brief_html, top_stories, other_parents, child_map, target
        )

        # 5. Upsert into daily_briefs
        cursor.execute("""
            INSERT INTO daily_briefs (date, summary_text, summary_html, newsletter_html,
                                      subject_line, word_count, generated_at, published)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), FALSE)
            ON CONFLICT (date) DO UPDATE SET
                summary_text = EXCLUDED.summary_text,
                summary_html = EXCLUDED.summary_html,
                newsletter_html = EXCLUDED.newsletter_html,
                subject_line = EXCLUDED.subject_line,
                word_count = EXCLUDED.word_count,
                generated_at = NOW()
            RETURNING *
        """, (target, brief_text, brief_html, newsletter_html, subject_line, word_count))

        result = dict(cursor.fetchone())
        conn.commit()
        return result

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Newsletter generation error: {e}")
        raise HTTPException(500, f"Generation failed: {e}")
    finally:
        cursor.close()
        conn.close()


@router.post("/{brief_id}/publish", response_model=NewsletterPublishResponse)
def publish_to_beehiiv(brief_id: int):
    """Push a generated newsletter to Beehiiv as a draft."""
    if not BEEHIIV_API_KEY or not BEEHIIV_PUB_ID:
        raise HTTPException(500, "Beehiiv credentials not configured. Set BEEHIIV_API_KEY and BEEHIIV_PUBLICATION_ID in .env")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM daily_briefs WHERE id = %s", (brief_id,))
        brief = cursor.fetchone()
        if not brief:
            raise HTTPException(404, "Newsletter brief not found")

        # Idempotent: if already published, return existing post ID
        if brief['published'] and brief['beehiiv_post_id']:
            return NewsletterPublishResponse(
                message="Already published",
                beehiiv_post_id=brief['beehiiv_post_id'],
                brief_id=brief_id,
            )

        # Create Beehiiv draft post
        url = f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUB_ID}/posts"
        headers = {
            "Authorization": f"Bearer {BEEHIIV_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "title": brief['subject_line'] or f"GeoMemo Daily Intelligence - {brief['date']}",
            "content_html": brief['newsletter_html'] or brief['summary_html'] or "",
            "status": "draft",
            "show_in_feed": True,
            "email_subject_line": brief['subject_line'] or f"GeoMemo: Daily Intelligence - {brief['date']}",
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        beehiiv_id = response.json()['data']['id']

        # Update database
        cursor.execute(
            "UPDATE daily_briefs SET published = TRUE, beehiiv_post_id = %s WHERE id = %s",
            (beehiiv_id, brief_id),
        )
        conn.commit()

        return NewsletterPublishResponse(
            message="Draft created in Beehiiv",
            beehiiv_post_id=beehiiv_id,
            brief_id=brief_id,
        )

    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Beehiiv API error: {e}")
        error_body = e.response.text if e.response else "No response"
        raise HTTPException(502, f"Beehiiv API error: {error_body}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Publish error: {e}")
        raise HTTPException(500, f"Publish failed: {e}")
    finally:
        cursor.close()
        conn.close()


@router.get("/history", response_model=List[DailyBrief])
def get_newsletter_history(limit: int = Query(30, ge=1, le=365)):
    """List past daily briefs with metadata."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id, date, summary_text, summary_html, newsletter_html,
                   subject_line, word_count, generated_at, published, beehiiv_post_id
            FROM daily_briefs
            ORDER BY date DESC
            LIMIT %s
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


@router.get("/{brief_id}", response_model=DailyBrief)
def get_newsletter_by_id(brief_id: int):
    """Get a single newsletter brief by ID."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM daily_briefs WHERE id = %s", (brief_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Brief not found")
        return dict(row)
    finally:
        cursor.close()
        conn.close()


# =========================================
# PRIVATE HELPERS
# =========================================

def _generate_ai_brief(parents: list, top_stories: list) -> tuple:
    """
    Call Groq to generate a ~300-word executive intelligence summary.
    Returns (plain_text, html).
    """
    if not groq_client:
        logger.warning("Groq client not available, skipping AI brief")
        return "", ""

    # Build article summaries for the prompt (cap at 20 to stay within context)
    article_summaries = ""
    for i, a in enumerate(parents[:20]):
        label = "[TOP STORY] " if a.get('is_top_story') else ""
        headline = a.get('headline_en') or a.get('headline') or 'N/A'
        summary = (a.get('summary') or 'N/A')[:400]
        # Strip HTML tags from summary
        summary = re.sub(r'<[^>]*>', '', summary)
        article_summaries += (
            f"{i+1}. {label}{headline}\n"
            f"   Category: {a.get('category', 'Other')}\n"
            f"   Summary: {summary}\n"
            f"   Source: {a.get('publication_name') or 'Unknown'}\n\n"
        )

    system_prompt = """You are the chief analyst at GeoMemo, a geopolitical intelligence service used by investment bankers, asset managers, and senior policymakers.

Write a "Daily Brief" — a 250-350 word executive summary of today's most significant geopolitical developments and their market/policy implications.

REQUIREMENTS:
1. LEAD with the single most consequential development and its immediate implications
2. Cover 3-5 key stories, prioritizing TOP STORY items
3. Draw connections between events when relevant (e.g., "This compounds pressure on..." or "Combined with...")
4. Include specific data points, names, and figures when available
5. End with a forward-looking sentence on what to watch next
6. Tone: authoritative, concise, analytical. No hedging language ("might", "could possibly"). Use direct statements.
7. NO bullet points. Write in flowing paragraphs (2-3 paragraphs).
8. Do NOT use any greetings, sign-offs, or meta-commentary. Start directly with the analysis.

FORMAT: Return a JSON object with exactly two fields:
- "text": The plain text version of the brief
- "html": The HTML version using only <p> and <strong> tags. Use <strong> for country names, leader names, key figures, and critical terms."""

    user_prompt = f"Today's approved articles for the Daily Brief:\n\n{article_summaries}"

    try:
        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = chat.choices[0].message.content
        result = json.loads(raw)
        text = result.get("text", "")
        html = result.get("html", f"<p>{text}</p>")
        return text, html
    except json.JSONDecodeError as e:
        logger.error(f"Groq returned invalid JSON for brief: {e}")
        # Try to extract text from raw response as fallback
        if raw and len(raw) > 20:
            return raw[:1000], f"<p>{raw[:1000]}</p>"
        return "", ""
    except Exception as e:
        logger.error(f"Groq brief generation failed: {e}")
        return "", ""


def _build_subject_line(top_stories: list, parents: list) -> str:
    """Generate email subject line from top story headline."""
    if top_stories:
        text = top_stories[0].get('summary') or top_stories[0].get('headline_en') or top_stories[0].get('headline') or 'Daily Update'
    elif parents:
        text = parents[0].get('summary') or parents[0].get('headline_en') or parents[0].get('headline') or 'Daily Update'
    else:
        text = 'Daily Update'
    # Strip HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    # Truncate for email subject
    if len(text) > 120:
        text = text[:117] + '...'
    return f"GeoMemo: {text}"


def _build_newsletter_html(
    brief_html: str,
    top_stories: list,
    other_parents: list,
    child_map: dict,
    target_date: str,
) -> str:
    """Build the complete newsletter HTML with AI brief and all article sections."""
    try:
        date_formatted = datetime.strptime(target_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        date_formatted = target_date

    # --- Header ---
    html = f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family:{FONT_STACK};color:#111;margin:0;padding:0;background-color:#fff;">
<div style="max-width:600px;width:100%;margin:0 auto;padding:20px;">

<div style="border-bottom:2px solid #eee;padding-bottom:15px;margin-bottom:20px;">
    <span style="font-size:24px;font-weight:800;color:#430297;letter-spacing:-0.5px;text-transform:uppercase;">GeoMemo</span><br>
    <span style="color:#666;font-size:13px;font-weight:400;">Daily Intelligence &bull; {date_formatted}</span>
</div>"""

    # --- AI Daily Brief (NEW in M3) ---
    if brief_html and brief_html.strip():
        html += f"""
<div style="background-color:#f8f6ff;border-left:4px solid #430297;padding:16px 20px;margin-bottom:25px;border-radius:0 6px 6px 0;">
    <div style="font-size:14px;font-weight:700;color:#430297;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">Daily Brief</div>
    <div style="font-size:14px;line-height:1.6;color:#1f2937;">{brief_html}</div>
</div>"""

    # --- Top News ---
    if top_stories:
        html += f"""<div style="color:#b00;font-family:{FONT_STACK};font-weight:700;font-size:14px;border-bottom:2px solid #b00;margin-bottom:15px;text-transform:uppercase;letter-spacing:0.5px;">Top News</div>"""
        for a in top_stories:
            html += _format_article_item(a, child_map.get(a['id'], []))

    # --- Category Sections ---
    categories = {}
    for a in other_parents:
        cat = a.get('category', 'Other')
        if cat not in VALID_CATEGORIES:
            cat = 'Other'
        categories.setdefault(cat, []).append(a)

    for cat in VALID_CATEGORIES + ['Other']:
        if cat in categories and categories[cat]:
            html += f"""<div style="color:#b00;font-family:{FONT_STACK};font-weight:700;font-size:14px;border-bottom:1px solid #ddd;margin-top:30px;margin-bottom:15px;text-transform:uppercase;letter-spacing:0.5px;">{cat}</div>"""
            for a in categories[cat]:
                html += _format_article_item(a, child_map.get(a['id'], []))

    # --- Footer ---
    html += """
<div style="margin-top:50px;padding-top:20px;border-top:1px solid #eee;color:#999;font-size:11px;text-align:center;line-height:1.6;">
    &copy; 2025 GeoMemo.<br>Briefing the world's decision makers.<br>
    <a href="{{unsubscribe_url}}" style="color:#999;text-decoration:underline;">Unsubscribe</a>
</div>
</div></body></html>"""

    return html


def _format_article_item(article: dict, children: list) -> str:
    """Render one article (parent + children) in newsletter HTML."""
    text = article.get('summary') or article.get('headline_en') or article.get('headline') or 'No Content'
    # Strip HTML tags
    text_clean = re.sub(r'<[^>]*>', '', text)

    time_str = ''
    if article.get('scraped_at'):
        try:
            time_str = article['scraped_at'].strftime("%I:%M %p")
        except AttributeError:
            # scraped_at might be a string
            pass

    pub_name = article.get('publication_name') or ''
    author = article.get('author') or ''
    meta = f"({pub_name}" + (f" - {author}" if author else "") + f") {time_str}"

    html = f"""
<div style="border-bottom:1px solid #eee;padding-bottom:15px;margin-bottom:15px;">
    <div style="line-height:1.4;font-size:16px;">
        <a href="{article['url']}" style="color:#1f2937;text-decoration:none;font-weight:700;">{text_clean}</a>
        <span style="color:#888;font-size:12px;font-weight:300;margin-left:6px;">{meta}</span>
    </div>"""

    # Render children (cluster items)
    if children:
        for child in children:
            child_pub = child.get('publication_name') or 'Source'
            child_text = child.get('summary') or child.get('headline_en') or child.get('headline') or ''
            child_text = re.sub(r'<[^>]*>', '', child_text)
            html += f"""
    <div style="margin-top:8px;font-size:13px;color:#666;line-height:1.4;">
        <a href="{child['url']}" style="color:#008000;font-weight:bold;text-decoration:none;">{child_pub}</a>: {child_text}
    </div>"""

    html += "\n</div>"
    return html
