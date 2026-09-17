"""
Embedding service using sentence-transformers for generating text embeddings and calculating cosine similarity.
"""

import logging
from typing import List, Union
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Manages loading of sentence-transformers models, vector generation,
    and cosine similarity calculations.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", model_instance=None):
        self.model_name = model_name
        self._model = model_instance

    @property
    def model(self):
        """Lazy loader for SentenceTransformer model."""
        if self._model is None:
            logger.info("Loading sentence-transformers model: '%s'", self.model_name)
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode_text(self, text: str) -> np.ndarray:
        """
        Generates a 1D embedding vector for a single text string.
        """
        if not text:
            text = " "
        embedding = self.model.encode(text, convert_to_numpy=True)
        return np.asarray(embedding, dtype=np.float32)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generates 2D embedding vectors for a batch of text strings.
        """
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        sanitized = [t if t and t.strip() else " " for t in texts]
        embeddings = self.model.encode(sanitized, convert_to_numpy=True, batch_size=32)
        return np.asarray(embeddings, dtype=np.float32)

    def calculate_cosine_similarity(
        self, vec1: np.ndarray, vec2: np.ndarray
    ) -> float:
        """
        Calculates normalized cosine similarity between two vectors.

        Note:
            Cosine similarity represents geometric distance in vector space (0.0 to 1.0).
            It measures semantic textual similarity, NOT hiring probability or interview odds.

        Returns:
            float: Score clamped between 0.0 and 1.0.
        """
        v1 = np.asarray(vec1, dtype=np.float32).flatten()
        v2 = np.asarray(vec2, dtype=np.float32).flatten()

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = float(np.dot(v1, v2) / (norm1 * norm2))
        # Clamp to [0.0, 1.0] range
        return max(0.0, min(1.0, similarity))
