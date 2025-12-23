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

    def open_spider(self, spider):
        try:
            # --- UPDATED: Smart Host Detection ---
            # Checks for 'POSTGRES_HOST' env var, defaults to 'db' (Cloud), works with 'localhost' if set.
            self.connection = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "db"),
                database="postgres",
                user="postgres",
                password="Quantishh@1979" 
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

    def _get_historical_context(self, embedding):
        """
        Fetches historical context. Fixes the 'vector <=> numeric[]' error.
        """
        try:
            # --- FIX: Added ::vector cast to the placeholder ---
            self.cursor.execute(
                """
                SELECT headline_en, status 
                FROM articles 
                WHERE status IN ('approved', 'rejected')
                ORDER BY embedding <=> %s::vector ASC
                LIMIT 5
                """,
                (embedding,)
            )
            rows = self.cursor.fetchall()
            
            if not rows:
                return "No historical data available yet."
            
            context_str = "Here are similar articles the user has previously processed:\n"
            for row in rows:
                context_str += f"- Headline: '{row[0]}' | User Decision: {row[1].upper()}\n"
            return context_str
            
        except (Exception, InternalError) as e:
            # --- FIX: Immediate Rollback on error to prevent stuck transaction ---
            self.connection.rollback()
            self.logger.warning(f"Could not fetch history (Transaction Rolled Back): {e}")
            return "No historical data available (DB Error)."

    def _get_groq_completion(self, headline: str, content_snippet: str, history_context: str) -> dict:
        system_prompt = f"""
You are a top-tier geopolitical analyst for 'GeoMemo'.
Your goal is to curate high-value geopolitical news.

STEP 1: Analyze relevance based on these rules:
- `Geopolitical Conflict`: War, civil war, terrorism.
- `Geopolitical Politics`: NATIONAL elections/outcomes only.
- `GeoNatDisaster`: MAJOR climate disasters only.
- `Geopolitical Economics`: Trade, sanctions, economic pacts.
- `Global Markets`: Major stock/commodity/currency moves.
- `GeoLocal`: Local event with INTERNATIONAL implications.

STEP 2: Assign a CONFIDENCE SCORE (0-100).
- Review the "User History" provided. If the user rejected similar articles in the past, give a LOW score (0-30).
- If the user approved similar articles, or if it strongly matches the rules above, give a HIGH score (80-100).

STEP 3: Output valid JSON:
{{
    "is_relevant": "yes/no",
    "confidence_score": <integer 0-100>,
    "headline_en": "Formal English Headline",
    "summary": "Detailed 50-word summary based on text.",
    "category": "Category Name"
}}
"""
        user_prompt = f"""
--- NEW ARTICLE ---
Headline: "{headline}"
Content: "{content_snippet}"

--- USER HISTORY (LEARNING CONTEXT) ---
{history_context}
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

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        if adapter.get('url') in self.seen_urls: raise DropItem(f"Duplicate: {item['url']}")
        self.seen_urls.add(adapter['url'])

        headline = adapter['headline']
        content_snippet = adapter.get('description', '') or ""

        self.logger.info(f"Processing: '{headline}'")

        try:
            # 1. Generate Embedding
            text_to_embed = f"Headline: {headline}\nSummary: {content_snippet}"
            embedding = self.embedding_model.encode(text_to_embed).tolist()
            adapter['embedding'] = embedding

            # 2. Get History (RAG) - Now robust against errors
            history_context = self._get_historical_context(embedding)

            # 3. Ask Groq
            processed_data = self._get_groq_completion(headline, content_snippet, history_context)

            # 4. Check Relevance
            if processed_data.get("is_relevant") == "no":
                self.logger.info(f"DROPPED (Irrelevant): '{headline}' (Score: {processed_data.get('confidence_score', 0)})")
                raise DropItem(f"Irrelevant: {headline}")

            # 5. Assign Data
            adapter['headline_en'] = processed_data.get('headline_en', headline)
            adapter['summary'] = processed_data.get('summary', 'No summary.')
            adapter['category'] = processed_data.get('category', 'Other')
            adapter['confidence_score'] = processed_data.get('confidence_score', 50)

            if adapter['category'] not in self.valid_categories_set: adapter['category'] = 'Other'

            self.logger.info(f"Success: '{headline}' | Score: {adapter['confidence_score']}/100")

            # 6. Save to DB
            self.cursor.execute(
                """
                INSERT INTO articles 
                (url, headline, publication_name, author, headline_en, summary, category, status, scraped_at, embedding, confidence_score) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW(), %s, %s) 
                ON CONFLICT (url) DO NOTHING
                """,
                (
                    adapter['url'], adapter['headline'], adapter.get('publication_name'), adapter.get('author'),
                    adapter['headline_en'], adapter['summary'], adapter['category'], 
                    adapter['embedding'], adapter['confidence_score']
                )
            )
            self.connection.commit()

        except DropItem as e: raise e
        except Exception as e:
            # Rollback on any other error to keep connection alive
            self.connection.rollback()
            self.logger.error(f"Error processing '{headline}': {e}")
            raise DropItem(f"Processing failed: {item['url']}")
        
        return item
