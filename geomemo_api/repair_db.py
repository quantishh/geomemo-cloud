import psycopg2
from pgvector.psycopg2 import register_vector

# Config
DB_CONFIG = {
    "host": "localhost",
    "database": "postgres",
    "user": "postgres",
    "password": "Quantishh@1979" 
}

def fix_database():
    try:
        print("Connecting to DB...")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        # 1. Enable Vector Extension
        print("Enabling pgvector...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        register_vector(conn)

        # 2. Create 'articles' table
        print("Creating 'articles' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                headline TEXT,
                headline_original TEXT,
                headline_en TEXT,
                summary TEXT,
                category TEXT,
                status TEXT DEFAULT 'pending',
                publication_name TEXT,
                author TEXT,
                scraped_at TIMESTAMPTZ DEFAULT NOW(),
                confidence_score INTEGER,
                is_top_story BOOLEAN DEFAULT FALSE,
                embedding vector(384)
            );
        """)

        # 3. Create 'tweets' table
        print("Creating 'tweets' table...")
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

        # 4. Create 'sponsors' table
        print("Creating 'sponsors' table...")
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

        # 5. Create 'podcasts' table
        print("Creating 'podcasts' table...")
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

        print("✅ Database Repair Complete! All tables created.")
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_database()