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

        # --- Social queue for scheduled posting ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS social_queue (
                id SERIAL PRIMARY KEY,
                article_id INTEGER REFERENCES articles(id),
                platform TEXT NOT NULL,
                content_text TEXT NOT NULL,
                status TEXT DEFAULT 'queued',
                queued_at TIMESTAMPTZ DEFAULT NOW(),
                posted_at TIMESTAMPTZ,
                error_message TEXT
            );
        """)

        # --- Events table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT,
                location TEXT,
                start_date DATE NOT NULL,
                end_date DATE,
                description TEXT,
                category TEXT DEFAULT 'Conference',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # --- Event search queries table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_search_queries (
                id SERIAL PRIMARY KEY,
                query TEXT NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT TRUE,
                last_run_at TIMESTAMPTZ,
                events_found INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # --- Forum discussions table (Phase 1: Pipeline Overhaul) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forum_discussions (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE,
                title TEXT,
                forum_name TEXT,
                author TEXT,
                content TEXT,
                full_content TEXT,
                category TEXT,
                significance_score INTEGER DEFAULT 0,
                embedding vector(384),
                scraped_at TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'pending',
                article_id INTEGER REFERENCES articles(id),
                platform TEXT,
                upvotes INTEGER DEFAULT 0,
                subreddit TEXT
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
            # Source management: RSS feed URL + X/Twitter handle per source
            "ALTER TABLE sources ADD COLUMN IF NOT EXISTS rss_feed_url TEXT",
            "ALTER TABLE sources ADD COLUMN IF NOT EXISTS twitter_handle TEXT",
            # Social queue indexes
            "CREATE INDEX IF NOT EXISTS idx_social_queue_status ON social_queue (status)",
            "CREATE INDEX IF NOT EXISTS idx_social_queue_queued_at ON social_queue (queued_at)",
            # Website: OG image URL for article thumbnails
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS og_image TEXT",
            # Events index for upcoming events query
            "CREATE INDEX IF NOT EXISTS idx_events_start_date ON events (start_date)",
            # Podcast YouTube video embed support
            "ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS video_url TEXT",
            # Events: registration URL + featured flag
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS register_url TEXT",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT FALSE",
            # Website X posts: auto-fetched tweets cached per article (separate from newsletter embedded_tweets)
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS website_tweets JSONB",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS website_tweets_fetched_at TIMESTAMPTZ",
            # Automated event extraction from articles
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'approved'",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS source_article_id INTEGER",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMPTZ",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS events_extracted BOOLEAN DEFAULT FALSE",
            "CREATE INDEX IF NOT EXISTS idx_events_status ON events (status)",
            "CREATE INDEX IF NOT EXISTS idx_articles_events_extracted ON articles (events_extracted)",
            # Google Search event discovery
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS source_query TEXT",
            # --- Phase 1: Pipeline Overhaul (April 2026) ---
            # Full content extraction
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS full_content TEXT",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_source TEXT",
            # Clustering
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS cluster_id INTEGER",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS cluster_role TEXT",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS cluster_label TEXT",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS child_summary TEXT",
            # Q1-Q5 multi-criteria scores
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS significance_score INTEGER DEFAULT 0",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS impact_score INTEGER DEFAULT 0",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS novelty_score_v2 INTEGER DEFAULT 0",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS relevance_score_v2 INTEGER DEFAULT 0",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS depth_score INTEGER DEFAULT 0",
            # Source type classification
            "ALTER TABLE sources ADD COLUMN IF NOT EXISTS source_type TEXT",
            # Cluster index
            "CREATE INDEX IF NOT EXISTS idx_articles_cluster_id ON articles (cluster_id)",
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
