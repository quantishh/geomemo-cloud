-- =============================================================================
-- GeoMemo Milestone 2: Smart Curation Migration
-- All statements are idempotent (safe to re-run).
-- =============================================================================

-- 1. IVFFlat index on article embeddings for fast cosine similarity
--    Dramatically speeds up repetition detection and novelty queries.
--    Requires rows to exist; safe to re-run.
CREATE INDEX IF NOT EXISTS idx_articles_embedding_ivfflat
ON articles USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 2. Index on scraped_at for the 48-hour window lookups
CREATE INDEX IF NOT EXISTS idx_articles_scraped_at ON articles (scraped_at);

-- 3. Index on status for filtering approved articles in novelty check
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles (status);

-- 4. Index on source_id for credibility lookups
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles (source_id);

-- 5. Composite index for the repetition detection query pattern
CREATE INDEX IF NOT EXISTS idx_articles_status_scraped
ON articles (status, scraped_at DESC) WHERE embedding IS NOT NULL;
