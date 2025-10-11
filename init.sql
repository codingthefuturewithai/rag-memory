-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Collection management table
CREATE TABLE collections (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Source documents table (stores full documents before chunking)
CREATE TABLE source_documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    file_type VARCHAR(50),
    file_size INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Document chunks table (stores chunks for vector search)
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    source_document_id INTEGER REFERENCES source_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_document_id, chunk_index)
);

-- Chunk-collection relationship
CREATE TABLE chunk_collections (
    chunk_id INTEGER REFERENCES document_chunks(id) ON DELETE CASCADE,
    collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
    PRIMARY KEY (chunk_id, collection_id)
);

-- HNSW index for chunk embeddings
CREATE INDEX document_chunks_embedding_idx ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Index for chunk lookups
CREATE INDEX document_chunks_source_idx ON document_chunks(source_document_id);

-- Index for chunk metadata queries
CREATE INDEX document_chunks_metadata_idx ON document_chunks USING gin (metadata);

-- Trigger for source_documents updated_at
CREATE TRIGGER update_source_documents_updated_at
    BEFORE UPDATE ON source_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
