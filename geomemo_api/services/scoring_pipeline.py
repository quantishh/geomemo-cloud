"""
Pass 2: Scoring Pipeline
Runs AFTER scraping. Takes unscored articles from DB and processes them:
1. Tier 3 keyword filter
2. Tier 1 entity auto-include
3. Q1-Q5 classification via Groq
4. Embedding generation
5. Haiku summary generation
6. Composite scoring
"""
import json
import logging
import os
import numpy as np
import psycopg2.extras
from groq import Groq

logger = logging.getLogger(__name__)

# Lazy-load heavy models only when scoring is triggered
_embedding_model = None
_groq_client = None
_anthropic_client = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Embedding model loaded for scoring pipeline")
    return _embedding_model


def _get_groq():
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq()
    return _groq_client


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
            key = os.getenv("ANTHROPIC_API_KEY", "")
            if key:
                _anthropic_client = anthropic.Anthropic(api_key=key)
        except ImportError:
            pass
    return _anthropic_client


# =========================================
# KEYWORD & ENTITY CHECKS
# =========================================

GEO_KEYWORDS = {
    "conflict": ["war", "military", "troops", "missile", "bombing", "ceasefire",
                 "invasion", "insurgency", "coup", "airstrike", "drone strike",
                 "artillery", "combat", "siege", "occupation", "conflict",
                 "attack", "strike", "offensive", "defense", "armed",
                 "terrorism", "militant", "rebel", "casualties"],
    "diplomacy": ["sanctions", "embargo", "treaty", "summit", "diplomatic",
                  "ambassador", "bilateral", "multilateral", "peace talks",
                  "foreign minister", "diplomacy", "envoy", "negotiate",
                  "accord", "pact", "alliance", "bloc", "customs"],
    "economics": ["tariff", "trade war", "gdp", "inflation", "central bank",
                  "currency", "debt crisis", "recession", "fiscal policy",
                  "monetary policy", "interest rate", "deficit", "trade",
                  "export", "import", "subsidy", "economic"],
    "markets": ["stock market", "commodity", "oil price", "forex", "bond",
                "equity", "market crash", "rally", "crude oil", "gold price",
                "dow jones", "nasdaq", "stocks", "shares", "investor"],
    "politics": ["election", "parliament", "legislation", "referendum",
                 "coalition", "opposition", "regime", "constitutional",
                 "impeachment", "political crisis", "president", "minister",
                 "government", "congress", "senate", "policy", "vote"],
    "security": ["nuclear", "cybersecurity", "espionage", "intelligence",
                 "defense pact", "arms deal", "weapons", "ballistic",
                 "hypersonic", "submarine", "aircraft carrier", "security",
                 "spy", "surveillance", "drone", "cyber"],
    "energy": ["opec", "oil price", "pipeline", "lng", "energy security",
               "renewable", "natural gas", "petroleum", "refinery",
               "strait of hormuz", "energy crisis", "oil", "gas", "fuel",
               "solar", "wind power", "energy"],
    "disaster": ["earthquake", "hurricane", "tsunami", "flood", "wildfire",
                 "drought", "famine", "climate change", "crop failure",
                 "climate migration", "displacement", "disaster", "volcano",
                 "typhoon", "cyclone", "landslide"],
    "institutions": ["nato", "united nations", "european union", "african union",
                     "brics", "asean", "g7", "g20", "imf", "world bank",
                     "wto", "iaea", "who", "icc", "icj", "eu ", "un "],
    "leaders": ["biden", "trump", "putin", "xi jinping", "macron", "scholz",
                "modi", "erdogan", "netanyahu", "zelenskyy", "zelensky",
                "kim jong", "khamenei", "mbs"],
    "countries": ["iran", "israel", "ukraine", "russia", "china", "taiwan",
                  "north korea", "syria", "iraq", "yemen", "gaza",
                  "palestine", "afghanistan", "pakistan", "india",
                  "saudi", "turkey", "egypt", "libya", "sudan"],
}

HIGH_VALUE_ENTITIES = [
    "un security council", "nato", "g7", "g20", "brics", "european union", "asean",
    "imf", "world bank", "federal reserve", "ecb", "opec",
    "biden", "trump", "xi jinping", "putin", "modi", "macron", "scholz",
    "zelenskyy", "zelensky", "kim jong un", "erdogan", "netanyahu",
    "pentagon", "kremlin", "white house", "state department",
    "icc", "icj", "who", "wto", "iaea",
    "strait of hormuz", "south china sea", "taiwan strait",
    "nuclear weapons", "ballistic missile",
]


def _keyword_check(headline, content):
    text = (headline + " " + (content or "")).lower()
    for kw_list in GEO_KEYWORDS.values():
        for kw in kw_list:
            if kw in text:
                return True
    return False


def _entity_check(headline):
    h = headline.lower()
    return any(e in h for e in HIGH_VALUE_ENTITIES)


# =========================================
# GROQ Q1-Q5 CLASSIFICATION
# =========================================

VALID_CATEGORIES = {
    'Geopolitical Conflict', 'Geopolitical Economics', 'Global Markets',
    'International Relations', 'Geopolitical Politics', 'GeoNatDisaster',
    'GeoLocal', 'Other'
}


def _classify_article(headline, content):
    """Q1-Q5 classification via Groq. Returns dict with validated category."""
    groq = _get_groq()
    system_prompt = """You are a geopolitical intelligence analyst for GeoMemo.
Evaluate this article on 5 independent criteria. Answer YES or NO for each.

Q1 - GEOPOLITICAL SIGNIFICANCE: Does this describe a development with INTERNATIONAL implications?
  YES = cross-border military action, international sanctions, treaties between nations,
  alliance shifts (NATO, EU, BRICS decisions), territorial disputes between countries,
  international trade agreements, conflicts affecting multiple nations, major elections
  that change a country's foreign policy direction.
  NO = purely domestic policy (minimum wage, healthcare, education) without international
  spillover, routine diplomatic meetings with no outcome, courtesy calls between leaders,
  local crime, sports, entertainment, celebrity, tourism, lifestyle, opinion/editorial.

Q2 - GLOBAL ECONOMIC IMPACT: Does this directly affect INTERNATIONAL trade, commodity markets,
  supply chains, currency markets, or central bank policy across borders?
  NO = purely domestic economic policy affecting only one country's internal market.

Q3 - NOVELTY: Does this contain genuinely NEW information?
  YES = first report of an event, escalation, new actor entering, quantified impact,
  policy reversal, breakthrough in negotiations.
  NO = rehash of yesterday's news, "conflict continues" updates, opinion/editorial
  about known events, routine status reports.

Q4 - DECISION-MAKER RELEVANCE: Would a US/European/Asian government official, institutional
  investor, or multinational business leader need to know this for decisions?

Q5 - ANALYTICAL DEPTH: Does the article provide data, named sources, expert analysis,
  historical context, or quantified impact (not just bare facts from a wire report)?

Also extract:
- category: MUST be exactly one of: Geopolitical Conflict, Geopolitical Economics, Global Markets, International Relations, Geopolitical Politics, GeoNatDisaster, GeoLocal, Other.
- sub_category: specific topic within category (e.g., "Trade War", "Sanctions", "Crypto", "Elections", "Maritime Security", "Nuclear", "Cybersecurity", "Food Security", "Climate", "Migration")
- countries: list of country names mentioned or implied
- headline_en: formal English translation of headline (keep original if already English)
- language: ISO 639-1 language code of the original article (e.g., "en", "ar", "zh", "vi", "es")
- entities: list of key entities mentioned. For each: name, type (person/organization/company/military/commodity/currency/stock_index/policy/infrastructure/industry), and country code if applicable.

Return valid JSON:
{"q1": "YES or NO", "q2": "YES or NO", "q3": "YES or NO", "q4": "YES or NO", "q5": "YES or NO", "category": "...", "sub_category": "...", "countries": [...], "headline_en": "...", "language": "en", "entities": [{"name": "...", "type": "...", "country": "..."}]}"""

    user_prompt = f'Headline: "{headline}"\nContent: "{(content or "")[:3000]}"'

    chat = groq.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    result = json.loads(chat.choices[0].message.content)

    # Force category validation
    if result.get('category') not in VALID_CATEGORIES:
        result['category'] = 'Other'

    return result


def _derive_scores(q_data):
    """Returns (q1, q2, q3, q4, q5, composite)."""
    def yn(key):
        return 1 if str(q_data.get(key, "NO")).upper().startswith("YES") else 0
    q1, q2, q3, q4, q5 = yn("q1"), yn("q2"), yn("q3"), yn("q4"), yn("q5")
    composite = q1 * 30 + q2 * 25 + q3 * 20 + q4 * 20 + q5 * 5
    return q1, q2, q3, q4, q5, composite


# =========================================
# TWO-TIER SUMMARIES
# =========================================

def _generate_groq_summary(headline, content):
    """Tier 1: Cheap Groq Llama summary for ALL articles. 30-35 words."""
    groq = _get_groq()
    if not groq:
        return None

    parts = [f"Headline: {headline}"]
    if content and len(content.strip()) > 50:
        parts.append(f"Content: {content[:3000]}")
    article_text = "\n".join(parts)

    try:
        chat = groq.chat.completions.create(
            messages=[{
                "role": "user",
                "content": f"""Summarize this article in one comprehensive sentence of 30-35 words.
Write in English, in your own words, reporter and analyst tone.
Match tense to event. No hashtags, no markdown. Never refuse.

{article_text}"""
            }],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=80,
        )
        raw = chat.choices[0].message.content.strip()
        return _clean_summary(raw, headline)
    except Exception as e:
        logger.warning(f"Groq summary failed: {e}")
        return None


def _generate_haiku_summary(headline, content):
    """Tier 2: Quality Haiku summary for APPROVED articles only. 30-35 words."""
    client = _get_anthropic()
    if not client:
        return None

    parts = [f"Headline: {headline}"]
    if content and len(content.strip()) > 50:
        parts.append(f"Content: {content[:4000]}")
    article_text = "\n".join(parts)

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"""Summarize this article in one comprehensive sentence of 30-35 words.
Include: who did what, the specific impact or number, and the broader context.
Write in English, in your own words, reporter and analyst tone.
Match tense to event. No hashtags, no markdown. Never refuse.

{article_text}"""
            }]
        )
        raw = msg.content[0].text.strip()
        return _clean_summary(raw, headline)
    except Exception as e:
        logger.warning(f"Haiku summary failed: {e}")
        return None


# Legacy alias
def _generate_summary(headline, content):
    return _generate_haiku_summary(headline, content)


# =========================================
# ENTITY STORAGE
# =========================================

def _store_entities(cursor, article_id, entities_data):
    """Store extracted entities and link to article."""
    if not entities_data or not isinstance(entities_data, list):
        return 0

    stored = 0
    for ent in entities_data:
        if not isinstance(ent, dict) or not ent.get('name'):
            continue

        name = ent['name'].strip()
        etype = ent.get('type', 'unknown').lower()
        country = ent.get('country', None)

        if len(name) < 2 or len(name) > 200:
            continue

        try:
            # Upsert entity
            cursor.execute("""
                INSERT INTO entities (name, entity_type, country_code, last_seen_at, article_count)
                VALUES (%s, %s, %s, NOW(), 1)
                ON CONFLICT (LOWER(name), entity_type)
                DO UPDATE SET last_seen_at = NOW(),
                              article_count = entities.article_count + 1,
                              country_code = COALESCE(EXCLUDED.country_code, entities.country_code)
                RETURNING id
            """, (name, etype, country))
            entity_id = cursor.fetchone()[0]

            # Link to article
            cursor.execute("""
                INSERT INTO article_entities (article_id, entity_id)
                VALUES (%s, %s)
                ON CONFLICT (article_id, entity_id) DO NOTHING
            """, (article_id, entity_id))

            stored += 1
        except Exception as e:
            logger.debug(f"Entity store failed for '{name}': {e}")
            cursor.connection.rollback()

    return stored


def _clean_summary(summary: str, headline: str) -> str:
    """Post-process summary: strip hashtags, detect refusals."""
    if not summary:
        return None

    # Strip markdown headers and hashtags
    lines = summary.split('\n')
    cleaned_lines = [l for l in lines if not l.strip().startswith('#')]
    summary = ' '.join(cleaned_lines).strip()

    # Remove leading labels like "Summary:", "News Summary:", etc.
    import re
    summary = re.sub(r'^(summary|news summary|article summary)\s*[:\-]\s*', '', summary, flags=re.IGNORECASE).strip()

    # Detect refusals
    refusal_phrases = [
        "i appreciate", "i cannot", "could you please", "i notice",
        "i would need", "to produce an accurate", "please provide",
        "i'm unable", "as requested", "source material",
        "i don't have", "i don't see", "please share",
        "you've provided only", "without the article",
    ]
    lower = summary.lower()
    if any(phrase in lower for phrase in refusal_phrases):
        return None  # Will trigger fallback

    return summary.strip()


# =========================================
# COUNTRY RESOLUTION
# =========================================

def _resolve_countries(country_names):
    """Convert country names to ISO codes + region."""
    try:
        import pycountry
    except ImportError:
        return [], None

    REGION_MAP = {
        'US': 'North America', 'CA': 'North America', 'MX': 'North America',
        'GB': 'Europe', 'FR': 'Europe', 'DE': 'Europe', 'IT': 'Europe',
        'ES': 'Europe', 'PL': 'Europe', 'UA': 'Europe', 'NL': 'Europe',
        'SE': 'Europe', 'NO': 'Europe', 'GR': 'Europe', 'RO': 'Europe',
        'CH': 'Europe', 'AT': 'Europe', 'BE': 'Europe', 'PT': 'Europe',
        'CN': 'East Asia', 'JP': 'East Asia', 'KR': 'East Asia',
        'KP': 'East Asia', 'TW': 'East Asia', 'MN': 'East Asia',
        'IN': 'South Asia', 'PK': 'South Asia', 'BD': 'South Asia',
        'LK': 'South Asia', 'NP': 'South Asia',
        'RU': 'Russia & Central Asia', 'KZ': 'Russia & Central Asia',
        'UZ': 'Russia & Central Asia',
        'IR': 'Middle East', 'IQ': 'Middle East', 'SA': 'Middle East',
        'AE': 'Middle East', 'IL': 'Middle East', 'TR': 'Middle East',
        'SY': 'Middle East', 'YE': 'Middle East', 'JO': 'Middle East',
        'LB': 'Middle East', 'PS': 'Middle East', 'QA': 'Middle East',
        'EG': 'Africa', 'NG': 'Africa', 'ZA': 'Africa', 'KE': 'Africa',
        'ET': 'Africa', 'SD': 'Africa', 'LY': 'Africa',
        'BR': 'South America', 'AR': 'South America', 'CO': 'South America',
        'CL': 'South America', 'VE': 'South America', 'PE': 'South America',
        'AU': 'Oceania', 'NZ': 'Oceania',
        'TH': 'Southeast Asia', 'VN': 'Southeast Asia', 'PH': 'Southeast Asia',
        'MY': 'Southeast Asia', 'SG': 'Southeast Asia', 'ID': 'Southeast Asia',
        'MM': 'Southeast Asia',
    }

    codes = []
    for name in (country_names or []):
        name = name.strip()
        if not name:
            continue
        country = pycountry.countries.get(name=name)
        if not country:
            country = pycountry.countries.get(common_name=name)
        if not country:
            try:
                results = pycountry.countries.search_fuzzy(name)
                country = results[0] if results else None
            except LookupError:
                country = None
        if country:
            codes.append(country.alpha_2)

    region = REGION_MAP.get(codes[0]) if codes else None
    return codes, region


# =========================================
# MAIN SCORING FUNCTION
# =========================================

def score_unscored_articles(cursor, limit=500, batch_name="manual"):
    """
    Pass 2: Score all unscored articles in the database.
    Returns stats dict.
    """
    from pgvector.psycopg2 import register_vector
    register_vector(cursor.connection)

    cursor.execute("""
        SELECT id, headline, summary, full_content, publication_name
        FROM articles
        WHERE status = 'unscored'
        ORDER BY scraped_at DESC
        LIMIT %s
    """, (limit,))
    articles = [dict(row) for row in cursor.fetchall()]

    if not articles:
        return {"message": "No unscored articles found", "processed": 0}

    logger.info(f"Scoring {len(articles)} unscored articles...")

    stats = {
        "processed": 0,
        "keyword_rejected": 0,
        "groq_classified": 0,
        "haiku_summarized": 0,
        "errors": 0,
        "_scored_ids": [],  # Track IDs for scoped auto-approve
    }

    model = _get_embedding_model()

    for art in articles:
        article_id = art['id']
        headline = art['headline'] or ''
        content = art['full_content'] or art['summary'] or ''
        pub_name = art['publication_name'] or ''

        try:
            # Tier 3: Keyword filter
            if not _keyword_check(headline, content):
                cursor.execute("""
                    UPDATE articles SET status = 'rejected', auto_approval_score = 35,
                    confidence_score = 35 WHERE id = %s
                """, (article_id,))
                cursor.connection.commit()
                stats["keyword_rejected"] += 1
                stats["processed"] += 1
                continue

            # Tier 1: Entity check
            entity_auto = _entity_check(headline)

            # Q1-Q5 classification
            q_data = _classify_article(headline, content)
            q1, q2, q3, q4, q5, q_composite = _derive_scores(q_data)

            if entity_auto:
                q_composite = max(q_composite, 75)

            headline_en = q_data.get('headline_en', headline)
            category = q_data.get('category', 'Other')
            stats["groq_classified"] += 1

            # Countries
            country_names = q_data.get('countries', [])
            if not isinstance(country_names, list):
                country_names = []
            country_codes, region = _resolve_countries(country_names)

            # Embedding
            text_to_embed = f"Headline: {headline_en}\nContent: {content[:500]}"
            embedding = model.encode(text_to_embed).tolist()

            # Source credibility
            cursor.execute("SELECT credibility_score FROM sources WHERE name = %s", (pub_name,))
            cred_row = cursor.fetchone()
            credibility = cred_row[0] if cred_row else 50

            # Novelty
            try:
                cursor.execute("""
                    SELECT 1 - (embedding <=> %s::vector) AS sim
                    FROM articles WHERE scraped_at >= NOW() - INTERVAL '48 hours'
                    AND status = 'approved' AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector ASC LIMIT 1
                """, (embedding, embedding))
                row = cursor.fetchone()
                novelty = max(0, min(100, (1.0 - float(row[0])) * 100)) if row and row[0] else 100.0
            except Exception:
                cursor.connection.rollback()
                novelty = 100.0

            # Composite score
            auto_score = round(q_composite * 0.70 + credibility * 0.20 + novelty * 0.10, 2)

            # Tier 1 summary: Groq Llama for ALL articles (cheap)
            if content and len(content.strip()) > 50:
                summary = _generate_groq_summary(headline_en, content)
                if not summary:
                    summary = headline_en
                stats["groq_summarized"] = stats.get("groq_summarized", 0) + 1
            else:
                summary = headline_en

            # Extract sub_category and language from classification
            sub_category = q_data.get('sub_category', None)
            content_language = q_data.get('language', 'en')

            # Update article
            cursor.execute("""
                UPDATE articles SET
                    status = 'pending',
                    headline_en = %s, summary = %s, summary_long = %s,
                    category = %s, sub_category = %s, embedding = %s,
                    confidence_score = %s, auto_approval_score = %s,
                    significance_score = %s, impact_score = %s,
                    novelty_score_v2 = %s, relevance_score_v2 = %s, depth_score = %s,
                    country_codes = %s, region = %s, content_language = %s
                WHERE id = %s
            """, (
                headline_en, summary, summary,
                category, sub_category, embedding,
                q_composite, auto_score,
                q1, q2, q3, q4, q5,
                country_codes if country_codes else None, region,
                content_language, article_id,
            ))
            cursor.connection.commit()

            # Store entities from classification
            entities_data = q_data.get('entities', [])
            if entities_data:
                entities_stored = _store_entities(cursor, article_id, entities_data)
                cursor.connection.commit()
                stats["entities_stored"] = stats.get("entities_stored", 0) + entities_stored

            stats["processed"] += 1
            stats["_scored_ids"].append(article_id)

            logger.info(
                f"Scored #{article_id}: '{headline_en[:50]}' | "
                f"Q:{q_composite} Auto:{auto_score} | "
                f"Q1:{q1} Q2:{q2} Q3:{q3} Q4:{q4} Q5:{q5} | "
                f"Entities:{len(entities_data)}"
            )

        except Exception as e:
            cursor.connection.rollback()
            logger.error(f"Error scoring #{article_id}: {e}")
            stats["errors"] += 1
            stats["processed"] += 1

    # Auto-approve and auto-reject — only articles scored in THIS run
    try:
        scored_ids = [aid for aid in stats.get("_scored_ids", [])]
        if scored_ids:
            cursor.execute("""
                UPDATE articles SET status = 'approved'
                WHERE id = ANY(%s) AND status = 'pending' AND auto_approval_score >= 75
            """, (scored_ids,))
            approved = cursor.rowcount
            cursor.execute("""
                UPDATE articles SET status = 'rejected'
                WHERE id = ANY(%s) AND status = 'pending' AND auto_approval_score < 40
            """, (scored_ids,))
            rejected_extra = cursor.rowcount
        else:
            # Fallback: approve/reject from last 6 hours only
            cursor.execute("""
                UPDATE articles SET status = 'approved'
                WHERE status = 'pending' AND auto_approval_score >= 75
                AND scraped_at >= NOW() - INTERVAL '6 hours'
            """)
            approved = cursor.rowcount
            cursor.execute("""
                UPDATE articles SET status = 'rejected'
                WHERE status = 'pending' AND auto_approval_score < 40
                AND scraped_at >= NOW() - INTERVAL '6 hours'
            """)
            rejected_extra = cursor.rowcount
        cursor.connection.commit()
        stats["auto_approved"] = approved
        stats["auto_approved"] = approved
        stats["auto_rejected_extra"] = rejected_extra
        logger.info(f"Auto-approve: {approved} approved (75+), {rejected_extra} rejected (<40)")

        # Tier 2: Haiku summary upgrade for approved articles ONLY
        if approved > 0:
            logger.info(f"Upgrading {approved} approved articles with Haiku summaries...")
            cursor.execute("""
                SELECT id, headline_en, full_content, summary
                FROM articles
                WHERE status = 'approved'
                  AND id = ANY(%s)
            """, (scored_ids if scored_ids else [],))
            approved_articles = [dict(row) for row in cursor.fetchall()]

            haiku_upgraded = 0
            for art in approved_articles:
                art_content = art.get('full_content') or art.get('summary') or ''
                if art_content and len(art_content.strip()) > 50:
                    haiku_summary = _generate_haiku_summary(
                        art['headline_en'] or '', art_content
                    )
                    if haiku_summary:
                        cursor.execute("""
                            UPDATE articles SET summary = %s, summary_long = %s
                            WHERE id = %s
                        """, (haiku_summary, haiku_summary, art['id']))
                        haiku_upgraded += 1

            cursor.connection.commit()
            stats["haiku_upgraded"] = haiku_upgraded
            logger.info(f"Haiku upgrade: {haiku_upgraded}/{approved} articles")

    except Exception as e:
        cursor.connection.rollback()
        logger.error(f"Auto-approve/Haiku upgrade failed: {e}")

    # Clean internal tracking before returning
    scored_count = len(stats.get("_scored_ids", []))
    stats.pop("_scored_ids", None)

    logger.info(f"Scoring complete: {stats}")

    # Send Telegram report to owner
    _send_pipeline_report(stats)

    return stats


def _send_pipeline_report(stats: dict):
    """Send pipeline completion report to owner via Telegram DM."""
    try:
        import requests as http_req
        from datetime import datetime
        from zoneinfo import ZoneInfo

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        owner_id = os.getenv("OWNER_TELEGRAM_ID", "5378505717")
        if not bot_token or not owner_id:
            return

        now = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p EDT")
        date = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")

        processed = stats.get("processed", 0)
        classified = stats.get("groq_classified", 0)
        groq_summarized = stats.get("groq_summarized", 0)
        haiku_upgraded = stats.get("haiku_upgraded", 0)
        entities_stored = stats.get("entities_stored", 0)
        rejected = stats.get("keyword_rejected", 0)
        approved = stats.get("auto_approved", 0)
        rejected_extra = stats.get("auto_rejected_extra", 0)
        errors = stats.get("errors", 0)

        pending = processed - rejected - approved - rejected_extra - errors
        if pending < 0:
            pending = 0

        report = (
            f"📊 *GeoMemo Pipeline Report*\n"
            f"📅 {date} — {now}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 Processed: {processed}\n"
            f"🤖 Classified (Groq): {classified}\n"
            f"📝 Summarized (Groq): {groq_summarized}\n"
            f"✨ Upgraded (Haiku): {haiku_upgraded}\n"
            f"🏷️ Entities extracted: {entities_stored}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Approved (75+): {approved}\n"
            f"⏳ Pending (40-74): {pending}\n"
            f"❌ Rejected (<40): {rejected + rejected_extra}\n"
            f"🚫 Keyword filtered: {rejected}\n"
        )

        if errors > 0:
            report += f"⚠️ Errors: {errors}\n"

        report += (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Website updated | Ready for newsletter"
        )

        http_req.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={
                "chat_id": owner_id,
                "text": report,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"Telegram report failed: {e}")


def reset_articles_for_rescoring(cursor, since_date='2026-04-01'):
    """Reset all scored/rejected articles back to 'unscored' for re-scoring."""
    cursor.execute("""
        UPDATE articles SET
            status = 'unscored',
            headline_en = NULL, summary = NULL, summary_long = NULL,
            category = 'Other', embedding = NULL,
            confidence_score = 0, auto_approval_score = 0,
            significance_score = 0, impact_score = 0,
            novelty_score_v2 = 0, relevance_score_v2 = 0, depth_score = 0,
            country_codes = NULL, region = NULL
        WHERE scraped_at > %s::date
        RETURNING id
    """, (since_date,))
    count = len(cursor.fetchall())
    cursor.connection.commit()
    logger.info(f"Reset {count} articles to 'unscored' for re-scoring")
    return count
