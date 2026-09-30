-- Migration: 001_incident_docs.sql
-- Enables pgvector extension, creates incident_docs table with 768-dim embeddings,
-- and defines match_incident_docs RPC function for cosine similarity search.

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create incident_docs table
CREATE TABLE IF NOT EXISTS incident_docs (
    id BIGSERIAL PRIMARY KEY,
    doc_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Create index for metadata JSON queries
CREATE INDEX IF NOT EXISTS idx_incident_docs_metadata ON incident_docs USING gin (metadata);

-- 4. Create RPC function for cosine similarity retrieval
CREATE OR REPLACE FUNCTION match_incident_docs(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.0,
    match_count int DEFAULT 5,
    filter_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id bigint,
    doc_key text,
    title text,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.doc_key,
        d.title,
        d.content,
        d.metadata,
        (1 - (d.embedding <=> query_embedding))::float AS similarity
    FROM incident_docs d
    WHERE
        (filter_metadata = '{}'::jsonb OR d.metadata @> filter_metadata)
        AND (1 - (d.embedding <=> query_embedding)) >= match_threshold
    ORDER BY d.embedding <=> query_embedding ASC
    LIMIT match_count;
END;
$$;
