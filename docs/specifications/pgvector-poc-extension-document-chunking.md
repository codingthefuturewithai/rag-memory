# POC Extension: Document Chunking and Ingestion

## Purpose

This document extends the base pgvector POC to add document chunking capabilities. This allows ingesting full text documents (files from disk), automatically splitting them into optimal-sized chunks, and storing each chunk as a separate embedding for precise retrieval.

## Prerequisites

You should have already implemented the base POC with:
- ✅ PostgreSQL 17 + pgvector running in Docker
- ✅ Basic `documents` table with embeddings
- ✅ Collections table and management
- ✅ Basic search functionality
- ✅ CLI framework with Click
- ✅ Embedding generation with normalization

## Why Add Document Chunking?

**Current Limitation**: 
The base POC likely handles short text snippets inserted directly. For real-world use, you need to:
- Ingest full documents from files (text, markdown, PDF, etc.)
- Split long documents into manageable chunks
- Store each chunk separately with its own embedding
- Track which chunks came from which source document

**Benefits**:
- Search returns specific relevant sections, not entire documents
- Better similarity scores (focused chunks vs generic whole-doc embeddings)
- Can retrieve full source document from any chunk
- Standard RAG application pattern

## Architecture Overview

### Database Changes

**Add two new tables** to track source documents and their chunks separately:

```sql
-- Store original full documents
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

-- Store chunks (what actually gets searched)
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    source_document_id INTEGER REFERENCES source_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    char_start INTEGER,              -- Position in original document
    char_end INTEGER,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),          -- Chunk embedding
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(source_document_id, chunk_index)
);

-- Link chunks to collections (many-to-many)
CREATE TABLE chunk_collections (
    chunk_id INTEGER REFERENCES document_chunks(id) ON DELETE CASCADE,
    collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
    PRIMARY KEY (chunk_id, collection_id)
);

-- Indexes
CREATE INDEX document_chunks_embedding_idx ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX document_chunks_source_idx ON document_chunks(source_document_id);
CREATE INDEX document_chunks_metadata_idx ON document_chunks USING gin (metadata);

-- Trigger for updated_at
CREATE TRIGGER update_source_documents_updated_at 
    BEFORE UPDATE ON source_documents 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
```

**Note**: Your existing `documents` table from the base POC can remain for backward compatibility or can be migrated to this new structure.

## Text Chunking Implementation

### Add Dependencies to pyproject.toml

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "langchain-text-splitters>=0.3.0",  # New: dedicated text splitting package
]
```

### New Module: `src/chunking.py`

```python
"""Document chunking using LangChain text splitters."""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for document chunking."""
    
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: Optional[List[str]] = None
    
    def __post_init__(self):
        """Set default separators if not provided."""
        if self.separators is None:
            # Optimized for general text and markdown
            self.separators = [
                "\n## ",   # Markdown H2
                "\n### ",  # Markdown H3
                "\n#### ", # Markdown H4
                "\n\n",    # Paragraph breaks
                "\n",      # Line breaks
                ". ",      # Sentence endings
                " ",       # Word boundaries
                "",        # Character-level fallback
            ]


class DocumentChunker:
    """Split documents into chunks for embedding."""
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        """
        Initialize the chunker.
        
        Args:
            config: Optional chunking configuration
        """
        self.config = config or ChunkingConfig()
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separators=self.config.separators,
            length_function=len,
            is_separator_regex=False,
        )
        
        logger.info(
            f"Initialized chunker: chunk_size={self.config.chunk_size}, "
            f"overlap={self.config.chunk_overlap}"
        )
    
    def chunk_text(
        self, 
        text: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Split text into chunks.
        
        Args:
            text: Full text to chunk
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of Document objects (LangChain format)
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking")
            return []
        
        # Create LangChain Document
        doc = Document(
            page_content=text,
            metadata=metadata or {}
        )
        
        # Split into chunks
        chunks = self.splitter.split_documents([doc])
        
        # Add chunk-specific metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
            # Approximate character positions (not exact due to overlap)
            chunk.metadata["char_start"] = i * (self.config.chunk_size - self.config.chunk_overlap)
            chunk.metadata["char_end"] = chunk.metadata["char_start"] + len(chunk.page_content)
        
        logger.info(
            f"Split {len(text)} chars into {len(chunks)} chunks. "
            f"Avg size: {sum(len(c.page_content) for c in chunks) / len(chunks):.0f} chars"
        )
        
        return chunks
    
    def get_stats(self, chunks: List[Document]) -> Dict[str, Any]:
        """
        Calculate statistics about chunks.
        
        Args:
            chunks: List of chunked documents
            
        Returns:
            Dictionary with statistics
        """
        if not chunks:
            return {
                "num_chunks": 0,
                "total_chars": 0,
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0,
            }
        
        sizes = [len(c.page_content) for c in chunks]
        
        return {
            "num_chunks": len(chunks),
            "total_chars": sum(sizes),
            "avg_chunk_size": sum(sizes) / len(sizes),
            "min_chunk_size": min(sizes),
            "max_chunk_size": max(sizes),
        }
```

### New Module: `src/document_store.py`

```python
"""Store and manage full documents with chunking."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .database import get_connection
from .chunking import DocumentChunker, ChunkingConfig
from .embeddings import generate_embedding, normalize_embedding

logger = logging.getLogger(__name__)


class DocumentStore:
    """Manage full documents and their chunks."""
    
    def __init__(self, chunker: Optional[DocumentChunker] = None):
        """
        Initialize document store.
        
        Args:
            chunker: Optional DocumentChunker (uses default if None)
        """
        self.chunker = chunker or DocumentChunker()
    
    def ingest_document(
        self,
        content: str,
        filename: str,
        collection_name: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        file_type: str = "text",
    ) -> Tuple[int, List[int]]:
        """
        Ingest a document: store full text, chunk it, generate embeddings.
        
        Args:
            content: Full document text
            filename: Document filename/identifier
            collection_name: Collection to add chunks to
            metadata: Optional metadata for the document
            file_type: File type (text, markdown, pdf, etc.)
            
        Returns:
            Tuple of (source_document_id, list_of_chunk_ids)
        """
        conn = get_connection()
        
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                # 1. Store the full source document
                logger.info(f"Storing source document: {filename}")
                cur.execute(
                    """
                    INSERT INTO source_documents 
                    (filename, content, file_type, file_size, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        filename,
                        content,
                        file_type,
                        len(content),
                        psycopg.types.json.Jsonb(metadata or {}),
                    ),
                )
                source_id = cur.fetchone()["id"]
                
                # 2. Get or create collection
                cur.execute(
                    """
                    INSERT INTO collections (name)
                    VALUES (%s)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """,
                    (collection_name,)
                )
                collection_id = cur.fetchone()["id"]
                
                # 3. Chunk the document
                logger.info(f"Chunking document ({len(content)} chars)...")
                chunks = self.chunker.chunk_text(content, metadata)
                
                stats = self.chunker.get_stats(chunks)
                logger.info(
                    f"Created {stats['num_chunks']} chunks. "
                    f"Avg: {stats['avg_chunk_size']:.0f} chars, "
                    f"Range: {stats['min_chunk_size']}-{stats['max_chunk_size']}"
                )
                
                # 4. Generate embeddings and store chunks
                chunk_ids = []
                for chunk_doc in chunks:
                    # Generate embedding for this chunk
                    embedding = generate_embedding(chunk_doc.page_content)
                    
                    # CRITICAL: Normalize for proper similarity scores
                    normalized = normalize_embedding(embedding)
                    
                    # Store chunk
                    cur.execute(
                        """
                        INSERT INTO document_chunks 
                        (source_document_id, chunk_index, content, 
                         char_start, char_end, metadata, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            source_id,
                            chunk_doc.metadata.get("chunk_index", 0),
                            chunk_doc.page_content,
                            chunk_doc.metadata.get("char_start", 0),
                            chunk_doc.metadata.get("char_end", 0),
                            psycopg.types.json.Jsonb(chunk_doc.metadata),
                            normalized,
                        ),
                    )
                    chunk_id = cur.fetchone()["id"]
                    chunk_ids.append(chunk_id)
                    
                    # Link chunk to collection
                    cur.execute(
                        """
                        INSERT INTO chunk_collections (chunk_id, collection_id)
                        VALUES (%s, %s)
                        """,
                        (chunk_id, collection_id),
                    )
                
                conn.commit()
                logger.info(
                    f"✅ Ingested document {source_id} with {len(chunk_ids)} chunks"
                )
                
                return source_id, chunk_ids
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error ingesting document: {e}")
            raise
        finally:
            conn.close()
    
    def ingest_file(
        self,
        file_path: str,
        collection_name: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, List[int]]:
        """
        Read a file from disk and ingest it.
        
        Args:
            file_path: Path to the file
            collection_name: Collection to add to
            metadata: Optional metadata
            
        Returns:
            Tuple of (source_document_id, list_of_chunk_ids)
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read file
        content = path.read_text(encoding="utf-8")
        
        # Determine file type from extension
        file_type = path.suffix.lstrip(".").lower() or "text"
        
        # Add file info to metadata
        file_metadata = metadata or {}
        file_metadata.update({
            "filename": path.name,
            "file_path": str(path.absolute()),
            "file_type": file_type,
        })
        
        return self.ingest_document(
            content=content,
            filename=path.name,
            collection_name=collection_name,
            metadata=file_metadata,
            file_type=file_type,
        )
    
    def get_source_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a full source document.
        
        Args:
            doc_id: Source document ID
            
        Returns:
            Document dictionary or None if not found
        """
        conn = get_connection()
        
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT * FROM source_documents WHERE id = %s
                    """,
                    (doc_id,)
                )
                return cur.fetchone()
        finally:
            conn.close()
    
    def list_source_documents(
        self,
        collection_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all source documents, optionally filtered by collection.
        
        Args:
            collection_name: Optional collection filter
            
        Returns:
            List of document dictionaries
        """
        conn = get_connection()
        
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                if collection_name:
                    cur.execute(
                        """
                        SELECT DISTINCT 
                            sd.id, sd.filename, sd.file_type, 
                            sd.file_size, sd.created_at,
                            COUNT(dc.id) as chunk_count
                        FROM source_documents sd
                        JOIN document_chunks dc ON dc.source_document_id = sd.id
                        JOIN chunk_collections cc ON cc.chunk_id = dc.id
                        JOIN collections c ON c.id = cc.collection_id
                        WHERE c.name = %s
                        GROUP BY sd.id
                        ORDER BY sd.created_at DESC
                        """,
                        (collection_name,)
                    )
                else:
                    cur.execute(
                        """
                        SELECT 
                            sd.id, sd.filename, sd.file_type, 
                            sd.file_size, sd.created_at,
                            COUNT(dc.id) as chunk_count
                        FROM source_documents sd
                        LEFT JOIN document_chunks dc ON dc.source_document_id = sd.id
                        GROUP BY sd.id
                        ORDER BY sd.created_at DESC
                        """
                    )
                
                return cur.fetchall()
        finally:
            conn.close()
```

### Enhanced Search Module

Update `src/search.py` to search chunks and return source document info:

```python
def search_chunks(
    query: str,
    collection_name: str = "default",
    limit: int = 5,
    threshold: float = 0.3,
    include_source: bool = False,
) -> List[Dict[str, Any]]:
    """
    Search document chunks and optionally include source document.
    
    Args:
        query: Search query
        collection_name: Collection to search
        limit: Max results
        threshold: Minimum similarity score
        include_source: Whether to include full source document
        
    Returns:
        List of search results with chunk and optional source info
    """
    from .embeddings import generate_embedding, normalize_embedding
    
    conn = get_connection()
    
    try:
        # Generate query embedding
        query_embedding = generate_embedding(query)
        normalized_query = normalize_embedding(query_embedding)
        
        with conn.cursor(row_factory=dict_row) as cur:
            if include_source:
                # Include source document in results
                cur.execute(
                    """
                    SELECT 
                        dc.id as chunk_id,
                        dc.content as chunk_content,
                        dc.chunk_index,
                        dc.metadata as chunk_metadata,
                        sd.id as source_id,
                        sd.filename,
                        sd.content as full_document,
                        sd.metadata as source_metadata,
                        1 - (dc.embedding <=> %s::vector) as similarity
                    FROM document_chunks dc
                    JOIN source_documents sd ON sd.id = dc.source_document_id
                    JOIN chunk_collections cc ON cc.chunk_id = dc.id
                    JOIN collections c ON c.id = cc.collection_id
                    WHERE c.name = %s
                      AND 1 - (dc.embedding <=> %s::vector) >= %s
                    ORDER BY dc.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (normalized_query, collection_name, normalized_query,
                     threshold, normalized_query, limit)
                )
            else:
                # Just chunks with source reference
                cur.execute(
                    """
                    SELECT 
                        dc.id as chunk_id,
                        dc.content as chunk_content,
                        dc.chunk_index,
                        dc.metadata as chunk_metadata,
                        sd.id as source_id,
                        sd.filename,
                        1 - (dc.embedding <=> %s::vector) as similarity
                    FROM document_chunks dc
                    JOIN source_documents sd ON sd.id = dc.source_document_id
                    JOIN chunk_collections cc ON cc.chunk_id = dc.id
                    JOIN collections c ON c.id = cc.collection_id
                    WHERE c.name = %s
                      AND 1 - (dc.embedding <=> %s::vector) >= %s
                    ORDER BY dc.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (normalized_query, collection_name, normalized_query,
                     threshold, normalized_query, limit)
                )
            
            results = cur.fetchall()
            logger.info(f"Found {len(results)} chunks matching query")
            return results
            
    finally:
        conn.close()
```

## Updated CLI Commands

Add these new commands to `src/cli.py`:

```python
@cli.command(name="ingest-file")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--collection", default="default", help="Collection name")
@click.option("--chunk-size", type=int, help="Chunk size (default: 1000)")
@click.option("--chunk-overlap", type=int, help="Chunk overlap (default: 200)")
def ingest_file_cmd(file_path, collection, chunk_size, chunk_overlap):
    """Ingest a text file, chunk it, and store embeddings."""
    from rich.console import Console
    from .document_store import DocumentStore
    from .chunking import ChunkingConfig, DocumentChunker
    
    console = Console()
    
    # Create chunker with custom config if provided
    config = ChunkingConfig()
    if chunk_size:
        config.chunk_size = chunk_size
    if chunk_overlap:
        config.chunk_overlap = chunk_overlap
    
    chunker = DocumentChunker(config)
    doc_store = DocumentStore(chunker=chunker)
    
    try:
        with console.status(f"[bold green]Ingesting {file_path}..."):
            source_id, chunk_ids = doc_store.ingest_file(
                file_path=file_path,
                collection_name=collection,
            )
        
        console.print(f"✅ [green]Successfully ingested document![/green]")
        console.print(f"   Source Document ID: [cyan]{source_id}[/cyan]")
        console.print(f"   Chunks created: [yellow]{len(chunk_ids)}[/yellow]")
        console.print(f"   Collection: [magenta]{collection}[/magenta]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        raise click.Abort()


@cli.command(name="ingest-text")
@click.argument("text")
@click.option("--collection", default="default", help="Collection name")
@click.option("--filename", default="inline_text", help="Document name")
def ingest_text_cmd(text, collection, filename):
    """Ingest text directly from command line."""
    from rich.console import Console
    from .document_store import DocumentStore
    
    console = Console()
    doc_store = DocumentStore()
    
    try:
        source_id, chunk_ids = doc_store.ingest_document(
            content=text,
            filename=filename,
            collection_name=collection,
            file_type="text",
        )
        
        console.print(f"✅ Text ingested: ID {source_id}, {len(chunk_ids)} chunks")
        
    except Exception as e:
        console.print(f"❌ Error: {e}")
        raise click.Abort()


@cli.command(name="ingest-directory")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--collection", default="default", help="Collection name")
@click.option("--pattern", default="*.txt", help="File pattern (e.g., *.txt, *.md)")
def ingest_directory_cmd(directory, collection, pattern):
    """Ingest all matching files from a directory."""
    from rich.console import Console
    from rich.progress import track
    from pathlib import Path
    from .document_store import DocumentStore
    
    console = Console()
    doc_store = DocumentStore()
    path = Path(directory)
    
    # Find matching files
    files = list(path.rglob(pattern))
    
    if not files:
        console.print(f"⚠️  No files matching '{pattern}' found")
        return
    
    console.print(f"Found [yellow]{len(files)}[/yellow] files to ingest...")
    
    successful = 0
    failed = 0
    total_chunks = 0
    
    for file_path in track(files, description="Ingesting..."):
        try:
            source_id, chunk_ids = doc_store.ingest_file(
                file_path=str(file_path),
                collection_name=collection,
            )
            successful += 1
            total_chunks += len(chunk_ids)
        except Exception as e:
            logger.error(f"Failed to ingest {file_path}: {e}")
            failed += 1
    
    console.print(f"\n✅ [green]Ingestion complete![/green]")
    console.print(f"   Successful: [green]{successful}[/green] files")
    console.print(f"   Failed: [red]{failed}[/red] files")
    console.print(f"   Total chunks: [yellow]{total_chunks}[/yellow]")


@cli.command(name="list-documents")
@click.option("--collection", help="Filter by collection")
def list_documents_cmd(collection):
    """List all ingested source documents."""
    from rich.console import Console
    from rich.table import Table
    from .document_store import DocumentStore
    
    console = Console()
    doc_store = DocumentStore()
    
    docs = doc_store.list_source_documents(collection_name=collection)
    
    if not docs:
        console.print("No documents found.")
        return
    
    # Create table
    table = Table(
        title=f"Source Documents{' in ' + collection if collection else ''}"
    )
    
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Filename", style="green")
    table.add_column("Type", style="yellow", width=8)
    table.add_column("Chunks", style="magenta", width=8)
    table.add_column("Size", style="blue", width=12)
    table.add_column("Created", style="white")
    
    for doc in docs:
        table.add_row(
            str(doc["id"]),
            doc["filename"],
            doc["file_type"],
            str(doc["chunk_count"]),
            f"{doc['file_size']:,}",
            doc["created_at"].strftime("%Y-%m-%d %H:%M"),
        )
    
    console.print(table)


@cli.command(name="view-document")
@click.argument("document_id", type=int)
@click.option("--show-chunks", is_flag=True, help="Show all chunks")
def view_document_cmd(document_id, show_chunks):
    """View a source document and optionally its chunks."""
    from rich.console import Console
    from rich.panel import Panel
    from .document_store import DocumentStore
    
    console = Console()
    doc_store = DocumentStore()
    
    # Get document
    doc = doc_store.get_source_document(document_id)
    if not doc:
        console.print(f"❌ Document {document_id} not found")
        return
    
    # Display document info
    console.print(Panel(
        f"[bold]Filename:[/bold] {doc['filename']}\n"
        f"[bold]Type:[/bold] {doc['file_type']}\n"
        f"[bold]Size:[/bold] {doc['file_size']:,} chars\n"
        f"[bold]Created:[/bold] {doc['created_at']}",
        title=f"Document {document_id}",
        border_style="green"
    ))
    
    # Get chunks
    conn = get_connection()
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT chunk_index, content, char_start, char_end
                FROM document_chunks
                WHERE source_document_id = %s
                ORDER BY chunk_index
                """,
                (document_id,)
            )
            chunks = cur.fetchall()
    finally:
        conn.close()
    
    console.print(f"\n[bold]Chunks:[/bold] {len(chunks)} total\n")
    
    if show_chunks and chunks:
        for chunk in chunks:
            preview = chunk['content'][:150] + "..." if len(chunk['content']) > 150 else chunk['content']
            console.print(Panel(
                f"[bold]Position:[/bold] chars {chunk['char_start']}-{chunk['char_end']}\n"
                f"[bold]Length:[/bold] {len(chunk['content'])} chars\n\n"
                f"{preview}",
                title=f"Chunk {chunk['chunk_index']}",
                border_style="blue"
            ))
    elif not show_chunks:
        console.print("[dim]Use --show-chunks to view chunk contents[/dim]")


@cli.command(name="search")
@click.argument("query")
@click.option("--collection", default="default", help="Collection to search")
@click.option("--limit", default=5, help="Max results")
@click.option("--threshold", default=0.3, help="Min similarity score")
@click.option("--show-source", is_flag=True, help="Include full source document")
def search_cmd(query, collection, limit, threshold, show_source):
    """Search document chunks with similarity scoring."""
    from rich.console import Console
    from rich.panel import Panel
    from .search import search_chunks
    
    console = Console()
    
    with console.status("[bold green]Searching..."):
        results = search_chunks(
            query=query,
            collection_name=collection,
            limit=limit,
            threshold=threshold,
            include_source=show_source,
        )
    
    if not results:
        console.print("No results found.")
        return
    
    console.print(f"\n[bold]Found {len(results)} results:[/bold]\n")
    
    for i, result in enumerate(results, 1):
        content = result['chunk_content']
        preview = content[:200] + "..." if len(content) > 200 else content
        
        panel_content = (
            f"[bold cyan]Similarity:[/bold cyan] {result['similarity']:.3f}\n"
            f"[bold green]Source:[/bold green] {result['filename']} "
            f"(ID: {result['source_id']})\n"
            f"[bold yellow]Chunk:[/bold yellow] {result['chunk_index']}\n\n"
            f"{preview}"
        )
        
        if show_source:
            panel_content += f"\n\n[dim]Full document available in result[/dim]"
        
        console.print(Panel(
            panel_content,
            title=f"Result {i}",
            border_style="blue"
        ))
```

## Chunking Configuration Best Practices

### Recommended Settings

```python
# For general text documents
ChunkingConfig(
    chunk_size=1000,     # Good balance of context and precision
    chunk_overlap=200,   # 20% overlap prevents context loss
)

# For very long documents
ChunkingConfig(
    chunk_size=1500,     # Larger chunks for more context
    chunk_overlap=300,   # Proportional overlap
)

# For short snippets or Q&A
ChunkingConfig(
    chunk_size=500,      # Smaller, focused chunks
    chunk_overlap=100,
)
```

### Why These Parameters?

**chunk_size=1000**:
- ~250 tokens (safe for 8K token models)
- Focused on 1-2 concepts per chunk
- Better retrieval precision than larger chunks
- Fast to process and search

**chunk_overlap=200**:
- 20% overlap (industry standard)
- Prevents information loss at boundaries
- Related content appears in multiple chunks
- Improves search recall

## Testing Document Chunking

### Test File: `tests/test_document_chunking.py`

```python
"""Test document chunking functionality."""

import pytest
from src.chunking import DocumentChunker, ChunkingConfig
from src.document_store import DocumentStore


def test_basic_chunking():
    """Test that chunking creates appropriate number of chunks."""
    chunker = DocumentChunker()
    
    # Create text that should split into multiple chunks
    text = "This is a test paragraph. " * 100  # ~2500 chars
    chunks = chunker.chunk_text(text)
    
    # Should create 2-3 chunks with default config (1000 size, 200 overlap)
    assert len(chunks) >= 2
    assert len(chunks) <= 4
    
    # Each chunk should be reasonably sized
    for chunk in chunks:
        assert len(chunk.page_content) <= 1200  # chunk_size + some tolerance


def test_chunk_metadata():
    """Verify chunk metadata is correctly set."""
    chunker = DocumentChunker()
    
    text = "Test content. " * 200
    metadata = {"source": "test.txt"}
    
    chunks = chunker.chunk_text(text, metadata)
    
    # Check metadata on each chunk
    for i, chunk in enumerate(chunks):
        assert chunk.metadata["chunk_index"] == i
        assert chunk.metadata["total_chunks"] == len(chunks)
        assert chunk.metadata["source"] == "test.txt"
        assert "char_start" in chunk.metadata
        assert "char_end" in chunk.metadata


def test_document_ingestion(tmp_path):
    """Test full document ingestion workflow."""
    # Create a test file
    test_file = tmp_path / "test_doc.txt"
    test_content = "This is a test document. " * 100
    test_file.write_text(test_content)
    
    doc_store = DocumentStore()
    
    # Ingest the file
    source_id, chunk_ids = doc_store.ingest_file(
        file_path=str(test_file),
        collection_name="test_collection"
    )
    
    # Verify results
    assert source_id > 0
    assert len(chunk_ids) > 0
    
    # Retrieve source document
    source_doc = doc_store.get_source_document(source_id)
    assert source_doc is not None
    assert source_doc["filename"] == "test_doc.txt"
    assert source_doc["content"] == test_content


def test_search_returns_chunks():
    """Verify search returns chunk results with source info."""
    from src.search import search_chunks
    
    # This test assumes you've ingested some test data
    # Create test data first, then search
    
    results = search_chunks(
        query="test query",
        collection_name="test_collection",
        limit=5,
    )
    
    # Verify result structure
    for result in results:
        assert "chunk_id" in result
        assert "chunk_content" in result
        assert "source_id" in result
        assert "filename" in result
        assert "similarity" in result
        assert 0 <= result["similarity"] <= 1
```

## Usage Examples

### Example 1: Ingest a Single File

```bash
# Basic ingestion
uv run poc ingest-file ./my_document.txt --collection my_docs

# With custom chunking
uv run poc ingest-file ./large_doc.txt \
    --collection docs \
    --chunk-size 1500 \
    --chunk-overlap 300
```

### Example 2: Ingest Directory of Files

```bash
# Ingest all text files
uv run poc ingest-directory ./documents --pattern "*.txt"

# Ingest markdown files into specific collection
uv run poc ingest-directory ./articles \
    --pattern "*.md" \
    --collection articles
```

### Example 3: Search and View Results

```bash
# Basic search
uv run poc search "postgresql performance"

# Search with source context
uv run poc search "database indexing" \
    --collection docs \
    --limit 10 \
    --threshold 0.5 \
    --show-source

# List what's been ingested
uv run poc list-documents --collection docs

# View a specific document's chunks
uv run poc view-document 5 --show-chunks
```

### Example 4: Python API Usage

```python
from src.document_store import DocumentStore
from src.search import search_chunks

# Initialize
doc_store = DocumentStore()

# Ingest a file
source_id, chunks = doc_store.ingest_file(
    "./README.md",
    collection_name="documentation"
)

# Search the chunks
results = search_chunks(
    query="how to install",
    collection_name="documentation",
    limit=3,
)

# Access results
for result in results:
    print(f"Score: {result['similarity']:.3f}")
    print(f"From: {result['filename']}")
    print(f"Chunk {result['chunk_index']}: {result['chunk_content'][:100]}...")
    print()
```

## Migration Notes

### Updating init.sql

Add the new tables to your `init.sql` file:

```sql
-- Your existing tables remain...

-- Add these new tables:
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

CREATE TABLE chunk_collections (
    chunk_id INTEGER REFERENCES document_chunks(id) ON DELETE CASCADE,
    collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
    PRIMARY KEY (chunk_id, collection_id)
);

-- Indexes
CREATE INDEX document_chunks_embedding_idx ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX document_chunks_source_idx ON document_chunks(source_document_id);
CREATE INDEX document_chunks_metadata_idx ON document_chunks USING gin (metadata);

-- Trigger
CREATE TRIGGER update_source_documents_updated_at 
    BEFORE UPDATE ON source_documents 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
```

### Rebuilding Docker Container

```bash
# Stop and remove existing container
docker-compose down -v

# Rebuild with new schema
docker-compose up -d

# Verify tables were created
docker exec -it pgvector-rag-poc psql -U raguser -d rag_poc -c "\dt"
```

## Success Criteria

This extension is complete when:

✅ Can ingest a text file via CLI  
✅ File is automatically chunked into ~1000 char pieces  
✅ Each chunk gets its own embedding (normalized)  
✅ Chunks are stored in `document_chunks` table  
✅ Full source document stored in `source_documents` table  
✅ Can search and get chunk results with source info  
✅ Can retrieve full source document from chunk result  
✅ Can list all ingested documents  
✅ Can ingest entire directories with file patterns  
✅ Chunk metadata includes position in original document  
✅ Search returns better similarity scores than before (0.7-0.95 range)  

## Troubleshooting

### Common Issues

**Chunks too large/small:**
- Adjust `chunk_size` parameter
- Check if separators are appropriate for your content

**Missing embeddings:**
- Verify OpenAI API key is set
- Check embedding generation is working
- Ensure normalization is being applied

**Search returns no results:**
- Check chunks were actually created: `SELECT COUNT(*) FROM document_chunks;`
- Verify embeddings exist: `SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL;`
- Lower similarity threshold

**Can't retrieve source document:**
- Verify foreign key relationships
- Check source_documents table has data

## Next Steps

After implementing this extension:

1. **Test with real documents** - Ingest some actual files
2. **Validate chunking quality** - Review chunks to ensure they make sense
3. **Test search accuracy** - Verify similarity scores improved
4. **Benchmark performance** - Measure ingestion and search speed
5. **Document findings** - Record what worked well vs what needs tuning

---

## Summary

This extension adds production-ready document ingestion and chunking to your POC:

- **Automated chunking** using LangChain's RecursiveCharacterTextSplitter
- **Optimal parameters**: 1000 char chunks, 200 char overlap
- **Source tracking**: Always know where chunks came from
- **CLI commands**: Easy file and directory ingestion
- **Enhanced search**: Returns chunks with source document context
- **Flexible configuration**: Override chunk settings per ingestion

The implementation is straightforward, builds cleanly on your existing POC, and follows modern RAG best practices.

