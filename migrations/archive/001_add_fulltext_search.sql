-- Migration 001: Add Full-Text Search Support
-- Purpose: Enable hybrid search (vector + keyword matching)
-- Date: 2025-10-11

-- Add tsvector column for full-text search on document chunks
-- GENERATED ALWAYS ensures it stays in sync with content automatically
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS content_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

-- Create GIN index for fast full-text search
-- GIN (Generalized Inverted Index) is optimal for full-text search
CREATE INDEX IF NOT EXISTS document_chunks_content_tsv_idx
ON document_chunks USING gin(content_tsv);

-- Verify the migration
DO $$
BEGIN
    -- Check if column exists
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'document_chunks'
        AND column_name = 'content_tsv'
    ) THEN
        RAISE NOTICE 'SUCCESS: content_tsv column added to document_chunks';
    ELSE
        RAISE EXCEPTION 'FAILED: content_tsv column not found';
    END IF;

    -- Check if index exists
    IF EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE tablename = 'document_chunks'
        AND indexname = 'document_chunks_content_tsv_idx'
    ) THEN
        RAISE NOTICE 'SUCCESS: GIN index created on content_tsv';
    ELSE
        RAISE EXCEPTION 'FAILED: GIN index not found';
    END IF;
END $$;

-- Show some stats
SELECT
    COUNT(*) as total_chunks,
    COUNT(content_tsv) as chunks_with_tsv,
    pg_size_pretty(pg_total_relation_size('document_chunks')) as table_size,
    pg_size_pretty(pg_relation_size('document_chunks_content_tsv_idx')) as index_size
FROM document_chunks;
