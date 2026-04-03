"""
Phase 2: Autonomous Newsletter Orchestrator
Chains: select_top_40 → auto_cluster → select_top_5 → fetch_tweets → assemble HTML → send preview
"""
import json
import logging
import uuid
import numpy as np
import psycopg2.extras
from datetime import datetime
from zoneinfo import ZoneInfo
from groq import Groq

logger = logging.getLogger(__name__)

# Groq client (reads GROQ_API_KEY from env)
groq_client = Groq()

# Anthropic client for child summaries
try:
    import anthropic as anthropic_sdk
    import os
    _ak = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_client = anthropic_sdk.Anthropic(api_key=_ak) if _ak else None
except ImportError:
    anthropic_client = None


# =========================================
# TOP 40 SELECTION WITH CATEGORY DIVERSITY
# =========================================

def select_top_40(cursor, target_date: str) -> list:
    """
    Select top 40 approved articles for the target date with category diversity.
    Same-day only — no fallback to old days (no stale news).
    Fills each category up to its cap, then spills unused slots to categories
    that have more articles than their cap.
    """
    from config import NEWSLETTER_CATEGORY_CAPS, NEWSLETTER_TOTAL

    cursor.execute("""
        SELECT id, url, headline, headline_en, summary, summary_long, category,
               publication_name, author, scraped_at, is_top_story,
               auto_approval_score, confidence_score, parent_id,
               country_codes, region, og_image, embedded_tweets, website_tweets,
               source_id, significance_score, impact_score,
               novelty_score_v2, relevance_score_v2, depth_score,
               embedding
        FROM articles
        WHERE status = 'approved'
          AND parent_id IS NULL
          AND scraped_at::date = %s::date
        ORDER BY auto_approval_score DESC NULLS LAST, scraped_at DESC
    """, (target_date,))
    all_articles = [dict(row) for row in cursor.fetchall()]

    if not all_articles:
        logger.warning(f"No approved articles for {target_date}")
        return []

    logger.info(f"Top 40 selection: {len(all_articles)} approved articles available")

    # First pass: fill each category up to its cap
    buckets = {cat: [] for cat in NEWSLETTER_CATEGORY_CAPS}
    overflow = {cat: [] for cat in NEWSLETTER_CATEGORY_CAPS}  # articles beyond cap
    uncategorized = []

    for art in all_articles:
        cat = art.get('category', 'Other')
        cap = NEWSLETTER_CATEGORY_CAPS.get(cat, 0)
        if cat in buckets:
            if len(buckets[cat]) < cap:
                buckets[cat].append(art)
            else:
                overflow[cat].append(art)
        else:
            uncategorized.append(art)

    # Calculate unused slots
    total_selected = sum(len(v) for v in buckets.values())
    unused_slots = NEWSLETTER_TOTAL - total_selected

    # Second pass: distribute unused slots to categories with overflow (by score)
    if unused_slots > 0:
        # Pool all overflow articles, sorted by score
        all_overflow = []
        for cat, arts in overflow.items():
            for art in arts:
                all_overflow.append(art)
        all_overflow.extend(uncategorized)
        all_overflow.sort(key=lambda a: (a.get('auto_approval_score') or 0), reverse=True)

        for art in all_overflow:
            if unused_slots <= 0:
                break
            cat = art.get('category', 'Other')
            if cat in buckets:
                buckets[cat].append(art)
            unused_slots -= 1

    # Flatten
    selected = []
    for cat_articles in buckets.values():
        selected.extend(cat_articles)

    # Sort final selection by score
    selected.sort(key=lambda a: (a.get('auto_approval_score') or 0), reverse=True)

    logger.info(f"Top 40 selected: {len(selected)} articles across "
                f"{len(set(a.get('category') for a in selected))} categories")
    return selected


# =========================================
# TOP 5 SELECTION WITH DIVERSITY
# =========================================

def select_top_5(top_40: list) -> list:
    """
    Select top 5 from top 40 with region/category diversity.
    """
    from config import TOP_NEWS_COUNT

    if len(top_40) <= TOP_NEWS_COUNT:
        return top_40

    # Already sorted by score DESC
    top_5 = [top_40[0]]
    used_categories = {top_40[0].get('category')}
    used_regions = {top_40[0].get('region')}

    for art in top_40[1:]:
        if len(top_5) >= TOP_NEWS_COUNT:
            break
        cat = art.get('category')
        region = art.get('region')

        # Prefer diversity
        if cat not in used_categories or region not in used_regions:
            top_5.append(art)
            used_categories.add(cat)
            used_regions.add(region)

    # If still not enough, fill from remaining by score
    if len(top_5) < TOP_NEWS_COUNT:
        selected_ids = {a['id'] for a in top_5}
        for art in top_40:
            if len(top_5) >= TOP_NEWS_COUNT:
                break
            if art['id'] not in selected_ids:
                top_5.append(art)

    logger.info(f"Top 5 selected: {[a['id'] for a in top_5]}")
    return top_5


# =========================================
# AUTO-CLUSTERING
# =========================================

def auto_cluster_approved(cursor, articles: list) -> dict:
    """
    Cluster approved articles by embedding similarity.
    Classify children via Groq, generate 20-word Haiku child summaries.
    Returns child_map: {parent_id: [child_dict, ...]}
    """
    if len(articles) < 2:
        return {}

    # Use _group_by_topic for NxN similarity clustering
    from routers.articles import _group_by_topic
    grouped = _group_by_topic([dict(a) for a in articles], threshold=0.70)

    # Build groups from topic_group field
    groups = {}
    for art in grouped:
        gid = art.get('topic_group', -1)
        if gid not in groups:
            groups[gid] = []
        groups[gid].append(art)

    child_map = {}
    clusters_created = 0

    for gid, group in groups.items():
        if len(group) < 2:
            continue

        # Parent = highest scoring
        parent = group[0]  # already sorted by score DESC
        children = group[1:]

        # Classify children via Groq
        candidates_txt = ""
        for i, child in enumerate(children[:8]):  # max 8 children per cluster
            candidates_txt += (
                f"{i+1}. ID:{child['id']} | "
                f"Source: {child.get('publication_name') or 'Unknown'} | "
                f"Headline: {child.get('headline') or child.get('headline_en') or 'N/A'} | "
                f"Summary: {(child.get('summary') or 'N/A')[:200]}\n"
            )

        try:
            classify_prompt = f"""Given a MAIN article and CANDIDATE articles, classify each candidate's relationship.

MAIN ARTICLE:
Headline: {parent.get('headline_en') or parent.get('headline') or 'N/A'}
Summary: {(parent.get('summary') or 'N/A')[:300]}

CANDIDATES:
{candidates_txt}

Return ONLY a JSON array:
[{{"id": 123, "relationship": "ADDS_DETAIL", "reason": "Brief reason"}}]

Types:
- DUPLICATE: Same story, no new info
- ADDS_DETAIL: Same story + new facts/data
- DIFFERENT_ANGLE: Different editorial perspective
- CONTRARIAN: Disagrees with main framing
- RELATED: Different story, tangentially related

Be strict: most similar articles are DUPLICATE."""

            chat = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Classify article relationships. Valid JSON only."},
                    {"role": "user", "content": classify_prompt},
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
            )

            raw = chat.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3].strip()

            classifications = json.loads(raw)
            class_map = {c['id']: c for c in classifications if isinstance(c, dict)}

        except Exception as e:
            logger.warning(f"Cluster classification failed for group {gid}: {e}")
            class_map = {}

        # Process children
        cluster_children = []
        for child in children[:8]:
            cls_info = class_map.get(child['id'], {})
            relationship = cls_info.get('relationship', 'RELATED')

            # Skip duplicates
            if relationship == 'DUPLICATE':
                continue

            # Generate 20-word Haiku child summary for valuable children
            child_summary = None
            if relationship in ('ADDS_DETAIL', 'DIFFERENT_ANGLE', 'CONTRARIAN') and anthropic_client:
                try:
                    msg = anthropic_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=50,
                        messages=[{
                            "role": "user",
                            "content": f"""In 20 words, describe what NEW or DIFFERENT perspective this article adds.
Parent story: {parent.get('headline_en') or parent.get('headline')}
Child headline: {child.get('headline_en') or child.get('headline')}
Child source: {child.get('publication_name', 'Unknown')}
Relationship: {relationship}"""
                        }]
                    )
                    child_summary = msg.content[0].text.strip()
                except Exception as e:
                    logger.warning(f"Haiku child summary failed: {e}")
                    child_summary = cls_info.get('reason', '')

            if not child_summary:
                child_summary = cls_info.get('reason', '')

            # Write to DB
            try:
                cursor.execute("""
                    UPDATE articles SET
                        cluster_id = %s, cluster_role = 'child',
                        cluster_label = %s, child_summary = %s,
                        parent_id = %s
                    WHERE id = %s
                """, (parent['id'], relationship, child_summary, parent['id'], child['id']))
            except Exception as e:
                logger.warning(f"Cluster DB update failed for child {child['id']}: {e}")

            cluster_children.append({
                'id': child['id'],
                'headline': child.get('headline_en') or child.get('headline'),
                'publication_name': child.get('publication_name'),
                'url': child.get('url'),
                'relationship': relationship,
                'child_summary': child_summary,
            })

        if cluster_children:
            # Mark parent
            try:
                cursor.execute("""
                    UPDATE articles SET cluster_id = %s, cluster_role = 'parent'
                    WHERE id = %s
                """, (parent['id'], parent['id']))
            except Exception:
                pass

            child_map[parent['id']] = cluster_children
            clusters_created += 1

    try:
        cursor.connection.commit()
    except Exception:
        cursor.connection.rollback()

    logger.info(f"Auto-clustering: {clusters_created} clusters created")
    return child_map


# =========================================
# TWEET FETCHING FOR TOP 5
# =========================================

def fetch_tweets_for_top5(cursor, top_5: list) -> dict:
    """
    Fetch top 3-4 tweets per top 5 article.
    Returns tweet_map: {article_id: [tweet_dict, ...]}
    """
    from config import TOP_TWEETS_PER_ARTICLE
    import time

    tweet_map = {}
    total_fetched = 0

    try:
        from services.social.twitter import fetch_tweets_for_article
    except ImportError:
        logger.warning("Twitter module not available, skipping tweet fetch")
        return tweet_map

    for art in top_5:
        headline = art.get('headline_en') or art.get('headline', '')
        summary = art.get('summary', '')

        try:
            tweets = fetch_tweets_for_article(headline, summary, max_results=10)
            if tweets:
                # Filter: min 50 likes, min 1000 followers, min 50 chars
                quality_tweets = [
                    t for t in tweets
                    if t.get('like_count', 0) >= 20
                    and t.get('followers_count', 0) >= 500
                    and len(t.get('text', '')) >= 50
                ]
                # Take top N by relevance_score
                quality_tweets.sort(key=lambda t: t.get('relevance_score', 0), reverse=True)
                selected = quality_tweets[:TOP_TWEETS_PER_ARTICLE]

                if selected:
                    tweet_map[art['id']] = selected
                    total_fetched += len(selected)

                    # Cache in DB
                    try:
                        cursor.execute("""
                            UPDATE articles SET embedded_tweets = %s WHERE id = %s
                        """, (json.dumps(selected), art['id']))
                    except Exception:
                        pass

            time.sleep(2)  # Rate limit
        except Exception as e:
            logger.warning(f"Tweet fetch failed for article {art['id']}: {e}")

    try:
        cursor.connection.commit()
    except Exception:
        cursor.connection.rollback()

    logger.info(f"Tweets fetched: {total_fetched} across {len(tweet_map)} articles")
    return tweet_map


# =========================================
# PREVIEW EMAIL VIA POSTMARK
# =========================================

def send_preview_email(brief_id: int, newsletter_html: str, subject_line: str, approval_token: str) -> bool:
    """Send newsletter preview to owner via Postmark."""
    import requests
    from config import POSTMARK_SERVER_TOKEN, POSTMARK_FROM_EMAIL, OWNER_EMAIL

    if not POSTMARK_SERVER_TOKEN or not OWNER_EMAIL:
        logger.warning("Postmark not configured, skipping preview email")
        return False

    # Add approval instruction footer
    footer = """
    <div style="margin-top: 30px; padding: 20px; background: #f0f0f0; text-align: center; font-size: 14px;">
        <strong>Reply "approved" to this email to publish this newsletter.</strong><br>
        <span style="color: #666;">Token: {}</span>
    </div>
    """.format(approval_token)

    html_with_footer = newsletter_html.replace("</body>", footer + "</body>")

    try:
        resp = requests.post(
            "https://api.postmarkapp.com/email",
            headers={
                "X-Postmark-Server-Token": POSTMARK_SERVER_TOKEN,
                "Content-Type": "application/json",
            },
            json={
                "From": POSTMARK_FROM_EMAIL,
                "To": OWNER_EMAIL,
                "Subject": f"[PREVIEW] {subject_line}",
                "HtmlBody": html_with_footer,
                "MessageStream": "outbound",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info(f"Preview email sent for brief {brief_id}")
            return True
        else:
            logger.error(f"Postmark error: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Preview email failed: {e}")
        return False


# =========================================
# MAIN ORCHESTRATOR
# =========================================

def orchestrate_newsletter(cursor, target_date: str = None,
                           regenerate: bool = False,
                           send_preview: bool = True) -> dict:
    """
    Full autonomous pipeline:
    1. select_top_40 with category diversity
    2. auto_cluster approved articles
    3. select_top_5 with region/category diversity
    4. fetch_tweets for top 5
    5. Generate AI brief (via existing newsletter.py function)
    6. Build newsletter HTML
    7. Upsert to daily_briefs
    8. Send preview email

    Returns dict with brief_id, article_count, top_5_ids, etc.
    """
    if not target_date:
        target_date = datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d')

    logger.info(f"=== NEWSLETTER ORCHESTRATION START for {target_date} ===")

    # 1. Select top 40
    top_40 = select_top_40(cursor, target_date)
    if not top_40:
        logger.warning("No approved articles found for newsletter")
        return {"error": "No approved articles found", "date": target_date}

    # 2. Auto-cluster
    child_map = auto_cluster_approved(cursor, top_40)

    # 3. Select top 5
    top_5 = select_top_5(top_40)

    # 4. Fetch tweets for top 5
    tweet_map = fetch_tweets_for_top5(cursor, top_5)

    # 5. Group remaining articles by category
    top_5_ids = {a['id'] for a in top_5}
    category_articles = {}
    for art in top_40:
        if art['id'] not in top_5_ids:
            cat = art.get('category', 'Other')
            if cat not in category_articles:
                category_articles[cat] = []
            category_articles[cat].append(art)

    # Generate approval token
    approval_token = str(uuid.uuid4())

    logger.info(f"=== ORCHESTRATION COMPLETE: {len(top_40)} articles, "
                f"{len(top_5)} top, {len(child_map)} clusters, "
                f"{sum(len(v) for v in tweet_map.values())} tweets ===")

    return {
        "date": target_date,
        "top_40": top_40,
        "top_5": top_5,
        "child_map": child_map,
        "tweet_map": tweet_map,
        "category_articles": category_articles,
        "approval_token": approval_token,
        "article_count": len(top_40),
        "top_5_ids": [a['id'] for a in top_5],
        "clusters_created": len(child_map),
        "tweets_fetched": sum(len(v) for v in tweet_map.values()),
    }
