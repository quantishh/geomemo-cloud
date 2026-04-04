# GeoMemo Intelligence Database Architecture
## Building the World's Best Publicly Available Intelligence Dataset

> Vision: A structured, queryable, real-time intelligence database that powers
> country factsheets, risk assessments, analytical reports, and API subscriptions.
> Built on daily ingestion of 5,000+ articles from 250+ sources across 145 countries,
> enriched with entity extraction, economic indicators, bilateral relations, and
> sentiment analysis.

---

## 1. Architecture Overview

```
DATA SOURCES                    PIPELINES                      INTELLIGENCE DB                 PRODUCTS
─────────────                   ─────────                      ───────────────                 ────────
RSS Feeds (250+)  ──┐
SERP API (85 queries)──┤     Pipeline 1: Newsletter           articles ──────────┐            Newsletter
BrightData WebUnlocker─┤     (every 4 hours, real-time)       ├── full_content   │            Website
                       ├──→  Scrape → Score → Approve         ├── full_content_en│            Telegram
Future Sources:        │     → Newsletter → Website           ├── embeddings     │
├── FRED API ──────────┤                                      ├── Q1-Q5 scores   │
├── World Bank API ────┤     Pipeline 2: Intelligence         │                  │
├── IMF API ───────────┤     (weekly batch, overnight)        entities ──────────┤──→  Country Factsheet
├── EIA API ───────────┤     Extract → Translate → Enrich     ├── people         │     Risk Assessments
├── UN Data ───────────┤     → Build relationships            ├── companies      │     Analytical Reports
├── OECD API ──────────┤                                      ├── commodities    │     API Subscription
├── BIS API ───────────┘     Pipeline 3: Economic Data        ├── policies       │     Entity Intelligence
                             (daily, from gov APIs)           │                  │     Bilateral Tracker
                             FRED → World Bank → IMF          economic_indicators┤     Economic Dashboard
                             → Store structured indicators    ├── GDP            │
                                                              ├── inflation      │
                                                              ├── interest_rates │
                                                              ├── trade_balance  │
                                                              │                  │
                                                              bilateral_relations┘
                                                              ├── alliances
                                                              ├── sanctions
                                                              ├── trade_deals
                                                              ├── conflicts
```

---

## 2. Database Schema

### 2.1 Core Article Store (Existing)

```sql
-- Already exists, enhanced with new columns
articles (
    id, url, headline, headline_en, summary, summary_long,
    full_content,           -- original language article body
    full_content_en,        -- NEW: English translation
    content_language,       -- NEW: detected language code (en, ar, zh, etc.)
    category, sub_category, -- NEW: sub_category for granular classification
    status, scraped_at, embedding,
    confidence_score, auto_approval_score,
    significance_score, impact_score, novelty_score_v2,
    relevance_score_v2, depth_score,
    country_codes, region, source_id, publication_name,
    content_source, og_image,
    -- clustering
    cluster_id, cluster_role, cluster_label, child_summary
)
```

### 2.2 Entity Store (NEW)

```sql
-- Master entity registry
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    -- Types: person, organization, company, military, political_party,
    --        industry, commodity, currency, crypto, stock_index, stock,
    --        exchange, treaty, policy, event, infrastructure

    sub_type TEXT,
    -- Sub-types by entity_type:
    -- person: head_of_state, minister, military_leader, ceo, analyst, activist
    -- organization: intergovernmental, ngo, think_tank, central_bank, regulator
    -- company: public, private, state_owned, startup
    -- commodity: energy, metal, agricultural, mineral
    -- currency: fiat, crypto, stablecoin, cbdc
    -- infrastructure: waterway, pipeline, port, cable, military_base

    country_code TEXT,           -- primary country association (ISO 3166-1)
    description TEXT,            -- "President of Nigeria since 2023"
    aliases TEXT[],              -- {"MBS", "Mohammed bin Salman", "Crown Prince"}
    metadata JSONB DEFAULT '{}', -- flexible: {"ticker": "AAPL", "exchange": "NASDAQ"}

    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    article_count INTEGER DEFAULT 0,
    avg_sentiment FLOAT DEFAULT 0,  -- -1.0 to 1.0 rolling average

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_entities_name_type ON entities (LOWER(name), entity_type);
CREATE INDEX idx_entities_country ON entities (country_code);
CREATE INDEX idx_entities_type ON entities (entity_type);
CREATE INDEX idx_entities_article_count ON entities (article_count DESC);

-- Article-entity relationships
CREATE TABLE article_entities (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'mentioned',
    -- Roles: subject, mentioned, quoted, target, author, source
    sentiment TEXT DEFAULT 'neutral',
    -- Sentiment: positive, negative, neutral, mixed
    context TEXT,
    -- Brief context: "imposed sanctions on", "signed trade deal with"
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(article_id, entity_id)
);

CREATE INDEX idx_article_entities_article ON article_entities (article_id);
CREATE INDEX idx_article_entities_entity ON article_entities (entity_id);
CREATE INDEX idx_article_entities_sentiment ON article_entities (sentiment);
```

### 2.3 Economic Indicators (NEW)

```sql
CREATE TABLE economic_indicators (
    id SERIAL PRIMARY KEY,
    country_code TEXT NOT NULL,          -- ISO 3166-1
    indicator_type TEXT NOT NULL,
    -- Types: gdp, gdp_growth, gdp_forecast, gdp_per_capita,
    --        inflation, cpi, ppi,
    --        interest_rate, policy_rate,
    --        unemployment, employment,
    --        trade_balance, exports, imports,
    --        fdi, fdi_inflow, fdi_outflow,
    --        debt_to_gdp, sovereign_debt, fiscal_deficit,
    --        forex_reserve, current_account,
    --        credit_rating, credit_outlook,
    --        oil_production, oil_price, gas_price,
    --        remittances, aid_received,
    --        population, poverty_rate

    value TEXT NOT NULL,                 -- "3.2%", "$1.45B", "BBB+", "hold"
    value_numeric FLOAT,                -- parsed numeric: 3.2, 1450000000
    unit TEXT,                           -- "percent", "usd_billion", "rating"
    direction TEXT,                      -- up, down, hold, stable, forecast
    period TEXT,                         -- "Q1 2026", "March 2026", "FY2027"
    previous_value TEXT,                 -- for comparison: "3.5%"

    source_type TEXT DEFAULT 'article',  -- article, api_fred, api_worldbank, api_imf
    source_org TEXT,                     -- "IMF", "Fed", "RBI", "BLS"
    article_id INTEGER REFERENCES articles(id),  -- NULL if from API
    api_series_id TEXT,                  -- FRED series ID, WB indicator code

    reported_at TIMESTAMPTZ,            -- when the data was reported
    extracted_at TIMESTAMPTZ DEFAULT NOW(),

    confidence FLOAT DEFAULT 1.0        -- 1.0 for API data, 0.7-0.9 for article-extracted
);

CREATE INDEX idx_econ_country ON economic_indicators (country_code);
CREATE INDEX idx_econ_type ON economic_indicators (indicator_type);
CREATE INDEX idx_econ_country_type ON economic_indicators (country_code, indicator_type);
CREATE INDEX idx_econ_reported ON economic_indicators (reported_at DESC);
CREATE INDEX idx_econ_source ON economic_indicators (source_type);
```

### 2.4 Bilateral Relations (NEW)

```sql
CREATE TABLE bilateral_relations (
    id SERIAL PRIMARY KEY,
    country_a TEXT NOT NULL,             -- ISO code (alphabetically first)
    country_b TEXT NOT NULL,             -- ISO code
    relation_type TEXT NOT NULL,
    -- Types: alliance, defense_pact, trade_agreement, trade_war,
    --        sanctions, sanctions_lifted, diplomatic_ties, diplomatic_break,
    --        military_conflict, ceasefire, peace_deal,
    --        investment, aid, joint_venture,
    --        territorial_dispute, maritime_dispute,
    --        intelligence_sharing, extradition

    status TEXT DEFAULT 'active',        -- active, resolved, escalating, de-escalating
    event_summary TEXT,                  -- "US imposed 100% tariff on CN pharmaceuticals"
    significance_score INTEGER,          -- 1-10 scale

    article_id INTEGER REFERENCES articles(id),
    extracted_at TIMESTAMPTZ DEFAULT NOW(),

    started_at TIMESTAMPTZ,             -- when the relation started/changed
    ended_at TIMESTAMPTZ                -- NULL if ongoing
);

CREATE INDEX idx_bilateral_countries ON bilateral_relations (country_a, country_b);
CREATE INDEX idx_bilateral_type ON bilateral_relations (relation_type);
CREATE INDEX idx_bilateral_status ON bilateral_relations (status);
```

### 2.5 Country Profiles (NEW — aggregated view)

```sql
CREATE TABLE country_profiles (
    country_code TEXT PRIMARY KEY,       -- ISO 3166-1
    country_name TEXT NOT NULL,

    -- Leadership (updated from entity extraction)
    head_of_state TEXT,
    head_of_state_entity_id INTEGER REFERENCES entities(id),
    government_type TEXT,
    political_system TEXT,

    -- Latest economic snapshot (updated weekly from indicators)
    latest_gdp TEXT,
    latest_gdp_growth TEXT,
    latest_inflation TEXT,
    latest_interest_rate TEXT,
    latest_unemployment TEXT,
    latest_credit_rating TEXT,
    latest_debt_to_gdp TEXT,

    -- Intelligence metrics (computed weekly)
    risk_score FLOAT,                    -- 0-100, computed from article signals
    stability_index FLOAT,              -- 0-100
    article_count_7d INTEGER,           -- articles in last 7 days
    article_count_30d INTEGER,
    top_categories JSONB,               -- {"Conflict": 45, "Economics": 23, ...}
    top_entities JSONB,                 -- [{"name": "Tinubu", "count": 15}, ...]
    trending_topics JSONB,              -- latest topic clusters

    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.6 API Data Sources (NEW — for gov API feeds)

```sql
CREATE TABLE api_data_sources (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,                  -- "FRED", "World Bank", "IMF"
    base_url TEXT NOT NULL,
    api_key_env TEXT,                    -- env var name for API key
    is_active BOOLEAN DEFAULT TRUE,
    last_fetched_at TIMESTAMPTZ,
    fetch_frequency TEXT DEFAULT 'daily', -- daily, weekly, monthly
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE api_series (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES api_data_sources(id),
    series_id TEXT NOT NULL,             -- "GDP", "CPIAUCSL", "NY.GDP.MKTP.CD"
    country_code TEXT,
    indicator_type TEXT,                 -- maps to economic_indicators.indicator_type
    description TEXT,
    unit TEXT,
    frequency TEXT,                      -- daily, monthly, quarterly, annual
    is_active BOOLEAN DEFAULT TRUE,
    last_value TEXT,
    last_updated TIMESTAMPTZ,
    UNIQUE(source_id, series_id)
);
```

---

## 3. Future Government API Sources

### Free APIs (No subscription required)

| Source | API | Data Available | Update Frequency |
|--------|-----|---------------|-----------------|
| **FRED** (Federal Reserve) | `api.stlouisfed.org` | US macro: GDP, CPI, unemployment, interest rates, money supply, 800K+ series | Real-time |
| **World Bank** | `api.worldbank.org` | 200+ countries: GDP, poverty, education, health, trade | Quarterly |
| **IMF** | `datahelp.imf.org` | Global: WEO forecasts, BOP, exchange rates, fiscal data | Monthly |
| **EIA** (US Energy) | `api.eia.gov` | Oil/gas production, prices, consumption, reserves | Weekly |
| **UN Data** | `data.un.org` | Demographics, migration, development indicators | Annual |
| **OECD** | `data.oecd.org` | 38 member countries: leading indicators, trade, productivity | Monthly |
| **BIS** (Bank for Intl Settlements) | `data.bis.org` | Global banking, credit, forex, property prices | Quarterly |
| **ECB** (European Central Bank) | `sdw.ecb.europa.eu` | Eurozone: rates, money supply, bank lending | Daily |
| **COMTRADE** (UN Trade) | `comtradeapi.un.org` | Bilateral trade flows for all countries | Monthly |
| **Eurostat** | `ec.europa.eu/eurostat` | EU27: economics, demographics, energy | Monthly |
| **USGS** | `earthquake.usgs.gov` | Seismic data, mineral resources | Real-time |
| **NASA FIRMS** | `firms.modaps.eosdis.nasa.gov` | Fire/thermal hotspots globally | Real-time |

### Data Integration Pattern

```python
# Example: FRED API integration
class FREDFetcher:
    BASE_URL = "https://api.stlouisfed.org/fred"

    SERIES = {
        "GDP":          {"id": "GDP",         "country": "US", "type": "gdp"},
        "CPI":          {"id": "CPIAUCSL",    "country": "US", "type": "inflation"},
        "FED_RATE":     {"id": "FEDFUNDS",    "country": "US", "type": "interest_rate"},
        "UNEMPLOYMENT": {"id": "UNRATE",      "country": "US", "type": "unemployment"},
        "10Y_YIELD":    {"id": "DGS10",       "country": "US", "type": "bond_yield"},
        "OIL_WTI":      {"id": "DCOILWTICO",  "country": "US", "type": "oil_price"},
        "GOLD":         {"id": "GOLDAMGBD228NLBM", "country": None, "type": "commodity_price"},
    }

    def fetch_and_store(self, cursor):
        for label, config in self.SERIES.items():
            data = self._fetch_series(config["id"])
            cursor.execute("""
                INSERT INTO economic_indicators
                (country_code, indicator_type, value, value_numeric, source_type,
                 source_org, api_series_id, reported_at)
                VALUES (%s, %s, %s, %s, 'api_fred', 'Federal Reserve', %s, %s)
            """, (...))
```

---

## 4. Pipeline Details

### Pipeline 1: Newsletter (existing, every 4 hours)

No changes except two-tier summaries:
```
Scrape → Score (Groq Q1-Q5) → Groq Llama summary (all)
→ Auto-approve → Haiku summary upgrade (approved only)
→ Newsletter → Website → Telegram
```

### Pipeline 2: Intelligence Extraction (NEW, weekly batch)

```python
def weekly_intelligence_extraction():
    """
    Runs Sunday 2 AM EDT. Processes all articles from the past week.
    Extracts entities, economic indicators, bilateral relations.
    Translates non-English content.
    """

    # Step 1: Get all articles from last 7 days (ALL statuses)
    articles = get_articles_since(days=7)
    # ~20,000-25,000 articles

    # Step 2: Entity extraction (Groq Llama, 5 concurrent)
    for batch in chunks(articles, 5):
        results = parallel_extract_entities(batch)
        store_entities(results)
    # Prompt: "Extract all named entities from this article.
    #          Return: people (name, title, country), organizations,
    #          companies, commodities, currencies, policies mentioned."

    # Step 3: Economic indicator extraction
    econ_articles = [a for a in articles if a.category in
                     ('Geopolitical Economics', 'Global Markets')]
    for article in econ_articles:
        indicators = extract_indicators(article)
        store_indicators(indicators)
    # Prompt: "Extract any economic data points: GDP, inflation,
    #          interest rates, trade figures, with country, value,
    #          direction, period, and source organization."

    # Step 4: Bilateral relations
    multi_country = [a for a in articles if len(a.country_codes) >= 2]
    for article in multi_country:
        relations = extract_relations(article)
        store_relations(relations)

    # Step 5: Content translation (non-English)
    non_english = [a for a in articles
                   if a.content_language != 'en' and a.full_content]
    for article in non_english:
        translated = groq_translate(article.full_content)
        update_full_content_en(article.id, translated)

    # Step 6: Entity enrichment
    consolidate_aliases()           # merge "MBS" + "Mohammed bin Salman"
    update_entity_counts()          # recalculate article_count
    update_sentiment_averages()     # rolling sentiment per entity
    update_country_profiles()       # refresh country_profiles table

    # Step 7: Send completion report
    send_telegram_report(stats)
```

### Pipeline 3: Economic Data (NEW, daily from APIs)

```python
def daily_economic_data_fetch():
    """
    Runs daily at 6 AM EDT. Fetches latest data from government APIs.
    """
    fetchers = [
        FREDFetcher(),       # US macro data
        WorldBankFetcher(),  # Global development indicators
        EIAFetcher(),        # Energy data
        # IMFFetcher(),      # Add when ready
        # OECDFetcher(),     # Add when ready
    ]

    for fetcher in fetchers:
        fetcher.fetch_and_store(cursor)

    # Update country profiles with latest API data
    refresh_country_profiles()
```

---

## 5. Query Patterns (What This Enables)

### Entity Intelligence
```sql
-- "Tell me about TSMC"
SELECT e.*, COUNT(ae.id) as mentions,
       AVG(CASE WHEN ae.sentiment='positive' THEN 1
                WHEN ae.sentiment='negative' THEN -1 ELSE 0 END) as sentiment_trend
FROM entities e
JOIN article_entities ae ON e.id = ae.entity_id
WHERE e.name ILIKE '%TSMC%'
GROUP BY e.id;

-- Related entities (who appears in the same articles)
SELECT e2.name, e2.entity_type, COUNT(*) as co_occurrences
FROM article_entities ae1
JOIN article_entities ae2 ON ae1.article_id = ae2.article_id AND ae1.entity_id != ae2.entity_id
JOIN entities e2 ON ae2.entity_id = e2.id
WHERE ae1.entity_id = (SELECT id FROM entities WHERE name = 'TSMC')
GROUP BY e2.id, e2.name, e2.entity_type
ORDER BY co_occurrences DESC LIMIT 20;
```

### Country Economic Profile
```sql
-- "India economic snapshot"
SELECT indicator_type, value, direction, period, source_org, reported_at
FROM economic_indicators
WHERE country_code = 'IN'
  AND indicator_type IN ('gdp_growth', 'inflation', 'interest_rate', 'unemployment')
ORDER BY indicator_type, reported_at DESC;
```

### Bilateral Tracker
```sql
-- "US-China relations timeline"
SELECT event_summary, relation_type, status, extracted_at
FROM bilateral_relations
WHERE (country_a = 'CN' AND country_b = 'US')
   OR (country_a = 'US' AND country_b = 'CN')
ORDER BY extracted_at DESC;
```

### Risk Assessment
```sql
-- "Countries with highest abduction incidents"
SELECT a.country_codes, COUNT(*) as incidents
FROM articles a
JOIN article_entities ae ON a.id = ae.article_id
JOIN entities e ON ae.entity_id = e.id
WHERE a.full_content_en ILIKE '%abduct%' OR a.full_content_en ILIKE '%kidnap%'
GROUP BY a.country_codes
ORDER BY incidents DESC;
```

### Report Generation
```sql
-- "All signals about Iran war this week"
SELECT a.headline_en, a.summary, a.publication_name, a.scraped_at,
       a.auto_approval_score, a.category, a.sub_category
FROM articles a
WHERE 'IR' = ANY(a.country_codes)
  AND a.scraped_at > NOW() - INTERVAL '7 days'
  AND a.category IN ('Geopolitical Conflict', 'International Relations')
ORDER BY a.scraped_at DESC;
-- Feed results to Claude for structured 5-page report
```

---

## 6. Technology Stack for Scale

### Current (sufficient for 1-2 years)
- PostgreSQL 15 + pgvector (articles + embeddings)
- Groq Llama 3.3 (classification + entity extraction)
- Claude Haiku (quality summaries)
- Sentence Transformers (embeddings)
- FastAPI (API layer)

### Future Scale (when data > 10M articles)
- **TimescaleDB** — for time-series economic indicators (hypertables)
- **Apache Kafka** — real-time article ingestion pipeline
- **Elasticsearch** — full-text search across full_content_en
- **Neo4j** — entity relationship graph (who knows who, which companies are connected)
- **Redis** — caching for API responses and country profiles
- **Apache Airflow** — orchestrate weekly batch pipelines
- **dbt** — transform raw data into analytical models

### API Subscription Architecture (Future)
```
Free Tier:
  - Country profiles (basic)
  - Top 10 news per country
  - Weekly global risk summary

Professional ($99/month):
  - Full entity search
  - Economic indicator API
  - Bilateral relations tracker
  - Country factsheets (100+ countries)
  - Weekly reports (5 regions)

Enterprise ($499/month):
  - Full article database access
  - Custom report generation
  - Real-time entity alerts
  - Custom country watchlists
  - Bulk data export
  - Dedicated API rate limits

API Endpoints:
  GET /api/v1/entities?q=TSMC&type=company
  GET /api/v1/countries/{code}/profile
  GET /api/v1/countries/{code}/indicators
  GET /api/v1/countries/{code}/intelligence
  GET /api/v1/bilateral/{code_a}/{code_b}
  GET /api/v1/reports/weekly/{region}
  POST /api/v1/query (natural language → structured response)
```

---

## 7. Data Quality & Governance

### Deduplication
- URL-based dedup (existing)
- Entity alias consolidation (weekly)
- Economic indicator versioning (keep history, mark latest)

### Confidence Scoring
- API data: confidence = 1.0 (authoritative)
- Article-extracted indicators: confidence = 0.7-0.9
- Entity descriptions: updated when seen in 3+ sources

### Data Retention
- Articles: indefinite (the dataset grows in value)
- Economic indicators: indefinite (time-series history)
- Entity snapshots: monthly snapshots for trend analysis
- Full content: indefinite (storage is cheap)

### Privacy & Compliance
- All data from public sources (RSS, SERP, government APIs)
- No personally identifiable information beyond public figures
- Entity data limited to public roles and activities
- GDPR: no EU citizen personal data collected

---

## 8. Implementation Roadmap

### Phase 1: Foundation (This Week)
- [x] Two-tier summaries (Groq for all, Haiku for approved)
- [ ] Schema: entities, article_entities, economic_indicators, bilateral_relations
- [ ] Entity extraction in Groq Q1-Q5 call (basic: names + types)
- [ ] full_content_en column + content_language detection
- [ ] Test on sandbox

### Phase 2: Intelligence Pipeline (Next Week)
- [ ] Weekly batch extraction script
- [ ] Deep entity extraction (descriptions, roles, sentiment)
- [ ] Economic indicator extraction from articles
- [ ] Bilateral relations extraction
- [ ] Content translation pipeline
- [ ] Entity consolidation + alias merging

### Phase 3: APIs & Queries (Week 3)
- [ ] Entity search endpoint
- [ ] Country profile endpoint
- [ ] Economic indicator endpoint
- [ ] Bilateral relations endpoint
- [ ] Natural language query endpoint (RAG)

### Phase 4: Government Data (Week 4)
- [ ] FRED API integration
- [ ] World Bank API integration
- [ ] EIA API integration
- [ ] Automated country profile updates

### Phase 5: Products (Month 2)
- [ ] CIA-style country factsheet pages
- [ ] Weekly intelligence report generator
- [ ] Entity intelligence dashboard
- [ ] Risk scoring model
- [ ] API subscription framework

---

*Document created: April 4, 2026*
*Architecture designed for scale: 10M+ articles, 1M+ entities, 50K+ indicators*
*All development on `dev` branch, tested on sandbox before production*
