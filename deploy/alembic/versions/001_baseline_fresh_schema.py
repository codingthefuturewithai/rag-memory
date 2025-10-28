"""baseline_fresh_schema

Revision ID: 001_baseline
Revises:
Create Date: 2025-10-24

Fresh baseline schema for RAG Memory. This is the complete schema from init.sql
consolidated into a single baseline migration for clean deployments.

This migration replaces the previous migration history (which is no longer needed
as we're starting with fresh cloud deployments).

Schema includes:
- pgvector extension for vector search
- collections table (with required description and metadata_schema)
- source_documents table (full documents before chunking)
- document_chunks table (searchable chunks with embeddings)
- chunk_collections junction table (many-to-many relationships)
- HNSW index for fast vector similarity search
- Metadata indexes for efficient JSONB queries
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create complete baseline schema."""

    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create collections table
    op.create_table(
        'collections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata_schema', sa.JSON(), nullable=False, server_default='{"custom": {}, "system": []}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create function for updating timestamps
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)

    # Create source_documents table
    op.create_table(
        'source_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_document_id', sa.Integer(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('embedding', sa.dialects.postgresql.ARRAY(sa.Float(), as_tuple=False, zero_indexes=False), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['source_document_id'], ['source_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_document_id', 'chunk_index')
    )

    # Create chunk_collections junction table
    op.create_table(
        'chunk_collections',
        sa.Column('chunk_id', sa.Integer(), nullable=False),
        sa.Column('collection_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('chunk_id', 'collection_id')
    )

    # Create indexes
    op.create_index('document_chunks_source_idx', 'document_chunks', ['source_document_id'])
    op.create_index('document_chunks_metadata_idx', 'document_chunks', ['metadata'], postgresql_using='gin')

    # Create HNSW index for embeddings (pgvector similarity search)
    op.execute("""
        CREATE INDEX document_chunks_embedding_idx ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Create triggers for updated_at column
    op.execute("""
        CREATE TRIGGER update_source_documents_updated_at
            BEFORE UPDATE ON source_documents
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """)

    # Add check constraint for description (not empty)
    op.execute("""
        ALTER TABLE collections
        ADD CONSTRAINT description_not_empty
        CHECK (length(trim(description)) > 0)
    """)


def downgrade() -> None:
    """Downgrade schema - drop all tables and functions.

    Note: Cannot downgrade from baseline. This migration removes the entire schema.
    """
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_source_documents_updated_at ON source_documents")

    # Drop tables (order matters due to foreign keys)
    op.drop_table('chunk_collections')
    op.drop_table('document_chunks')
    op.drop_table('source_documents')
    op.drop_table('collections')

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    # Drop extension
    op.execute("DROP EXTENSION IF EXISTS vector")
