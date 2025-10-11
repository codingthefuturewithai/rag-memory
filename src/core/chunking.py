"""Document chunking using LangChain text splitters."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
                "\n## ",  # Markdown H2
                "\n### ",  # Markdown H3
                "\n#### ",  # Markdown H4
                "\n\n",  # Paragraph breaks
                "\n",  # Line breaks
                ". ",  # Sentence endings
                " ",  # Word boundaries
                "",  # Character-level fallback
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
        self, text: str, metadata: Optional[Dict[str, Any]] = None
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
        doc = Document(page_content=text, metadata=metadata or {})

        # Split into chunks
        chunks = self.splitter.split_documents([doc])

        # Add chunk-specific metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
            # Approximate character positions (not exact due to overlap)
            chunk.metadata["char_start"] = i * (
                self.config.chunk_size - self.config.chunk_overlap
            )
            chunk.metadata["char_end"] = chunk.metadata["char_start"] + len(
                chunk.page_content
            )

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


def get_document_chunker(config: Optional[ChunkingConfig] = None) -> DocumentChunker:
    """
    Factory function to get a DocumentChunker instance.

    Args:
        config: Optional chunking configuration

    Returns:
        Configured DocumentChunker instance
    """
    return DocumentChunker(config=config)
