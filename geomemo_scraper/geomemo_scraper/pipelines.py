import psycopg2
import json
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
import logging
import os
from groq import Groq
from sentence_transformers import SentenceTransformer
from pgvector.psycopg2 import register_vector
from psycopg2 import InternalError

# Optional: pycountry for ISO country code resolution
try:
    import pycountry
except ImportError:
    pycountry = None
    logging.warning("pycountry not installed. Country code resolution will be skipped.")

# --- Load models ---
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    logging.info("Embedding model 'all-MiniLM-L6-v2' loaded successfully.")
except Exception as e:
    logging.critical(f"Failed to load SentenceTransformer model: {e}")
    raise e

try:
    groq_client = Groq()
except Exception as e:
    logging.getLogger(__name__).critical(f"Failed to initialize Groq client: {e}. Make sure GROQ_API_KEY is set.")
    raise e

class GeomemoDatabasePipeline:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.seen_urls = set()
        self.report_stats = {}
        self.logger = logging.getLogger(self.__class__.__name__)

        self.categories_list = [
            'Geopolitical Conflict', 'Geopolitical Economics', 'Global Markets',
            'Geopolitical Politics', 'GeoNatDisaster', 'GeoLocal', 'Other'
        ]
        self.valid_categories_set = set(self.categories_list)
        self.embedding_model = embedding_model

        # M2: Scoring weights
        self.scoring_weights = {
            "confidence": 0.40,
            "credibility": 0.30,
            "novelty": 0.15,
            "category_bonus": 0.15,
        }
        self.category_bonus_map = {
            'Geopolitical Conflict': 95,
            'Geopolitical Economics': 90,
            'Global Markets': 85,
            'Geopolitical Politics': 80,
            'GeoNatDisaster': 60,
            'GeoLocal': 40,
            'Other': 10,
        }
        self.repetition_threshold = 0.85
        self.default_credibility = 50

    def open_spider(self, spider):
        try:
            # --- Database connection from environment ---
            self.connection = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "db"),
                database=os.getenv("POSTGRES_DB", "postgres"),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", ""),
            )
            self.cursor = self.connection.cursor()
            register_vector(self.connection)
            self.logger.info("Database connection opened and vector type registered")
        except psycopg2.OperationalError as e:
            self.logger.critical(f"DATABASE CONNECTION FAILED: {e}")
            raise e

    def close_spider(self, spider):
        self.logger.info("--- CRAWL STATS REPORT ---")
        self.logger.info(json.dumps(self.report_stats, indent=2))
        if self.cursor: self.cursor.close()
        if self.connection: self.connection.close()
        self.logger.info("Database connection closed")

    # =========================================
    # GROQ CLASSIFICATION (M2: + country extraction)
    # =========================================

    def _get_groq_completion(self, headline: str, content_snippet: str) -> dict:
        """
        Sends the article to Groq (Llama 3) for classification.
        M2: Now also extracts country names from the article.
        """
        system_prompt = f"""
You are a top-tier geopolitical analyst for 'GeoMemo'.
Your goal is to curate high-value geopolitical news.

INSTRUCTION:
Judge this article STRICTLY based on the definitions below.
Do not use previous rejections as a guide. If it fits a category, approve it.

STEP 1: Analyze relevance based on these rules:
- `Geopolitical Conflict`: War, civil war, terrorism, defense pacts.
- `Geopolitical Politics`: NATIONAL elections/outcomes, diplomatic tensions.
- `GeoNatDisaster`: MAJOR climate disasters with international aid/impact.
- `Geopolitical Economics`: Trade wars, sanctions, economic pacts (EU, BRICS, etc).
- `Global Markets`: Major stock/commodity/currency moves driven by policy.
- `GeoLocal`: Local event with INTERNATIONAL implications.

STEP 2: Assign a CONFIDENCE SCORE (0-100).
- High Score (80-100): Fits the rules clearly.
- Low Score (0-30): Sports, Celebrity Gossip, Local Crime, or minor local news.

STEP 3: Extract ALL countries mentioned or implied in the headline and content.
Return their common English names (e.g., "United States", "China", "Russia").
If no specific country is mentioned, return an empty list.

STEP 4: Output valid JSON:
{{
    "is_relevant": "yes/no",
    "confidence_score": <integer 0-100>,
    "headline_en": "Formal English Headline",
    "summary": "Concise 50-word summary of the key facts.",
    "summary_long": "Detailed 100-word analytical summary. Include key facts, figures, names, country implications, and market/policy impact.",
    "category": "Category Name",
    "countries": ["Country1", "Country2"]
}}
"""
        user_prompt = f"""
--- NEW ARTICLE ---
Headline: "{headline}"
Content: "{content_snippet}"
"""
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            return json.loads(chat_completion.choices[0].message.content)
        except Exception as e:
            self.logger.error(f"Groq API error: {e}")
            raise DropItem(f"Groq API failed: {e}")

    # =========================================
    # M2: SCORING HELPER METHODS
    # =========================================

    def _resolve_country_codes(self, country_names: list) -> tuple:
        """Convert country names to ISO 3166-1 alpha-2 codes and determine region."""
        if not pycountry or not country_names:
            return [], None

        codes = []
        for name in country_names:
            name = name.strip()
            if not name:
                continue
            # Try exact match first
            country = pycountry.countries.get(name=name)
            if not country:
                # Try common name
                country = pycountry.countries.get(common_name=name)
            if not country:
                # Try fuzzy search
                try:
                    results = pycountry.countries.search_fuzzy(name)
                    country = results[0] if results else None
                except LookupError:
                    country = None
            if country:
                codes.append(country.alpha_2)

        # Determine region from first country code
        region = None
        if codes:
            region = self._get_region(codes[0])

        return codes, region

    def _get_region(self, alpha2_code: str) -> str:
        """Map a country's ISO alpha-2 code to a broad region."""
        REGION_MAP = {
            'US': 'North America', 'CA': 'North America', 'MX': 'North America',
            'GB': 'Europe', 'FR': 'Europe', 'DE': 'Europe', 'IT': 'Europe',
            'ES': 'Europe', 'PL': 'Europe', 'UA': 'Europe', 'NL': 'Europe',
            'SE': 'Europe', 'NO': 'Europe', 'FI': 'Europe', 'DK': 'Europe',
            'CH': 'Europe', 'AT': 'Europe', 'BE': 'Europe', 'PT': 'Europe',
            'GR': 'Europe', 'RO': 'Europe', 'CZ': 'Europe', 'HU': 'Europe',
            'IE': 'Europe', 'BG': 'Europe', 'HR': 'Europe', 'SK': 'Europe',
            'CN': 'East Asia', 'JP': 'East Asia', 'KR': 'East Asia',
            'KP': 'East Asia', 'TW': 'East Asia', 'MN': 'East Asia',
            'IN': 'South Asia', 'PK': 'South Asia', 'BD': 'South Asia',
            'LK': 'South Asia', 'NP': 'South Asia', 'AF': 'South Asia',
            'RU': 'Russia & Central Asia', 'KZ': 'Russia & Central Asia',
            'UZ': 'Russia & Central Asia', 'TM': 'Russia & Central Asia',
            'KG': 'Russia & Central Asia', 'TJ': 'Russia & Central Asia',
            'SA': 'Middle East', 'IR': 'Middle East', 'IQ': 'Middle East',
            'IL': 'Middle East', 'PS': 'Middle East', 'AE': 'Middle East',
            'TR': 'Middle East', 'SY': 'Middle East', 'LB': 'Middle East',
            'YE': 'Middle East', 'JO': 'Middle East', 'QA': 'Middle East',
            'KW': 'Middle East', 'BH': 'Middle East', 'OM': 'Middle East',
            'BR': 'South America', 'AR': 'South America', 'CO': 'South America',
            'CL': 'South America', 'PE': 'South America', 'VE': 'South America',
            'EC': 'South America', 'BO': 'South America', 'PY': 'South America',
            'UY': 'South America', 'GY': 'South America', 'SR': 'South America',
            'AU': 'Oceania', 'NZ': 'Oceania', 'FJ': 'Oceania',
            'PG': 'Oceania', 'SB': 'Oceania',
        }
        region = REGION_MAP.get(alpha2_code)
        if not region:
            # Default unmapped codes to Africa (most unmapped will be African nations)
            region = 'Africa'
        return region

    def _compute_repetition_score(self, embedding: list) -> float:
        """
        Compute max cosine similarity against articles from the last 48 hours.
        Returns a float 0.0-1.0 where higher means MORE repetitive.
        """
        try:
            self.cursor.execute("""
                SELECT 1 - (embedding <=> %s::vector) AS similarity
                FROM articles
                WHERE scraped_at >= NOW() - INTERVAL '48 hours'
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector ASC
                LIMIT 1
            """, (embedding, embedding))
            row = self.cursor.fetchone()
            if row and row[0] is not None:
                return max(0.0, float(row[0]))
            return 0.0
        except Exception as e:
            self.logger.warning(f"Repetition check failed: {e}")
            self.connection.rollback()
            return 0.0

    def _get_source_credibility(self, publication_name: str) -> int:
        """Look up source credibility score from sources table."""
        if not publication_name:
            return self.default_credibility
        try:
            self.cursor.execute(
                "SELECT credibility_score FROM sources WHERE name = %s",
                (publication_name,)
            )
            row = self.cursor.fetchone()
            if row:
                return row[0]
            return self.default_credibility
        except Exception as e:
            self.logger.warning(f"Source lookup failed: {e}")
            self.connection.rollback()
            return self.default_credibility

    def _compute_novelty_score(self, embedding: list) -> float:
        """
        Compute novelty: 1 - max_cosine_similarity to APPROVED articles in last 48h.
        Returns 0-100 scale. Higher = more novel.
        """
        try:
            self.cursor.execute("""
                SELECT 1 - (embedding <=> %s::vector) AS similarity
                FROM articles
                WHERE scraped_at >= NOW() - INTERVAL '48 hours'
                  AND status = 'approved'
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector ASC
                LIMIT 1
            """, (embedding, embedding))
            row = self.cursor.fetchone()
            if row and row[0] is not None:
                max_sim = float(row[0])
                # novelty = 1 - similarity, scaled to 0-100
                return max(0, min(100, (1.0 - max_sim) * 100))
            # No approved articles yet = fully novel
            return 100.0
        except Exception as e:
            self.logger.warning(f"Novelty check failed: {e}")
            self.connection.rollback()
            return 100.0

    def _compute_auto_approval_score(
        self, confidence: int, credibility: int, novelty: float, category: str
    ) -> float:
        """
        Composite score = weighted sum of:
          40% confidence (0-100)
          30% credibility (0-100)
          15% novelty (0-100)
          15% category bonus (0-100)
        Returns a float 0-100.
        """
        w = self.scoring_weights
        cat_bonus = self.category_bonus_map.get(category, 10)

        score = (
            w["confidence"] * confidence +
            w["credibility"] * credibility +
            w["novelty"] * novelty +
            w["category_bonus"] * cat_bonus
        )
        return round(min(100, max(0, score)), 2)

    def _lookup_or_create_source(self, publication_name: str):
        """Look up source_id, auto-creating if it doesn't exist. Returns int or None."""
        if not publication_name:
            return None
        try:
            self.cursor.execute(
                "SELECT id FROM sources WHERE name = %s", (publication_name,)
            )
            row = self.cursor.fetchone()
            if row:
                return row[0]
            # Auto-create source entry
            self.cursor.execute(
                "INSERT INTO sources (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
                (publication_name,)
            )
            new_row = self.cursor.fetchone()
            if new_row:
                return new_row[0]
            # Conflict path: source was created concurrently, re-fetch
            self.cursor.execute(
                "SELECT id FROM sources WHERE name = %s", (publication_name,)
            )
            row = self.cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            self.logger.warning(f"Source lookup/create failed: {e}")
            self.connection.rollback()
            return None

    # =========================================
    # MAIN PROCESSING
    # =========================================

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if adapter.get('url') in self.seen_urls:
            raise DropItem(f"Duplicate: {item['url']}")
        self.seen_urls.add(adapter['url'])

        headline = adapter['headline']
        content_snippet = adapter.get('description', '') or ""
        publication_name = adapter.get('publication_name')

        self.logger.info(f"Processing: '{headline}'")

        try:
            # 1. Generate Embedding
            text_to_embed = f"Headline: {headline}\nSummary: {content_snippet}"
            embedding = self.embedding_model.encode(text_to_embed).tolist()
            adapter['embedding'] = embedding

            # 2. Ask Groq (M2: now includes country extraction)
            processed_data = self._get_groq_completion(headline, content_snippet)

            # 3. Check Relevance
            if processed_data.get("is_relevant") == "no":
                self.logger.info(f"DROPPED (Irrelevant): '{headline}' (Score: {processed_data.get('confidence_score', 0)})")
                raise DropItem(f"Irrelevant: {headline}")

            # 4. Assign Data from Groq
            adapter['headline_en'] = processed_data.get('headline_en', headline)
            adapter['summary'] = processed_data.get('summary', 'No summary.')
            adapter['summary_long'] = processed_data.get('summary_long', adapter['summary'])
            adapter['category'] = processed_data.get('category', 'Other')
            adapter['confidence_score'] = processed_data.get('confidence_score', 50)

            if adapter['category'] not in self.valid_categories_set:
                adapter['category'] = 'Other'

            # 5. M2: Resolve country codes from Groq response
            country_names = processed_data.get('countries', [])
            if not isinstance(country_names, list):
                country_names = []
            country_codes, region = self._resolve_country_codes(country_names)

            # 6. M2: Compute repetition score (against ALL articles in 48h)
            repetition_score = self._compute_repetition_score(embedding)

            # 7. M2: Look up source credibility
            source_credibility = self._get_source_credibility(publication_name)

            # 8. M2: Compute novelty (against APPROVED articles in 48h)
            novelty_score = self._compute_novelty_score(embedding)

            # 9. M2: Compute composite auto-approval score
            auto_approval_score = self._compute_auto_approval_score(
                adapter['confidence_score'],
                source_credibility,
                novelty_score,
                adapter['category']
            )

            # 10. M2: Look up or auto-create source_id
            source_id = self._lookup_or_create_source(publication_name)

            self.logger.info(
                f"Scored: '{headline}' | Confidence: {adapter['confidence_score']} | "
                f"Credibility: {source_credibility} | Novelty: {novelty_score:.1f} | "
                f"Repetition: {repetition_score:.3f} | Auto: {auto_approval_score} | "
                f"Countries: {country_codes}"
            )

            # 11. Save to DB (M2: expanded INSERT with all new fields)
            self.cursor.execute(
                """
                INSERT INTO articles
                (url, headline, publication_name, author, headline_en, summary,
                 summary_long, category, status, scraped_at, embedding, confidence_score,
                 source_id, repetition_score, auto_approval_score,
                 country_codes, region)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW(), %s, %s,
                        %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING
                """,
                (
                    adapter['url'], adapter['headline'], publication_name,
                    adapter.get('author'),
                    adapter['headline_en'], adapter['summary'],
                    adapter['summary_long'], adapter['category'],
                    adapter['embedding'], adapter['confidence_score'],
                    source_id, repetition_score, auto_approval_score,
                    country_codes if country_codes else None,
                    region
                )
            )
            self.connection.commit()

        except DropItem as e:
            raise e
        except Exception as e:
            # Rollback on any other error to keep connection alive
            self.connection.rollback()
            self.logger.error(f"Error processing '{headline}': {e}")
            raise DropItem(f"Processing failed: {item['url']}")

        return item
