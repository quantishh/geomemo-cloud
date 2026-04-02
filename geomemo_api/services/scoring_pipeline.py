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

def _classify_article(headline, content):
    """Q1-Q5 classification via Groq. Returns dict."""
    groq = _get_groq()
    system_prompt = """You are a geopolitical intelligence analyst for GeoMemo.
Evaluate this article on 5 independent criteria. Answer YES or NO for each.

Q1 - GEOPOLITICAL SIGNIFICANCE: Does this describe a significant geopolitical development?
  Significant = new policy, military escalation/de-escalation, treaty, regime change,
  sanctions, territorial dispute, alliance shift, election outcome with policy implications,
  major natural disaster at national scale.
  NOT significant = routine daily casualties in ongoing conflict, courtesy diplomatic calls
  with no outcome, incremental updates, local crime, celebrity, sports, entertainment.

Q2 - GLOBAL ECONOMIC IMPACT: Does this directly affect international trade, commodity markets,
  supply chains, currency markets, central bank policy, or macroeconomic conditions?

Q3 - NOVELTY: Does this contain genuinely NEW information?
  New = first report of an event, escalation, new actor entering, quantified impact,
  policy reversal, breakthrough in negotiations.
  NOT new = rehash of yesterday's news, "conflict continues" updates, opinion/editorial
  about known events, routine status reports.

Q4 - DECISION-MAKER RELEVANCE: Would a US/European/Asian government official, institutional
  investor, or multinational business leader need to know this for decisions?

Q5 - ANALYTICAL DEPTH: Does the article provide data, named sources, expert analysis,
  historical context, or quantified impact (not just bare facts from a wire report)?

Also extract:
- category: one of [Geopolitical Conflict, Geopolitical Economics, Global Markets, International Relations, Geopolitical Politics, GeoNatDisaster, GeoLocal, Other]
- countries: list of country names mentioned or implied
- headline_en: formal English translation of headline (keep original if already English)

Return valid JSON:
{"q1": "YES or NO", "q2": "YES or NO", "q3": "YES or NO", "q4": "YES or NO", "q5": "YES or NO", "category": "...", "countries": [...], "headline_en": "..."}"""

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
    return json.loads(chat.choices[0].message.content)


def _derive_scores(q_data):
    """Returns (q1, q2, q3, q4, q5, composite)."""
    def yn(key):
        return 1 if str(q_data.get(key, "NO")).upper().startswith("YES") else 0
    q1, q2, q3, q4, q5 = yn("q1"), yn("q2"), yn("q3"), yn("q4"), yn("q5")
    composite = q1 * 30 + q2 * 25 + q3 * 20 + q4 * 20 + q5 * 5
    return q1, q2, q3, q4, q5, composite


# =========================================
# HAIKU SUMMARY
# =========================================

def _generate_summary(headline, content):
    """Generate 40-60 word summary via Haiku. Always produces output."""
    client = _get_anthropic()
    if not client:
        return None

    # Build the best possible context
    parts = [f"Headline: {headline}"]
    if content and len(content.strip()) > 50:
        parts.append(f"Content: {content[:4000]}")

    article_text = "\n".join(parts)

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": f"""Write a 2-3 sentence news summary (40-60 words) in English.
Authoritative analytical tone for investment bankers and geopolitical analysts.
Sentence 1: Core development with specific actors (names, countries, organizations).
Sentence 2: Quantify with numbers, figures, or dollar amounts from the article if available.
ONLY add a 3rd sentence if the article contains a concrete forward-looking fact (a date, deadline, vote, named action).
NEVER end with speculative 'this may impact...' or 'this could lead to...' statements.
NEVER invent or hallucinate details not in the source.
If the headline is in a non-English language, translate it and summarize in English.
You MUST always produce a summary — never refuse or ask for more information.

{article_text}"""
            }]
        )
        return msg.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Haiku summary failed: {e}")
        return None


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

            # Haiku summary
            summary = _generate_summary(headline_en, content)
            if not summary:
                summary = content[:200].strip() if content else headline_en
            stats["haiku_summarized"] += 1

            # Update article
            cursor.execute("""
                UPDATE articles SET
                    status = 'pending',
                    headline_en = %s, summary = %s, summary_long = %s,
                    category = %s, embedding = %s,
                    confidence_score = %s, auto_approval_score = %s,
                    significance_score = %s, impact_score = %s,
                    novelty_score_v2 = %s, relevance_score_v2 = %s, depth_score = %s,
                    country_codes = %s, region = %s
                WHERE id = %s
            """, (
                headline_en, summary, summary,
                category, embedding,
                q_composite, auto_score,
                q1, q2, q3, q4, q5,
                country_codes if country_codes else None, region,
                article_id,
            ))
            cursor.connection.commit()
            stats["processed"] += 1

            logger.info(
                f"Scored #{article_id}: '{headline_en[:50]}' | "
                f"Q:{q_composite} Auto:{auto_score} | "
                f"Q1:{q1} Q2:{q2} Q3:{q3} Q4:{q4} Q5:{q5}"
            )

        except Exception as e:
            cursor.connection.rollback()
            logger.error(f"Error scoring #{article_id}: {e}")
            stats["errors"] += 1
            stats["processed"] += 1

    logger.info(f"Scoring complete: {stats}")
    return stats
