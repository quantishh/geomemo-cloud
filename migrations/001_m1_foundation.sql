-- =============================================================================
-- GeoMemo Milestone 1: Foundation Migration
-- Run this AFTER backing up your database with pg_dump.
-- All statements are idempotent (safe to re-run).
-- =============================================================================

-- 1. Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create 'sources' table — tracks news sources with credibility scores
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

-- 3. Create 'daily_briefs' table — stores daily intelligence summaries
CREATE TABLE IF NOT EXISTS daily_briefs (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    summary_text TEXT NOT NULL,
    summary_html TEXT,
    word_count INTEGER,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    published BOOLEAN DEFAULT FALSE
);

-- 4. Add new columns to 'articles' table
ALTER TABLE articles ADD COLUMN IF NOT EXISTS parent_id INTEGER;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS source_id INTEGER REFERENCES sources(id);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS relevance_score FLOAT DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS repetition_score FLOAT DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS auto_approval_score FLOAT DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS country_codes TEXT[];
ALTER TABLE articles ADD COLUMN IF NOT EXISTS region TEXT;

-- 5. Add new columns to 'tweets' table
ALTER TABLE tweets ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE tweets ADD COLUMN IF NOT EXISTS article_id INTEGER REFERENCES articles(id);
ALTER TABLE tweets ADD COLUMN IF NOT EXISTS is_newsletter_tweet BOOLEAN DEFAULT FALSE;

-- 6. Seed 'sources' table from existing article publication names
INSERT INTO sources (name)
SELECT DISTINCT publication_name
FROM articles
WHERE publication_name IS NOT NULL
  AND publication_name != ''
  AND publication_name NOT IN (SELECT name FROM sources)
ORDER BY publication_name;

-- 7. Backfill source_id on articles
UPDATE articles a SET source_id = s.id
FROM sources s
WHERE a.publication_name = s.name
  AND a.source_id IS NULL;

-- 8. Update source article counts
UPDATE sources s SET
    total_articles = sub.total,
    approved_count = sub.approved,
    rejected_count = sub.rejected
FROM (
    SELECT publication_name,
           COUNT(*) as total,
           COUNT(*) FILTER (WHERE status = 'approved') as approved,
           COUNT(*) FILTER (WHERE status = 'rejected') as rejected
    FROM articles
    WHERE publication_name IS NOT NULL
    GROUP BY publication_name
) sub
WHERE s.name = sub.publication_name;
