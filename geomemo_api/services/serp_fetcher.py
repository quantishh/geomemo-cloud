"""
SERP API Google News Fetcher
Searches Google News via SerpAPI for geopolitical articles.
Supplements RSS feeds with content from major publications.
"""
import json
import logging
import os
import time
import requests
from datetime import datetime
from urllib.parse import quote_plus

import psycopg2.extras

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

# =========================================
# SEED QUERIES — comprehensive geopolitical coverage
# =========================================

SEED_QUERIES = [
    # --- LAYER 1: Country-specific (top geopolitical countries) ---
    # Format: "Country" + broad geopolitical terms
    # Each query targets one country's geopolitical activity

    # Middle East & Central Asia
    {"query": "Iran sanctions military nuclear diplomacy", "category": "country", "target_country": "IR"},
    {"query": "Israel Gaza security defense diplomacy", "category": "country", "target_country": "IL"},
    {"query": "Saudi Arabia OPEC oil economy foreign policy", "category": "country", "target_country": "SA"},
    {"query": "Turkey NATO Erdogan foreign policy", "category": "country", "target_country": "TR"},
    {"query": "UAE economy trade investment diplomacy", "category": "country", "target_country": "AE"},
    {"query": "Iraq conflict security reconstruction", "category": "country", "target_country": "IQ"},
    {"query": "Syria conflict reconstruction sanctions", "category": "country", "target_country": "SY"},
    {"query": "Yemen Houthis conflict Red Sea shipping", "category": "country", "target_country": "YE"},
    {"query": "Qatar diplomacy LNG energy foreign policy", "category": "country", "target_country": "QA"},
    {"query": "Afghanistan Taliban security humanitarian", "category": "country", "target_country": "AF"},

    # Asia-Pacific
    {"query": "China trade military Taiwan technology", "category": "country", "target_country": "CN"},
    {"query": "Japan defense economy trade alliance", "category": "country", "target_country": "JP"},
    {"query": "India foreign policy defense economy trade", "category": "country", "target_country": "IN"},
    {"query": "South Korea security economy North Korea", "category": "country", "target_country": "KR"},
    {"query": "North Korea nuclear missiles sanctions", "category": "country", "target_country": "KP"},
    {"query": "Taiwan China military semiconductor", "category": "country", "target_country": "TW"},
    {"query": "Pakistan military diplomacy economy security", "category": "country", "target_country": "PK"},
    {"query": "Australia defense trade China alliance", "category": "country", "target_country": "AU"},
    {"query": "Philippines South China Sea defense", "category": "country", "target_country": "PH"},
    {"query": "Indonesia economy trade ASEAN foreign policy", "category": "country", "target_country": "ID"},
    {"query": "Vietnam trade economy supply chain", "category": "country", "target_country": "VN"},
    {"query": "Myanmar conflict humanitarian crisis", "category": "country", "target_country": "MM"},

    # Europe
    {"query": "Russia Ukraine sanctions NATO military", "category": "country", "target_country": "RU"},
    {"query": "Ukraine war defense reconstruction aid", "category": "country", "target_country": "UA"},
    {"query": "Germany economy defense NATO energy", "category": "country", "target_country": "DE"},
    {"query": "France foreign policy defense Macron", "category": "country", "target_country": "FR"},
    {"query": "United Kingdom trade defense foreign policy", "category": "country", "target_country": "GB"},
    {"query": "Poland NATO defense security Eastern Europe", "category": "country", "target_country": "PL"},

    # Americas
    {"query": "United States foreign policy defense trade", "category": "country", "target_country": "US"},
    {"query": "Brazil economy trade BRICS commodities", "category": "country", "target_country": "BR"},
    {"query": "Mexico trade economy security border", "category": "country", "target_country": "MX"},
    {"query": "Argentina economy IMF trade Milei", "category": "country", "target_country": "AR"},
    {"query": "Venezuela sanctions oil political crisis", "category": "country", "target_country": "VE"},
    {"query": "Colombia security peace trade", "category": "country", "target_country": "CO"},
    {"query": "Cuba sanctions economy diplomacy", "category": "country", "target_country": "CU"},

    # Africa
    {"query": "Nigeria security economy oil conflict", "category": "country", "target_country": "NG"},
    {"query": "South Africa economy BRICS trade policy", "category": "country", "target_country": "ZA"},
    {"query": "Egypt economy Suez Canal diplomacy", "category": "country", "target_country": "EG"},
    {"query": "Ethiopia conflict economy dam Nile", "category": "country", "target_country": "ET"},
    {"query": "Sudan conflict humanitarian crisis", "category": "country", "target_country": "SD"},
    {"query": "Libya conflict oil reconstruction", "category": "country", "target_country": "LY"},

    # --- LAYER 2: Topic-based (cross-country) ---

    # Energy & Commodities
    {"query": "OPEC oil production supply cuts prices", "category": "topic", "target_country": None},
    {"query": "natural gas LNG energy crisis pipeline", "category": "topic", "target_country": None},
    {"query": "Strait of Hormuz shipping oil tanker", "category": "topic", "target_country": None},
    {"query": "critical minerals rare earth supply chain", "category": "topic", "target_country": None},
    {"query": "lithium cobalt mining supply chain electric vehicle", "category": "topic", "target_country": None},

    # Security & Defense
    {"query": "NATO defense spending military alliance", "category": "topic", "target_country": None},
    {"query": "nuclear weapons proliferation IAEA treaty", "category": "topic", "target_country": None},
    {"query": "cybersecurity attack infrastructure state-sponsored", "category": "topic", "target_country": None},
    {"query": "arms deal military export defense contract", "category": "topic", "target_country": None},
    {"query": "terrorism counterterrorism security threat", "category": "topic", "target_country": None},

    # Trade & Economics
    {"query": "trade war tariffs sanctions economic", "category": "topic", "target_country": None},
    {"query": "BRICS expansion dollar alternative currency", "category": "topic", "target_country": None},
    {"query": "central bank interest rate monetary policy inflation", "category": "topic", "target_country": None},
    {"query": "supply chain disruption semiconductor chips", "category": "topic", "target_country": None},
    {"query": "World Bank IMF economic forecast developing", "category": "topic", "target_country": None},

    # Technology & AI Geopolitics
    {"query": "artificial intelligence geopolitical risk regulation", "category": "topic", "target_country": None},
    {"query": "AI chip export controls technology war", "category": "topic", "target_country": None},
    {"query": "tech decoupling China United States semiconductor", "category": "topic", "target_country": None},

    # Crypto & Digital Finance
    {"query": "cryptocurrency regulation CBDC digital currency geopolitics", "category": "topic", "target_country": None},
    {"query": "bitcoin reserve strategic national crypto policy", "category": "topic", "target_country": None},

    # Climate & Natural Disasters
    {"query": "climate change migration displacement food security", "category": "topic", "target_country": None},
    {"query": "natural disaster earthquake hurricane flood humanitarian", "category": "topic", "target_country": None},
    {"query": "drought crop failure food crisis famine", "category": "topic", "target_country": None},
    {"query": "renewable energy transition solar wind geopolitics", "category": "topic", "target_country": None},

    # International Relations
    {"query": "United Nations Security Council resolution vote", "category": "topic", "target_country": None},
    {"query": "G7 G20 summit geopolitics economy", "category": "topic", "target_country": None},
    {"query": "EU European Union foreign policy sanctions", "category": "topic", "target_country": None},
    {"query": "ASEAN Indo-Pacific security trade", "category": "topic", "target_country": None},
    {"query": "African Union conflict peacekeeping development", "category": "topic", "target_country": None},

    # Global Markets
    {"query": "global stock market crash rally volatility geopolitics", "category": "topic", "target_country": None},
    {"query": "oil price crude Brent WTI energy market", "category": "topic", "target_country": None},
    {"query": "gold price commodity metals safe haven", "category": "topic", "target_country": None},

    # --- LAYER 3: Publication-specific ---
    {"query": "site:reuters.com geopolitics conflict sanctions trade", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:ft.com geopolitics economy markets trade", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:economist.com geopolitics economy", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:washingtonpost.com foreign policy defense", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:bloomberg.com geopolitics markets economy", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:wsj.com geopolitics trade economy", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:nytimes.com foreign policy conflict diplomacy", "category": "publication", "target_country": None, "frequency": "4h"},

    # Think tanks
    {"query": "site:brookings.edu geopolitics analysis", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:cfr.org foreign policy analysis", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:carnegieendowment.org geopolitics", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:csis.org defense security analysis", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:chathamhouse.org international affairs", "category": "publication", "target_country": None, "frequency": "4h"},
    {"query": "site:rand.org defense security policy", "category": "publication", "target_country": None, "frequency": "4h"},
]


# =========================================
# SERP API FETCH
# =========================================

def _fetch_google_news(query: str, max_results: int = 20) -> list:
    """Search Google News via SerpAPI. Returns list of article dicts."""
    if not SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not set")
        return []

    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_news",
                "q": query,
                "gl": "us",
                "hl": "en",
                "api_key": SERPAPI_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        articles = []
        # Google News results come in news_results
        for item in data.get("news_results", [])[:max_results]:
            # Handle both flat results and clustered results
            if "stories" in item:
                # Clustered result — extract individual stories
                for story in item["stories"][:3]:
                    articles.append(_parse_news_item(story))
            else:
                articles.append(_parse_news_item(item))

        return [a for a in articles if a.get("url")]

    except requests.exceptions.RequestException as e:
        logger.error(f"SERP API error for '{query[:40]}': {e}")
        return []
    except Exception as e:
        logger.error(f"SERP fetch unexpected error: {e}")
        return []


def _parse_news_item(item: dict) -> dict:
    """Parse a single Google News result into article dict."""
    url = item.get("link", "")
    # Resolve Google News redirect URLs to actual article URLs
    if url and 'news.google.com' in url:
        url = _resolve_google_redirect(url) or url
    return {
        "headline": item.get("title", ""),
        "url": url,
        "publication_name": item.get("source", {}).get("name", "") if isinstance(item.get("source"), dict) else item.get("source", ""),
        "description": item.get("snippet", ""),
        "og_image": item.get("thumbnail", ""),
        "scraped_at": item.get("date", ""),
    }


def _resolve_google_redirect(google_url: str) -> str:
    """Follow Google News redirect to get the actual article URL."""
    try:
        resp = requests.head(google_url, allow_redirects=True, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GeoMemoBot/2.0)"
        })
        final_url = resp.url
        if final_url and 'news.google.com' not in final_url:
            return final_url
    except Exception:
        pass
    # Fallback: try GET with redirect follow
    try:
        resp = requests.get(google_url, allow_redirects=True, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GeoMemoBot/2.0)"
        }, stream=True)
        final_url = resp.url
        resp.close()
        if final_url and 'news.google.com' not in final_url:
            return final_url
    except Exception:
        pass
    return None


# =========================================
# SEED QUERIES INTO DB
# =========================================

def seed_serp_queries(cursor):
    """Insert seed queries into serp_queries table if empty."""
    cursor.execute("SELECT COUNT(*) FROM serp_queries")
    count = cursor.fetchone()[0]
    if count > 0:
        logger.info(f"SERP queries already seeded ({count} queries)")
        return count

    for q in SEED_QUERIES:
        cursor.execute("""
            INSERT INTO serp_queries (query, category, target_country, frequency, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT DO NOTHING
        """, (q["query"], q.get("category", "country"),
              q.get("target_country"), q.get("frequency", "4h")))

    cursor.connection.commit()
    logger.info(f"Seeded {len(SEED_QUERIES)} SERP queries")
    return len(SEED_QUERIES)


# =========================================
# MAIN FETCH PIPELINE
# =========================================

def run_serp_fetch(cursor, frequency_filter: str = "4h", max_results_per_query: int = 15) -> dict:
    """
    Run SERP API fetch for all active queries matching the frequency.
    Inserts new articles as 'unscored'.
    Returns stats dict.
    """
    if not SERPAPI_KEY:
        return {"error": "SERPAPI_KEY not configured", "fetched": 0}

    # Seed queries if needed
    seed_serp_queries(cursor)

    # Fetch active queries matching frequency
    cursor.execute("""
        SELECT id, query, category, target_country
        FROM serp_queries
        WHERE is_active = TRUE AND frequency = %s
        ORDER BY last_run_at ASC NULLS FIRST
    """, (frequency_filter,))
    queries = [dict(row) for row in cursor.fetchall()]

    if not queries:
        return {"message": "No queries to run", "fetched": 0}

    stats = {
        "queries_run": 0,
        "articles_found": 0,
        "articles_inserted": 0,
        "duplicates_skipped": 0,
        "errors": 0,
    }

    for q in queries:
        query_text = q["query"]
        logger.info(f"SERP fetch: '{query_text[:50]}' ({q['category']})")

        try:
            articles = _fetch_google_news(query_text, max_results=max_results_per_query)
            stats["articles_found"] += len(articles)

            for art in articles:
                if not art.get("url") or not art.get("headline"):
                    continue

                try:
                    cursor.execute("""
                        INSERT INTO articles
                        (url, headline, publication_name, summary, category,
                         status, scraped_at, og_image, content_source)
                        VALUES (%s, %s, %s, %s, 'Other',
                                'unscored', NOW(), %s, 'serp')
                        ON CONFLICT (url) DO NOTHING
                    """, (
                        art["url"],
                        art["headline"],
                        art.get("publication_name", ""),
                        art.get("description", "")[:500],
                        art.get("og_image", ""),
                    ))

                    if cursor.rowcount > 0:
                        stats["articles_inserted"] += 1
                    else:
                        stats["duplicates_skipped"] += 1

                except Exception as e:
                    logger.debug(f"Insert error: {e}")
                    cursor.connection.rollback()
                    stats["errors"] += 1

            # Update query stats
            cursor.execute("""
                UPDATE serp_queries
                SET last_run_at = NOW(), results_found = %s
                WHERE id = %s
            """, (len(articles), q["id"]))
            cursor.connection.commit()

            stats["queries_run"] += 1
            time.sleep(1)  # Rate limit between queries

        except Exception as e:
            logger.error(f"SERP query failed: {e}")
            cursor.connection.rollback()
            stats["errors"] += 1

    # After inserting, fetch full content for new SERP articles
    if stats["articles_inserted"] > 0:
        logger.info(f"Fetching content for {stats['articles_inserted']} new SERP articles...")
        content_stats = fetch_content_for_serp_articles(cursor, limit=stats["articles_inserted"])
        stats["content_fetched"] = content_stats.get("fetched", 0)
        stats["content_failed"] = content_stats.get("failed", 0)

    logger.info(f"SERP fetch complete: {stats}")
    return stats


# =========================================
# CONTENT FETCH FOR SERP ARTICLES
# =========================================

def fetch_content_for_serp_articles(cursor, limit=500) -> dict:
    """
    Fetch full article content for SERP articles that have no full_content.
    Uses direct HTTP + BrightData WebUnlocker fallback.
    """
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura not installed, skipping content fetch")
        return {"fetched": 0, "failed": 0}

    cursor.execute("""
        SELECT id, url, publication_name
        FROM articles
        WHERE content_source = 'serp'
          AND (full_content IS NULL OR length(full_content) < 50)
          AND status = 'unscored'
        ORDER BY id DESC
        LIMIT %s
    """, (limit,))
    articles = [dict(row) for row in cursor.fetchall()]

    if not articles:
        return {"fetched": 0, "failed": 0}

    stats = {"fetched": 0, "failed": 0}

    # Think tank domains that need WebUnlocker
    think_tank_domains = [
        "chathamhouse.org", "rusi.org", "csis.org", "brookings.edu",
        "cfr.org", "rand.org", "carnegieendowment.org", "atlanticcouncil.org",
        "iiss.org", "piie.com", "foreignaffairs.com", "crisisgroup.org",
    ]

    api_key = os.getenv("BRIGHTDATA_WEBUNLOCKER_API_KEY", "")
    zone = os.getenv("BRIGHTDATA_WEBUNLOCKER_ZONE", "web_unlocker1")

    for art in articles:
        url = art["url"]
        article_id = art["id"]

        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower().replace('www.', '')
            is_think_tank = any(td in domain for td in think_tank_domains)

            content = None
            source = 'serp'

            # Step 1: Direct fetch (unless think tank)
            if not is_think_tank:
                try:
                    resp = requests.get(url, timeout=10, headers={
                        "User-Agent": "Mozilla/5.0 (compatible; GeoMemoBot/2.0)"
                    })
                    if resp.status_code == 200:
                        extracted = trafilatura.extract(resp.text, include_comments=False)
                        if extracted and len(extracted) >= 300:
                            content = extracted[:15000]
                            source = 'direct'
                except Exception:
                    pass

            # Step 2: WebUnlocker fallback
            if not content and api_key:
                try:
                    resp = requests.post(
                        "https://api.brightdata.com/request",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {api_key}",
                        },
                        json={"zone": zone, "url": url, "format": "raw"},
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        extracted = trafilatura.extract(resp.text, include_comments=False)
                        if extracted and len(extracted) >= 200:
                            content = extracted[:15000]
                            source = 'webunlocker'
                except Exception:
                    pass

            # Update article
            if content:
                cursor.execute("""
                    UPDATE articles SET full_content = %s, content_source = %s
                    WHERE id = %s
                """, (content, source, article_id))
                cursor.connection.commit()
                stats["fetched"] += 1
            else:
                stats["failed"] += 1

            time.sleep(0.5)  # Rate limit

        except Exception as e:
            logger.debug(f"Content fetch failed for #{article_id}: {e}")
            cursor.connection.rollback()
            stats["failed"] += 1

    logger.info(f"Content fetch for SERP articles: {stats}")
    return stats
