"""
Tests for app/services/embedding_service.py using mocked sentence-transformers model.
"""

from unittest import mock
import numpy as np

from app.services.embedding_service import EmbeddingService


def test_embedding_service_mocked_encode():
    """Test encode_text and encode_batch with a mocked model."""
    mock_model = mock.MagicMock()
    mock_model.encode.side_effect = lambda texts, **kwargs: (
        np.ones((len(texts), 384), dtype=np.float32)
        if isinstance(texts, list)
        else np.ones((384,), dtype=np.float32)
    )

    service = EmbeddingService(model_instance=mock_model)
    vec = service.encode_text("Machine Learning Engineer")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (384,)

    batch_vecs = service.encode_batch(["Text 1", "Text 2"])
    assert isinstance(batch_vecs, np.ndarray)
    assert batch_vecs.shape == (2, 384)


def test_calculate_cosine_similarity_identical_vectors():
    """Test that identical vectors yield cosine similarity of 1.0."""
    service = EmbeddingService(model_instance=mock.MagicMock())
    vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    vec2 = np.array([1.0, 2.0, 3.0], dtype=np.float32)

    sim = service.calculate_cosine_similarity(vec1, vec2)
    assert round(sim, 4) == 1.0


def test_calculate_cosine_similarity_orthogonal_vectors():
    """Test that orthogonal vectors yield cosine similarity of 0.0."""
    service = EmbeddingService(model_instance=mock.MagicMock())
    vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    vec2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    sim = service.calculate_cosine_similarity(vec1, vec2)
    assert round(sim, 4) == 0.0


def test_calculate_cosine_similarity_zero_vector():
    """Test that zero vector returns 0.0 without division by zero errors."""
    service = EmbeddingService(model_instance=mock.MagicMock())
    vec1 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    vec2 = np.array([1.0, 2.0, 3.0], dtype=np.float32)

    sim = service.calculate_cosine_similarity(vec1, vec2)
    assert sim == 0.0
