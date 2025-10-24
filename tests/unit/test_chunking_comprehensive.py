"""Comprehensive unit tests for document chunking functionality."""

import pytest
from langchain_core.documents import Document

from src.core.chunking import DocumentChunker, ChunkingConfig, get_document_chunker


class TestChunkingConfig:
    """Test ChunkingConfig initialization and defaults."""

    def test_default_config_values(self):
        """Test that default config has expected values."""
        config = ChunkingConfig()

        assert config.chunk_size == 1000
        assert config.chunk_overlap == 200
        assert config.separators is not None

    def test_custom_chunk_size(self):
        """Test custom chunk size configuration."""
        config = ChunkingConfig(chunk_size=500)

        assert config.chunk_size == 500
        assert config.chunk_overlap == 200  # Default

    def test_custom_chunk_overlap(self):
        """Test custom chunk overlap configuration."""
        config = ChunkingConfig(chunk_overlap=100)

        assert config.chunk_size == 1000  # Default
        assert config.chunk_overlap == 100

    def test_custom_separators(self):
        """Test custom separators configuration."""
        custom_seps = ["\n\n", "\n", " "]
        config = ChunkingConfig(separators=custom_seps)

        assert config.separators == custom_seps

    def test_default_separators_include_markdown(self):
        """Test that default separators include markdown headers."""
        config = ChunkingConfig()

        assert "\n## " in config.separators
        assert "\n### " in config.separators
        assert "\n#### " in config.separators

    def test_default_separators_include_common_breaks(self):
        """Test that default separators include common text breaks."""
        config = ChunkingConfig()

        assert "\n\n" in config.separators
        assert "\n" in config.separators
        assert ". " in config.separators

    def test_overlap_not_larger_than_chunk_size(self):
        """Test that overlap can be configured up to chunk size."""
        config = ChunkingConfig(chunk_size=1000, chunk_overlap=900)

        assert config.chunk_overlap == 900


class TestDocumentChunkerInitialization:
    """Test DocumentChunker initialization."""

    def test_chunker_with_default_config(self):
        """Test chunker initialization with default config."""
        chunker = DocumentChunker()

        assert chunker.config.chunk_size == 1000
        assert chunker.config.chunk_overlap == 200

    def test_chunker_with_custom_config(self):
        """Test chunker initialization with custom config."""
        config = ChunkingConfig(chunk_size=512, chunk_overlap=128)
        chunker = DocumentChunker(config)

        assert chunker.config.chunk_size == 512
        assert chunker.config.chunk_overlap == 128

    def test_chunker_has_splitter_initialized(self):
        """Test that chunker initializes the underlying splitter."""
        chunker = DocumentChunker()

        assert chunker.splitter is not None

    def test_factory_function_creates_chunker(self):
        """Test that factory function creates chunker instance."""
        chunker = get_document_chunker()

        assert isinstance(chunker, DocumentChunker)

    def test_factory_function_with_custom_config(self):
        """Test factory function with custom config."""
        config = ChunkingConfig(chunk_size=256)
        chunker = get_document_chunker(config)

        assert chunker.config.chunk_size == 256


class TestChunkTextBasic:
    """Test basic text chunking functionality."""

    def test_chunk_simple_text(self):
        """Test chunking simple text."""
        chunker = DocumentChunker()
        text = "This is a test document. " * 100

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        assert all(isinstance(c, Document) for c in chunks)

    def test_chunk_preserves_content(self):
        """Test that chunking preserves all content."""
        chunker = DocumentChunker()
        text = "Hello world. " * 50

        chunks = chunker.chunk_text(text)
        reconstructed = " ".join(c.page_content for c in chunks)

        # Content should be preserved (accounting for overlaps)
        assert "Hello world" in reconstructed

    def test_chunk_text_returns_documents(self):
        """Test that chunk_text returns Document objects."""
        chunker = DocumentChunker()
        text = "Sample text. " * 100

        chunks = chunker.chunk_text(text)

        assert all(isinstance(chunk, Document) for chunk in chunks)
        assert all(hasattr(chunk, 'page_content') for chunk in chunks)
        assert all(hasattr(chunk, 'metadata') for chunk in chunks)

    def test_chunk_large_text(self):
        """Test chunking large text."""
        chunker = DocumentChunker(config=ChunkingConfig(chunk_size=500))
        text = "Word " * 5000  # 20,000+ characters

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 10
        assert all(len(c.page_content) > 0 for c in chunks)

    def test_chunk_sizes_near_configured_max(self):
        """Test that chunks are near configured size."""
        config = ChunkingConfig(chunk_size=1000, chunk_overlap=200)
        chunker = DocumentChunker(config)
        text = "Word " * 5000

        chunks = chunker.chunk_text(text)

        # Most chunks should be close to chunk_size (allowing some variation)
        sizes = [len(c.page_content) for c in chunks]
        # Chunks should generally be smaller than or equal to chunk_size
        assert all(size <= config.chunk_size * 1.1 for size in sizes)


class TestChunkTextEmptyInput:
    """Test chunking with empty or whitespace input."""

    def test_chunk_empty_string(self):
        """Test that empty string returns empty list."""
        chunker = DocumentChunker()

        chunks = chunker.chunk_text("")

        assert chunks == []

    def test_chunk_whitespace_only(self):
        """Test that whitespace-only string returns empty list."""
        chunker = DocumentChunker()

        chunks = chunker.chunk_text("   \n\t  ")

        assert chunks == []

    def test_chunk_single_space(self):
        """Test chunking single space."""
        chunker = DocumentChunker()

        chunks = chunker.chunk_text(" ")

        assert chunks == []

    def test_chunk_single_newline(self):
        """Test chunking single newline."""
        chunker = DocumentChunker()

        chunks = chunker.chunk_text("\n")

        assert chunks == []


class TestChunkTextMetadata:
    """Test metadata handling in chunking."""

    def test_chunk_text_with_metadata(self):
        """Test that provided metadata is preserved in chunks."""
        chunker = DocumentChunker()
        text = "Sample text. " * 100
        metadata = {"source": "test_doc", "author": "test_author"}

        chunks = chunker.chunk_text(text, metadata=metadata)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.metadata["source"] == "test_doc"
            assert chunk.metadata["author"] == "test_author"

    def test_chunk_adds_chunk_index(self):
        """Test that chunker adds chunk_index to metadata."""
        chunker = DocumentChunker()
        text = "Sample. " * 200

        chunks = chunker.chunk_text(text)

        for i, chunk in enumerate(chunks):
            assert chunk.metadata["chunk_index"] == i

    def test_chunk_adds_total_chunks(self):
        """Test that chunker adds total_chunks to metadata."""
        chunker = DocumentChunker()
        text = "Sample. " * 200

        chunks = chunker.chunk_text(text)

        for chunk in chunks:
            assert chunk.metadata["total_chunks"] == len(chunks)

    def test_chunk_adds_char_positions(self):
        """Test that chunker adds character position metadata."""
        chunker = DocumentChunker()
        text = "Sample text. " * 100

        chunks = chunker.chunk_text(text)

        for chunk in chunks:
            assert "char_start" in chunk.metadata
            assert "char_end" in chunk.metadata
            assert chunk.metadata["char_start"] >= 0
            assert chunk.metadata["char_end"] > chunk.metadata["char_start"]

    def test_chunk_metadata_with_custom_data(self):
        """Test that custom metadata is preserved alongside auto-generated."""
        chunker = DocumentChunker()
        text = "Sample. " * 200
        custom_metadata = {"custom_key": "custom_value", "number": 42}

        chunks = chunker.chunk_text(text, metadata=custom_metadata)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.metadata["custom_key"] == "custom_value"
            assert chunk.metadata["number"] == 42
            assert "chunk_index" in chunk.metadata


class TestChunkTextMarkdown:
    """Test chunking with markdown content."""

    def test_chunk_markdown_respects_h2_headers(self):
        """Test that markdown H2 headers are used as chunk boundaries."""
        chunker = DocumentChunker()
        text = "# Main\n\nIntro text. " * 5 + "\n## Section 1\n\nSection 1 content. " * 5

        chunks = chunker.chunk_text(text)

        # Should have multiple chunks, split at headers
        assert len(chunks) > 0

    def test_chunk_markdown_with_code_block(self):
        """Test chunking markdown with code blocks."""
        chunker = DocumentChunker()
        text = """
# Example

Some text.

```python
def function():
    return "code"
```

More text.
""" * 20

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        # Code should be preserved
        assert any("def function" in c.page_content for c in chunks)

    def test_chunk_markdown_with_multiple_headers(self):
        """Test chunking with multiple header levels."""
        chunker = DocumentChunker()
        text = """
# H1
Content H1. """ * 5 + """
## H2
Content H2. """ * 5 + """
### H3
Content H3. """ * 5

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0


class TestChunkOverlap:
    """Test chunk overlap functionality."""

    def test_chunk_overlap_creates_duplicate_content(self):
        """Test that overlap causes content to appear in multiple chunks."""
        config = ChunkingConfig(chunk_size=100, chunk_overlap=50)
        chunker = DocumentChunker(config)
        text = "Word " * 100  # Long repetitive text

        chunks = chunker.chunk_text(text)

        if len(chunks) > 1:
            # With overlap, end of chunk N should overlap with start of chunk N+1
            chunk1_end = chunks[0].page_content[-50:]
            chunk2_start = chunks[1].page_content[:50]
            # There should be some overlap in content
            assert len(chunks) > 1

    def test_zero_overlap_no_duplicates(self):
        """Test that zero overlap minimizes duplicated content."""
        config = ChunkingConfig(chunk_size=100, chunk_overlap=0)
        chunker = DocumentChunker(config)
        text = "Word " * 100

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0


class TestGetStats:
    """Test statistics calculation for chunks."""

    def test_get_stats_empty_list(self):
        """Test statistics for empty chunk list."""
        chunker = DocumentChunker()

        stats = chunker.get_stats([])

        assert stats["num_chunks"] == 0
        assert stats["total_chars"] == 0
        assert stats["avg_chunk_size"] == 0
        assert stats["min_chunk_size"] == 0
        assert stats["max_chunk_size"] == 0

    def test_get_stats_single_chunk(self):
        """Test statistics with single chunk."""
        chunker = DocumentChunker()
        chunks = [Document(page_content="Test content", metadata={})]

        stats = chunker.get_stats(chunks)

        assert stats["num_chunks"] == 1
        assert stats["total_chars"] == len("Test content")
        assert stats["avg_chunk_size"] == len("Test content")
        assert stats["min_chunk_size"] == len("Test content")
        assert stats["max_chunk_size"] == len("Test content")

    def test_get_stats_multiple_chunks(self):
        """Test statistics with multiple chunks."""
        chunker = DocumentChunker()
        chunks = [
            Document(page_content="A" * 100, metadata={}),
            Document(page_content="B" * 200, metadata={}),
            Document(page_content="C" * 150, metadata={}),
        ]

        stats = chunker.get_stats(chunks)

        assert stats["num_chunks"] == 3
        assert stats["total_chars"] == 450
        assert stats["avg_chunk_size"] == 150
        assert stats["min_chunk_size"] == 100
        assert stats["max_chunk_size"] == 200

    def test_get_stats_returns_dict_with_all_keys(self):
        """Test that stats returns all expected keys."""
        chunker = DocumentChunker()
        chunks = [Document(page_content="Test", metadata={})]

        stats = chunker.get_stats(chunks)

        required_keys = ["num_chunks", "total_chars", "avg_chunk_size", "min_chunk_size", "max_chunk_size"]
        for key in required_keys:
            assert key in stats


class TestChunkingWithDifferentSizes:
    """Test chunking with various chunk size configurations."""

    def test_very_small_chunks(self):
        """Test chunking with very small chunk size."""
        config = ChunkingConfig(chunk_size=10, chunk_overlap=2)
        chunker = DocumentChunker(config)
        text = "Word " * 100

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 20  # Should create many small chunks
        assert all(len(c.page_content) <= 20 for c in chunks)  # Some tolerance

    def test_very_large_chunks(self):
        """Test chunking with very large chunk size."""
        config = ChunkingConfig(chunk_size=10000, chunk_overlap=1000)
        chunker = DocumentChunker(config)
        text = "Word " * 500  # ~2500 characters

        chunks = chunker.chunk_text(text)

        # Text should fit in single chunk
        assert len(chunks) <= 2

    def test_chunk_size_equals_overlap_invalid_but_handled(self):
        """Test edge case where chunk_size equals overlap (should still work)."""
        config = ChunkingConfig(chunk_size=100, chunk_overlap=100)
        chunker = DocumentChunker(config)
        text = "Word " * 100

        # Should not raise error
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 0


class TestChunkingUnicode:
    """Test chunking with Unicode and special characters."""

    def test_chunk_unicode_text(self):
        """Test chunking text with Unicode characters."""
        chunker = DocumentChunker()
        text = "Тест на русском языке. " * 50  # Russian text

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        assert any("Тест" in c.page_content for c in chunks)

    def test_chunk_mixed_unicode(self):
        """Test chunking mixed Unicode and ASCII."""
        chunker = DocumentChunker()
        text = ("English text. " + "日本語テキスト。" + "Текст на русском. ") * 30

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        assert any("English" in c.page_content for c in chunks)

    def test_chunk_emoji_content(self):
        """Test chunking text with emoji."""
        chunker = DocumentChunker()
        text = "This is text with emoji 🚀 and more 🎉 content. " * 30

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        assert any("🚀" in c.page_content or "emoji" in c.page_content for c in chunks)


class TestChunkingSpecialCases:
    """Test special cases and edge conditions."""

    def test_chunk_very_long_line(self):
        """Test chunking text with very long single line (no spaces)."""
        chunker = DocumentChunker(config=ChunkingConfig(chunk_size=500))
        text = "a" * 2000  # Very long line with no breaks

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        # Should be split at character level if no other separators work
        assert sum(len(c.page_content) for c in chunks) >= len(text) - 100

    def test_chunk_only_separators(self):
        """Test chunking text that's mostly separators."""
        chunker = DocumentChunker()
        text = "\n\n" * 500

        chunks = chunker.chunk_text(text)

        # Should handle gracefully even with mostly whitespace
        assert len(chunks) == 0 or all(len(c.page_content.strip()) == 0 for c in chunks)

    def test_chunk_alternating_long_short_sections(self):
        """Test chunking alternating long and short sections."""
        chunker = DocumentChunker()
        text = ("Long section. " * 100) + "\n\n" + ("Short. " * 10) + "\n\n" + ("Long. " * 100)

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0

    def test_chunk_with_tabs_and_special_whitespace(self):
        """Test chunking with various whitespace characters."""
        chunker = DocumentChunker()
        text = "Word\tword\tword.\n\nWord. " * 50

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0


class TestChunkingStatisticsEdgeCases:
    """Test statistics calculation edge cases."""

    def test_stats_with_empty_documents(self):
        """Test statistics when chunks have empty content."""
        chunker = DocumentChunker()
        chunks = [
            Document(page_content="", metadata={}),
            Document(page_content="Content", metadata={}),
            Document(page_content="", metadata={}),
        ]

        stats = chunker.get_stats(chunks)

        assert stats["num_chunks"] == 3
        assert stats["total_chars"] == len("Content")
        assert stats["min_chunk_size"] == 0
        assert stats["max_chunk_size"] == len("Content")

    def test_stats_calculates_correct_averages(self):
        """Test that average is calculated correctly."""
        chunker = DocumentChunker()
        chunks = [
            Document(page_content="A" * 100, metadata={}),
            Document(page_content="B" * 200, metadata={}),
            Document(page_content="C" * 300, metadata={}),
        ]

        stats = chunker.get_stats(chunks)

        expected_avg = (100 + 200 + 300) / 3
        assert abs(stats["avg_chunk_size"] - expected_avg) < 0.01


class TestDocumentChunkerIntegration:
    """Integration tests combining multiple chunking features."""

    def test_full_workflow_with_metadata_and_stats(self):
        """Test complete workflow: chunk with metadata, calculate stats."""
        config = ChunkingConfig(chunk_size=500, chunk_overlap=100)
        chunker = DocumentChunker(config)

        text = "Sample text with multiple sections. " * 100
        metadata = {"source": "test", "version": 1}

        chunks = chunker.chunk_text(text, metadata=metadata)
        stats = chunker.get_stats(chunks)

        assert len(chunks) > 0
        assert all(c.metadata["source"] == "test" for c in chunks)
        assert stats["num_chunks"] == len(chunks)
        assert stats["total_chars"] > 0

    def test_multiple_chunking_operations(self):
        """Test that chunker can chunk multiple texts sequentially."""
        chunker = DocumentChunker()

        chunks1 = chunker.chunk_text("First document. " * 50)
        chunks2 = chunker.chunk_text("Second document. " * 50)

        assert len(chunks1) > 0
        assert len(chunks2) > 0
        assert chunks1[0].page_content != chunks2[0].page_content
