"""
Newsletter generation and publishing endpoints.
M3: Server-side newsletter generation with AI daily brief and Beehiiv integration.
"""
import json
import logging
import re
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import List

import psycopg2.extras
import requests
from fastapi import APIRouter, HTTPException, Query
from groq import Groq

from database import get_db_connection
from config import (BEEHIIV_API_KEY, BEEHIIV_PUB_ID, VALID_CATEGORIES,
                    SOCIAL_AUTO_POST_NEWSLETTER, OWNER_EMAIL)
from models import (DailyBrief, NewsletterGenerateRequest, NewsletterPublishResponse,
                    PostmarkInboundPayload)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/newsletter", tags=["newsletter"])

# Groq client injected from main.py (same pattern as articles.py)
groq_client: Groq = None

HEADLINE_FONT = "Optima, 'Century Gothic', 'Trebuchet MS', Helvetica, Arial, sans-serif"
BODY_FONT = "Optima, 'Trebuchet MS', 'Microsoft Sans Serif', Helvetica, Arial, sans-serif"


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
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # 1. Fetch approved articles — use specific date if provided,
        #    otherwise find the latest approved batch (same as /articles/approved)
        if request.target_date:
            target = request.target_date
            cursor.execute("""
                SELECT id, url, headline, headline_en, summary, category,
                       publication_name, author, scraped_at, is_top_story, parent_id,
                       embedded_tweets
                FROM articles
                WHERE status = 'approved'
                  AND scraped_at::date = %s::date
                ORDER BY is_top_story DESC, scraped_at DESC
            """, (target,))
        else:
            cursor.execute("""
                SELECT id, url, headline, headline_en, summary, category,
                       publication_name, author, scraped_at, is_top_story, parent_id,
                       embedded_tweets
                FROM articles
                WHERE status = 'approved'
                  AND (scraped_at AT TIME ZONE 'America/New_York')::date
                      = (NOW() AT TIME ZONE 'America/New_York')::date
                ORDER BY is_top_story DESC, scraped_at DESC
            """)

        articles = [dict(row) for row in cursor.fetchall()]

        if not articles:
            raise HTTPException(404, "No approved articles found")

        # Determine the newsletter date — use US Eastern timezone (user's timezone)
        # so the newsletter shows "March 6" when it's still March 6 in the US,
        # even if the server (UTC) has already rolled over to March 7.
        if not request.target_date:
            target = datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d')
        # (when target_date was provided, `target` is already set from line 52)

        # 0. Check if brief already exists for this date (unless regenerate=True)
        if not request.regenerate:
            cursor.execute("SELECT * FROM daily_briefs WHERE date = %s", (target,))
            existing = cursor.fetchone()
            if existing:
                return dict(existing)

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

        # 4. Fetch sponsors for newsletter insertion
        cursor.execute("""
            SELECT id, company_name, headline, summary, link_url, logo_url
            FROM sponsors ORDER BY created_at DESC
        """)
        sponsors = [dict(row) for row in cursor.fetchall()]

        # 5. Build full newsletter HTML
        subject_line = _build_subject_line(top_stories, parents)
        newsletter_html = _build_newsletter_html(
            brief_html, top_stories, other_parents, child_map, target, sponsors=sponsors
        )

        # 6. Upsert into daily_briefs
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

        # Auto-post newsletter digest to Telegram
        if SOCIAL_AUTO_POST_NEWSLETTER:
            try:
                from services.social import telegram
                from services.social.content_generator import generate_newsletter_telegram

                if telegram.is_configured():
                    brief_for_tg = dict(result)
                    tg_text = generate_newsletter_telegram(brief_for_tg, articles)
                    tg_result = telegram.send_message(tg_text, disable_web_page_preview=True)

                    # Record in social_posts (dedup by brief_id)
                    cursor.execute("""
                        SELECT id FROM social_posts
                        WHERE platform = 'telegram' AND brief_id = %s
                    """, (result['id'],))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO social_posts
                                (platform, post_type, platform_post_id, brief_id,
                                 content_text, status, posted_at)
                            VALUES ('telegram', 'newsletter_digest', %s, %s, %s, 'sent', NOW())
                        """, (str(tg_result['message_id']), result['id'], tg_text))
                        conn.commit()
                        logger.info(f"Newsletter auto-posted to Telegram (brief_id={result['id']})")
            except Exception as tg_err:
                logger.error(f"Newsletter auto-post to Telegram failed: {tg_err}")
                # Don't fail the newsletter generation because of a Telegram error
                try:
                    conn.rollback()
                except Exception:
                    pass

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


@router.post("/generate-auto")
def generate_newsletter_auto(request: NewsletterGenerateRequest = NewsletterGenerateRequest()):
    """
    Phase 2: Fully autonomous newsletter generation.
    Selects top 40 → clusters → top 5 with tweets → assembles HTML → sends preview email.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        from services.newsletter_orchestrator import (
            orchestrate_newsletter, send_preview_email
        )

        target = request.target_date
        if not target:
            target = datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d')

        # Check existing brief (unless regenerate)
        if not request.regenerate:
            cursor.execute("SELECT * FROM daily_briefs WHERE date = %s", (target,))
            existing = cursor.fetchone()
            if existing:
                return dict(existing)

        # Run orchestrator
        orch_result = orchestrate_newsletter(cursor, target_date=target, regenerate=request.regenerate)

        if orch_result.get("error"):
            raise HTTPException(404, orch_result["error"])

        top_5 = orch_result["top_5"]
        category_articles = orch_result["category_articles"]
        child_map = orch_result["child_map"]
        tweet_map = orch_result["tweet_map"]
        approval_token = orch_result["approval_token"]

        # Generate AI brief from top 40
        top_40 = orch_result["top_40"]
        brief_text, brief_html = _generate_ai_brief(top_40, top_5)
        word_count = len(brief_text.split()) if brief_text else 0

        # Fetch sponsors
        cursor.execute("""
            SELECT id, company_name, headline, summary, link_url, logo_url
            FROM sponsors ORDER BY created_at DESC
        """)
        sponsors = [dict(row) for row in cursor.fetchall()]

        # Flatten category_articles for other_parents
        other_parents = []
        for cat_articles in category_articles.values():
            other_parents.extend(cat_articles)

        # Build subject line and newsletter HTML
        subject_line = _build_subject_line(top_5, top_40)
        newsletter_html = _build_newsletter_html(
            brief_html, top_5, other_parents, child_map, target,
            sponsors=sponsors, tweet_map=tweet_map
        )

        # Upsert to daily_briefs
        cursor.execute("""
            INSERT INTO daily_briefs (date, summary_text, summary_html, newsletter_html,
                                      subject_line, word_count, generated_at, published,
                                      approval_token)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), FALSE, %s)
            ON CONFLICT (date) DO UPDATE SET
                summary_text = EXCLUDED.summary_text,
                summary_html = EXCLUDED.summary_html,
                newsletter_html = EXCLUDED.newsletter_html,
                subject_line = EXCLUDED.subject_line,
                word_count = EXCLUDED.word_count,
                generated_at = NOW(),
                approval_token = EXCLUDED.approval_token,
                published = FALSE
            RETURNING *
        """, (target, brief_text, brief_html, newsletter_html,
              subject_line, word_count, approval_token))

        result = dict(cursor.fetchone())
        conn.commit()

        # Auto-post to Telegram
        if SOCIAL_AUTO_POST_NEWSLETTER:
            try:
                from services.social import telegram
                from services.social.content_generator import generate_newsletter_telegram
                if telegram.is_configured():
                    tg_text = generate_newsletter_telegram(dict(result), top_40)
                    tg_result = telegram.send_message(tg_text, disable_web_page_preview=True)
                    cursor.execute("""
                        SELECT id FROM social_posts WHERE platform = 'telegram' AND brief_id = %s
                    """, (result['id'],))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO social_posts
                                (platform, post_type, platform_post_id, brief_id,
                                 content_text, status, posted_at)
                            VALUES ('telegram', 'newsletter_digest', %s, %s, %s, 'sent', NOW())
                        """, (str(tg_result['message_id']), result['id'], tg_text))
                        conn.commit()
            except Exception as tg_err:
                logger.error(f"Telegram auto-post failed: {tg_err}")
                try:
                    conn.rollback()
                except Exception:
                    pass

        # Send preview email
        preview_sent = send_preview_email(
            result['id'], newsletter_html, subject_line, approval_token
        )

        result['preview_sent'] = preview_sent
        result['article_count'] = orch_result['article_count']
        result['top_5_ids'] = orch_result['top_5_ids']
        result['clusters_created'] = orch_result['clusters_created']
        result['tweets_fetched'] = orch_result['tweets_fetched']

        logger.info(f"Auto newsletter generated: {result['article_count']} articles, "
                     f"{result['clusters_created']} clusters, preview_sent={preview_sent}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Auto newsletter generation error: {e}")
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


@router.get("/archive")
def get_newsletter_archive(limit: int = Query(90, ge=1, le=365)):
    """
    Public archive: list past newsletters with date and HTML content.
    Returns reverse-chronological list for the public archive page.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT date::text, newsletter_html AS html, subject_line, word_count
            FROM daily_briefs
            WHERE newsletter_html IS NOT NULL
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


def _minify_html(html: str) -> str:
    """Strip unnecessary whitespace from HTML to minimize size for Beehiiv."""
    # Collapse runs of whitespace (newlines, tabs, spaces) into single space
    html = re.sub(r'\s+', ' ', html)
    # Remove space between tags
    html = re.sub(r'>\s+<', '><', html)
    return html.strip()


def _build_newsletter_html(
    brief_html: str,
    top_stories: list,
    other_parents: list,
    child_map: dict,
    target_date: str,
    sponsors: list = None,
    tweet_map: dict = None,
) -> str:
    """Build the complete newsletter HTML with AI brief and all article sections.
    Techmeme-style layout: charcoal headlines, (Author / Source) attribution,
    embedded X posts, sponsor blocks between sections.
    Output is minified for Beehiiv compatibility (shortest possible HTML)."""
    try:
        date_formatted = datetime.strptime(target_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        date_formatted = target_date

    parts = []

    # --- Envelope ---
    parts.append(
        f'<html><head><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>'
        f'<body style="font-family:{BODY_FONT};color:#333;margin:0;padding:0;background:#fff">'
        f'<div style="max-width:600px;margin:0 auto;padding:20px">'
    )

    # --- Header (logo left, date right) ---
    parts.append(
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-bottom:2px solid #e8e8e8;padding-bottom:12px;margin-bottom:24px">'
        f'<tr><td style="vertical-align:bottom">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 90" width="140" height="40">'
        f'<rect x="120" y="5" width="190" height="80" rx="6" fill="transparent" stroke="#E2C26D" stroke-width="6"/>'
        f'<line x1="120" y1="22" x2="310" y2="22" stroke="#E2C26D" stroke-width="3"/>'
        f'<line x1="120" y1="68" x2="310" y2="68" stroke="#E2C26D" stroke-width="3"/>'
        f'<text x="220" y="61" text-anchor="middle" font-family="Inter, sans-serif" font-weight="800" font-size="52" fill="#161625" letter-spacing="-2">memo</text>'
        f'<rect x="5" y="5" width="130" height="80" rx="6" fill="#161625"/>'
        f'<line x1="5" y1="22" x2="135" y2="22" stroke="#E2C26D" stroke-width="3"/>'
        f'<line x1="5" y1="68" x2="135" y2="68" stroke="#E2C26D" stroke-width="3"/>'
        f'<text x="70" y="61" text-anchor="middle" font-family="Inter, sans-serif" font-weight="800" font-size="52" fill="#FFFFFF" letter-spacing="-2">Geo</text>'
        f'</svg>'
        f'</td><td style="text-align:right;vertical-align:bottom">'
        f'<span style="color:#1a5276;font-size:13px;font-weight:600">{date_formatted}</span>'
        f'</td></tr></table>'
    )

    # --- AI Daily Brief (keep purple accent — GeoMemo identity) ---
    if brief_html and brief_html.strip():
        parts.append(
            f'<div style="background:#f8f6ff;border-left:4px solid #430297;padding:16px 20px;margin-bottom:28px;border-radius:0 6px 6px 0">'
            f'<div style="font-family:{HEADLINE_FONT};font-size:14px;font-weight:700;color:#430297;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">Daily Brief</div>'
            f'<div style="font-size:15px;line-height:1.7;color:#333">{brief_html}</div>'
            f'</div>'
        )

    # --- Top News ---
    if top_stories:
        parts.append(
            f'<div style="font-family:{HEADLINE_FONT};color:#1a5276;font-weight:700;font-size:14px;'
            f'border-bottom:3px solid #1a5276;padding-bottom:4px;margin-bottom:18px;'
            f'text-transform:uppercase;letter-spacing:1.5px">Top News</div>'
        )
        _tweet_map = tweet_map or {}
        for a in top_stories:
            # Inject tweets from tweet_map into article for rendering
            if a['id'] in _tweet_map and not a.get('embedded_tweets'):
                a['embedded_tweets'] = _tweet_map[a['id']]
            parts.append(_format_article_item(a, child_map.get(a['id'], []), is_top=True))

    # --- Sponsor block insertion logic ---
    # Distribute sponsors evenly among category sections
    sponsor_list = sponsors or []
    sponsor_slots = []
    if sponsor_list:
        # Build ordered category list first to know how many sections
        ordered_cats = []
        categories = {}
        for a in other_parents:
            cat = a.get('category', 'Other')
            if cat not in VALID_CATEGORIES:
                cat = 'Other'
            categories.setdefault(cat, []).append(a)
        for cat in VALID_CATEGORIES + ['Other']:
            if cat in categories and categories[cat]:
                ordered_cats.append(cat)

        # Place sponsors after every N sections (evenly spaced)
        if ordered_cats and sponsor_list:
            n_sponsors = min(len(sponsor_list), 4)  # Max 4 sponsor blocks
            interval = max(1, len(ordered_cats) // (n_sponsors + 1))
            slot_indices = set()
            for i in range(n_sponsors):
                idx = (i + 1) * interval - 1
                if idx < len(ordered_cats):
                    slot_indices.add(idx)
            sponsor_iter = iter(sponsor_list[:n_sponsors])
            for i, cat in enumerate(ordered_cats):
                sponsor_slots.append(('category', cat, categories[cat]))
                if i in slot_indices:
                    s = next(sponsor_iter, None)
                    if s:
                        sponsor_slots.append(('sponsor', s, None))
        else:
            for cat in VALID_CATEGORIES + ['Other']:
                if cat in categories and categories[cat]:
                    sponsor_slots.append(('category', cat, categories[cat]))
    else:
        # No sponsors — just categories
        categories = {}
        for a in other_parents:
            cat = a.get('category', 'Other')
            if cat not in VALID_CATEGORIES:
                cat = 'Other'
            categories.setdefault(cat, []).append(a)
        for cat in VALID_CATEGORIES + ['Other']:
            if cat in categories and categories[cat]:
                sponsor_slots.append(('category', cat, categories[cat]))

    # Insert first sponsor after Top News section (if available and not already placed)
    if sponsor_list and top_stories:
        first_sponsor = sponsor_list[0] if len(sponsor_list) > len([s for s in sponsor_slots if s[0] == 'sponsor']) else None
        if first_sponsor and not any(s[0] == 'sponsor' for s in sponsor_slots):
            parts.append(_format_sponsor_block(first_sponsor))

    # --- Category Sections + Sponsor Blocks ---
    for slot_type, slot_data, slot_articles in sponsor_slots:
        if slot_type == 'category':
            cat = slot_data
            cat_articles = slot_articles
            parts.append(
                f'<div style="font-family:{HEADLINE_FONT};color:#1a5276;font-weight:700;font-size:14px;'
                f'border-bottom:2px solid #1a5276;padding-bottom:4px;margin-top:32px;margin-bottom:18px;'
                f'text-transform:uppercase;letter-spacing:1.5px">{cat}</div>'
            )
            for a in cat_articles:
                parts.append(_format_article_item(a, child_map.get(a['id'], [])))
        elif slot_type == 'sponsor':
            parts.append(_format_sponsor_block(slot_data))

    # --- Footer ---
    parts.append(
        '<div style="margin-top:50px;padding-top:20px;border-top:1px solid #e8e8e8;color:#999;font-size:11px;text-align:center;line-height:1.6">'
        '&copy; 2026 GeoMemo. Briefing the world\'s decision makers.<br>'
        '<a href="{{unsubscribe_url}}" style="color:#999;text-decoration:underline">Unsubscribe</a>'
        '</div></div></body></html>'
    )

    return _minify_html(''.join(parts))


def _format_article_item(article: dict, children: list, is_top: bool = False) -> str:
    """Render one article (parent + children) in Techmeme-style newsletter HTML.
    Large bold charcoal headline, (Author / Publication) attribution,
    embedded X posts, child articles as bullet list."""
    # Headline text — use summary (which is the AI-enhanced summary) as the display text
    text = article.get('summary') or article.get('headline_en') or article.get('headline') or 'No Content'
    text_clean = re.sub(r'<[^>]*>', '', text)

    # Attribution: (Author / Publication) or just (Publication)
    author = article.get('author') or ''
    pub_name = article.get('publication_name') or ''
    if author and pub_name:
        attribution = f' <span style="color:#999;font-size:14px;font-weight:400">({author} / {pub_name})</span>'
    elif pub_name:
        attribution = f' <span style="color:#999;font-size:14px;font-weight:400">({pub_name})</span>'
    else:
        attribution = ''

    # Headline size: larger for top stories
    headline_size = '22px' if is_top else '18px'

    html = (
        f'<div style="border-bottom:1px solid #e8e8e8;padding:0 0 16px;margin-bottom:16px">'
        f'<a href="{article["url"]}" style="font-family:{HEADLINE_FONT};color:#333;text-decoration:none;'
        f'font-weight:700;font-size:{headline_size};line-height:1.35">{text_clean}</a>'
        f'{attribution}'
    )

    # Embedded X posts (if any)
    embedded_tweets = article.get('embedded_tweets')
    if embedded_tweets:
        tweets_data = embedded_tweets if isinstance(embedded_tweets, list) else []
        for tweet in tweets_data:
            if isinstance(tweet, dict):
                html += _format_embedded_tweet(
                    tweet.get('username', ''),
                    tweet.get('text', '')
                )

    # Render children (cluster items) — Techmeme bullet style
    if children:
        html += '<div style="margin-top:10px;padding-left:4px">'
        for child in children:
            # Use child_summary (20-word angle) if available, otherwise full summary
            child_angle = child.get('child_summary') or ''
            child_pub = child.get('publication_name') or ''
            child_label = child.get('cluster_label') or child.get('relationship') or ''

            if child_angle and child_pub:
                # Phase 2 format: "Publication: 20-word angle summary" with link
                label_badge = ''
                if child_label in ('CONTRARIAN', 'DIFFERENT_ANGLE'):
                    label_color = '#c0392b' if child_label == 'CONTRARIAN' else '#2471a3'
                    label_text = 'contrarian' if child_label == 'CONTRARIAN' else 'different angle'
                    label_badge = f' <span style="font-size:11px;color:{label_color};font-weight:600;text-transform:uppercase">[{label_text}]</span>'
                html += (
                    f'<div style="margin-top:8px;font-size:14px;line-height:1.4">'
                    f'&bull; <a href="{child["url"]}" style="color:#333;text-decoration:none">'
                    f'<strong>{child_pub}</strong>: {child_angle}</a>'
                    f'{label_badge}'
                    f'</div>'
                )
            else:
                # Legacy format: full summary with attribution
                child_text = child.get('summary') or child.get('headline_en') or child.get('headline') or ''
                child_text = re.sub(r'<[^>]*>', '', child_text)
                child_author = child.get('author') or ''
                if child_author and child_pub:
                    child_attr = f' <span style="color:#999;font-size:13px;font-weight:400">({child_author} / {child_pub})</span>'
                elif child_pub:
                    child_attr = f' <span style="color:#999;font-size:13px;font-weight:400">({child_pub})</span>'
                else:
                    child_attr = ''
                html += (
                    f'<div style="margin-top:8px;font-size:16px;line-height:1.4">'
                    f'&bull; <a href="{child["url"]}" style="font-family:{HEADLINE_FONT};color:#333;'
                    f'text-decoration:none;font-weight:700">{child_text}</a>'
                    f'{child_attr}'
                    f'</div>'
                )
        html += '</div>'

    html += '</div>'
    return html


def _format_embedded_tweet(username: str, text: str) -> str:
    """Render a single embedded X post in Techmeme style — clean inline text."""
    if not username and not text:
        return ''
    handle = f'@{username}' if username else ''
    return (
        f'<div style="margin-top:8px;padding-left:4px">'
        f'<span style="font-size:13px;font-weight:700;color:#333">&#120143; {handle}:</span> '
        f'<span style="font-size:13px;color:#555;font-weight:400;line-height:1.5">{text}</span>'
        f'</div>'
    )


def _format_sponsor_block(sponsor: dict) -> str:
    """Render a sponsor block in Techmeme newsletter style."""
    company = sponsor.get('company_name', '')
    headline = sponsor.get('headline', '')
    summary = sponsor.get('summary', '')
    link_url = sponsor.get('link_url', '#')
    logo_url = sponsor.get('logo_url', '')

    logo_html = ''
    if logo_url:
        logo_html = (
            f'<td style="width:80px;vertical-align:top;padding-left:12px">'
            f'<img src="{logo_url}" alt="{company}" style="max-width:80px;max-height:60px;display:block" />'
            f'</td>'
        )

    return (
        f'<div style="background:#f5f5f5;border:1px solid #e0e0e0;padding:16px 20px;margin:28px 0;border-radius:4px">'
        f'<div style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;font-weight:600">Sponsor</div>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="vertical-align:top">'
        f'<a href="{link_url}" style="font-family:{HEADLINE_FONT};font-size:16px;font-weight:700;color:#333;text-decoration:none;line-height:1.3">{headline}</a>'
        f'<div style="font-size:14px;color:#555;margin-top:6px;line-height:1.5">{summary}</div>'
        f'</td>'
        f'{logo_html}'
        f'</tr></table>'
        f'</div>'
    )


# =========================================
# PHASE 2: EMAIL APPROVAL WEBHOOK
# =========================================

@router.post("/inbound-webhook")
def handle_approval_webhook(payload: PostmarkInboundPayload):
    """
    Postmark inbound webhook. Owner replies 'approved' to publish newsletter.
    Verifies sender email matches OWNER_EMAIL.
    """
    # 1. Verify sender
    sender_email = ""
    if payload.FromFull and isinstance(payload.FromFull, dict):
        sender_email = payload.FromFull.get('Email', '').lower()

    if not OWNER_EMAIL or sender_email != OWNER_EMAIL.lower():
        logger.warning(f"Webhook rejected: sender {sender_email} != {OWNER_EMAIL}")
        return {"status": "rejected", "reason": "unauthorized sender"}

    # 2. Check for "approved" in body
    body = (payload.TextBody or '').lower()
    if 'approved' not in body:
        logger.info(f"Webhook received but no 'approved' keyword found")
        return {"status": "ignored", "reason": "no approval keyword"}

    # 3. Find the latest unpublished brief
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT id FROM daily_briefs
            WHERE published = FALSE
            ORDER BY generated_at DESC NULLS LAST, date DESC
            LIMIT 1
        """)
        brief = cursor.fetchone()
        if not brief:
            return {"status": "ignored", "reason": "no unpublished brief found"}

        brief_id = brief['id']
        logger.info(f"Approval received for brief {brief_id}, publishing to Beehiiv...")

        # 4. Publish
        result = publish_to_beehiiv(brief_id)
        return {"status": "published", "brief_id": brief_id, "beehiiv_post_id": result.beehiiv_post_id}

    except Exception as e:
        logger.error(f"Approval webhook error: {e}")
        return {"status": "error", "reason": str(e)}
    finally:
        cursor.close()
        conn.close()
