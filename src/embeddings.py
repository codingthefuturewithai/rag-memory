"""Embedding generation with OpenAI and vector normalization."""

import logging
import os
from typing import List

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates and normalizes embeddings using OpenAI's API."""

    def __init__(self, api_key: str = None, model: str = "text-embedding-3-small"):
        """
        Initialize the embedding generator.

        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY from env.
            model: OpenAI embedding model to use (default: text-embedding-3-small).
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Set it in .env or pass api_key parameter."
            )

        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        logger.info(f"EmbeddingGenerator initialized with model: {model}")

    def normalize_embedding(self, embedding: List[float]) -> List[float]:
        """
        Normalize vector to unit length for accurate cosine similarity.

        This is CRITICAL for getting proper similarity scores (0.7-0.95 range).
        Without normalization, scores can be artificially low (0.3 range).

        Args:
            embedding: Raw embedding vector from OpenAI.

        Returns:
            Normalized embedding vector with unit length.
        """
        arr = np.array(embedding)
        norm = np.linalg.norm(arr)

        if norm == 0:
            logger.warning("Zero-norm embedding detected, returning as-is")
            return arr.tolist()

        normalized = (arr / norm).tolist()
        logger.debug(f"Normalized embedding: original norm={norm:.4f}, new norm=1.0")
        return normalized

    def generate_embedding(self, text: str, normalize: bool = True) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed.
            normalize: Whether to normalize the embedding (recommended: True).

        Returns:
            Embedding vector (normalized if normalize=True).
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        try:
            logger.debug(f"Generating embedding for text (length: {len(text)} chars)")
            response = self.client.embeddings.create(input=text, model=self.model)

            embedding = response.data[0].embedding

            if normalize:
                embedding = self.normalize_embedding(embedding)
                logger.debug("Embedding normalized to unit length")

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def generate_embeddings(
        self, texts: List[str], normalize: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a single API call.

        Args:
            texts: List of input texts to embed.
            normalize: Whether to normalize embeddings (recommended: True).

        Returns:
            List of embedding vectors (normalized if normalize=True).
        """
        if not texts:
            raise ValueError("Cannot generate embeddings for empty text list")

        # Filter out empty texts
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            raise ValueError("All texts are empty")

        try:
            logger.debug(
                f"Generating embeddings for {len(valid_texts)} texts in batch"
            )
            response = self.client.embeddings.create(
                input=valid_texts, model=self.model
            )

            embeddings = [item.embedding for item in response.data]

            if normalize:
                embeddings = [self.normalize_embedding(emb) for emb in embeddings]
                logger.debug(f"Normalized {len(embeddings)} embeddings")

            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def verify_normalization(self, embedding: List[float]) -> bool:
        """
        Verify that an embedding is properly normalized (unit length).

        Args:
            embedding: Embedding vector to check.

        Returns:
            True if embedding has unit length (within tolerance).
        """
        arr = np.array(embedding)
        norm = np.linalg.norm(arr)

        # Allow small tolerance for floating point errors
        is_normalized = abs(norm - 1.0) < 1e-6

        if is_normalized:
            logger.debug(f"Embedding is normalized: norm={norm:.10f}")
        else:
            logger.warning(f"Embedding is NOT normalized: norm={norm:.10f}")

        return is_normalized

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings for the current model.

        Returns:
            Embedding dimension (1536 for text-embedding-3-small).
        """
        # Model dimension mapping
        dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return dimensions.get(self.model, 1536)


def get_embedding_generator(
    api_key: str = None, model: str = "text-embedding-3-small"
) -> EmbeddingGenerator:
    """
    Factory function to get an EmbeddingGenerator instance.

    Args:
        api_key: OpenAI API key (optional, uses env var if not provided).
        model: OpenAI embedding model to use.

    Returns:
        Configured EmbeddingGenerator instance.
    """
    return EmbeddingGenerator(api_key=api_key, model=model)
