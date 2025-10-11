"""Tests for embedding generation and normalization."""

import numpy as np
import pytest

from src.embeddings import EmbeddingGenerator


class TestEmbeddingNormalization:
    """Test vector normalization functionality."""

    def test_normalize_embedding(self):
        """Test that normalize_embedding produces unit-length vectors."""
        embedder = EmbeddingGenerator()

        # Test with a simple vector
        test_vector = [3.0, 4.0]  # Length = 5
        normalized = embedder.normalize_embedding(test_vector)

        # Check that norm is 1.0
        norm = np.linalg.norm(normalized)
        assert abs(norm - 1.0) < 1e-6, f"Normalized vector should have norm 1.0, got {norm}"

        # Check values are correct
        assert abs(normalized[0] - 0.6) < 1e-6
        assert abs(normalized[1] - 0.8) < 1e-6

    def test_normalize_zero_vector(self):
        """Test handling of zero vector."""
        embedder = EmbeddingGenerator()

        zero_vector = [0.0, 0.0, 0.0]
        normalized = embedder.normalize_embedding(zero_vector)

        # Should return zero vector unchanged
        assert normalized == [0.0, 0.0, 0.0]

    def test_normalize_already_normalized(self):
        """Test normalizing an already normalized vector."""
        embedder = EmbeddingGenerator()

        # Unit vector
        unit_vector = [1.0, 0.0, 0.0]
        normalized = embedder.normalize_embedding(unit_vector)

        # Should remain unchanged
        norm = np.linalg.norm(normalized)
        assert abs(norm - 1.0) < 1e-6

    def test_verify_normalization(self):
        """Test the verify_normalization method."""
        embedder = EmbeddingGenerator()

        # Normalized vector
        normalized_vector = [0.6, 0.8]
        assert embedder.verify_normalization(normalized_vector) is True

        # Non-normalized vector
        non_normalized_vector = [3.0, 4.0]
        assert embedder.verify_normalization(non_normalized_vector) is False

    def test_embedding_dimension(self):
        """Test get_embedding_dimension method."""
        embedder_small = EmbeddingGenerator(model="text-embedding-3-small")
        assert embedder_small.get_embedding_dimension() == 1536

        embedder_large = EmbeddingGenerator(model="text-embedding-3-large")
        assert embedder_large.get_embedding_dimension() == 3072


class TestEmbeddingGeneration:
    """Test embedding generation with OpenAI API."""

    @pytest.mark.skip(reason="Requires OpenAI API key and makes actual API calls")
    def test_generate_embedding(self):
        """Test generating a single embedding."""
        embedder = EmbeddingGenerator()

        text = "PostgreSQL is a powerful database system"
        embedding = embedder.generate_embedding(text, normalize=True)

        # Check that embedding has correct dimension
        assert len(embedding) == 1536

        # Check that it's normalized
        assert embedder.verify_normalization(embedding) is True

    @pytest.mark.skip(reason="Requires OpenAI API key and makes actual API calls")
    def test_generate_embeddings_batch(self):
        """Test generating multiple embeddings in batch."""
        embedder = EmbeddingGenerator()

        texts = [
            "PostgreSQL is a database",
            "Python is a programming language",
            "Machine learning uses neural networks",
        ]

        embeddings = embedder.generate_embeddings(texts, normalize=True)

        # Check correct number of embeddings
        assert len(embeddings) == len(texts)

        # Check all are normalized
        for embedding in embeddings:
            assert len(embedding) == 1536
            assert embedder.verify_normalization(embedding) is True

    def test_empty_text_raises_error(self):
        """Test that empty text raises ValueError."""
        embedder = EmbeddingGenerator()

        with pytest.raises(ValueError, match="Cannot generate embedding for empty text"):
            embedder.generate_embedding("")

        with pytest.raises(ValueError, match="Cannot generate embedding for empty text"):
            embedder.generate_embedding("   ")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
