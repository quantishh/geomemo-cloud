"""
Database connection and initialization.
Handles pgvector extension setup and table creation/migration.
"""
import logging
import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
from fastapi import HTTPException

from config import DB_CONFIG

logger = logging.getLogger(__name__)


def get_db_connection():
    """Get a new database connection with pgvector registered."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        cursor.close()
        register_vector(conn)
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")


def init_db():
    """Create all tables and run migrations on startup."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # --- Core tables ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE,
                headline TEXT,
                headline_en TEXT,
                summary TEXT,
                category TEXT,
                publication_name TEXT,
                author TEXT,
                status TEXT DEFAULT 'pending',
                scraped_at TIMESTAMPTZ DEFAULT NOW(),
                is_top_story BOOLEAN DEFAULT FALSE,
                embedding vector(384),
                confidence_score INTEGER DEFAULT 0,
                parent_id INTEGER
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                url TEXT,
                author TEXT,
                image_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sponsors (
                id SERIAL PRIMARY KEY,
                company_name TEXT NOT NULL,
                headline TEXT NOT NULL,
                summary TEXT NOT NULL,
                link_url TEXT NOT NULL,
                logo_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS podcasts (
                id SERIAL PRIMARY KEY,
                show_name TEXT NOT NULL,
                episode_title TEXT NOT NULL,
                description TEXT NOT NULL,
                link_url TEXT NOT NULL,
                image_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # --- New M1 tables ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                domain TEXT,
                credibility_score INTEGER DEFAULT 50,
                tier INTEGER DEFAULT 3,
                country TEXT,
                language TEXT DEFAULT 'en',
                total_articles INTEGER DEFAULT 0,
                approved_count INTEGER DEFAULT 0,
                rejected_count INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_briefs (
                id SERIAL PRIMARY KEY,
                date DATE UNIQUE NOT NULL,
                summary_text TEXT NOT NULL,
                summary_html TEXT,
                word_count INTEGER,
                generated_at TIMESTAMPTZ DEFAULT NOW(),
                published BOOLEAN DEFAULT FALSE
            );
        """)

        # --- M6: Social media tracking ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS social_posts (
                id SERIAL PRIMARY KEY,
                platform TEXT NOT NULL,
                post_type TEXT NOT NULL,
                platform_post_id TEXT,
                article_id INTEGER REFERENCES articles(id),
                brief_id INTEGER REFERENCES daily_briefs(id),
                content_text TEXT,
                status TEXT DEFAULT 'sent',
                error_message TEXT,
                posted_at TIMESTAMPTZ DEFAULT NOW(),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # --- Migrations (safe ADD COLUMN IF NOT EXISTS) ---
        migrations = [
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS parent_id INTEGER",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS source_id INTEGER REFERENCES sources(id)",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS relevance_score FLOAT DEFAULT 0",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS repetition_score FLOAT DEFAULT 0",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS auto_approval_score FLOAT DEFAULT 0",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS country_codes TEXT[]",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS region TEXT",
            "ALTER TABLE tweets ADD COLUMN IF NOT EXISTS image_url TEXT",
            "ALTER TABLE tweets ADD COLUMN IF NOT EXISTS article_id INTEGER REFERENCES articles(id)",
            "ALTER TABLE tweets ADD COLUMN IF NOT EXISTS is_newsletter_tweet BOOLEAN DEFAULT FALSE",
            # M2: Performance indexes for smart curation
            "CREATE INDEX IF NOT EXISTS idx_articles_scraped_at ON articles (scraped_at)",
            "CREATE INDEX IF NOT EXISTS idx_articles_status ON articles (status)",
            "CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles (source_id)",
            # M3: Newsletter enhancement — extend daily_briefs table
            "ALTER TABLE daily_briefs ADD COLUMN IF NOT EXISTS beehiiv_post_id TEXT",
            "ALTER TABLE daily_briefs ADD COLUMN IF NOT EXISTS newsletter_html TEXT",
            "ALTER TABLE daily_briefs ADD COLUMN IF NOT EXISTS subject_line TEXT",
            # M5: Map layer — 100-word summary for WorldMonitor fork
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS summary_long TEXT",
            # M6: Social media dedup index
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_social_posts_dedup
               ON social_posts (platform, article_id) WHERE article_id IS NOT NULL""",
            "CREATE INDEX IF NOT EXISTS idx_social_posts_platform ON social_posts (platform)",
            "CREATE INDEX IF NOT EXISTS idx_social_posts_posted_at ON social_posts (posted_at)",
            # M6 Phase 2: Store embedded X posts for newsletter (JSON array of tweet URLs/data)
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS embedded_tweets JSONB",
        ]
        for sql in migrations:
            try:
                cursor.execute(sql)
                conn.commit()  # Commit each migration individually so one failure doesn't roll back others
            except Exception as e:
                conn.rollback()
                logger.warning(f"Migration skipped (already applied or failed): {e}")
        logger.info("Database initialized successfully.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Init DB error: {e}")
    finally:
        cursor.close()
        conn.close()
