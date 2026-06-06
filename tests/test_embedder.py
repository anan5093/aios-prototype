"""
tests/test_embedder.py — Unit tests for daemon/embedder.py.

Tests cover:
  - Output shape for batch and single embedding
  - L2 normalisation guarantee
  - Cosine similarity between semantically similar / dissimilar texts
  - Lazy model loading behaviour
  - chunk_text splitting on long input
"""

import os
import sys

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — ensure daemon package is on sys.path
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from embedder import EmbeddingService, chunk_text  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmbedBatchShape:
    """Tests for the EmbeddingService.embed() batch method."""

    def test_embed_returns_correct_shape(self) -> None:
        """embed(['test sentence']) must return an ndarray of shape (1, 384)."""
        service = EmbeddingService()
        result: np.ndarray = service.embed(["test sentence"])
        assert result.shape == (1, 384), (
            f"Expected shape (1, 384), got {result.shape}"
        )


class TestEmbedSingle:
    """Tests for EmbeddingService.embed_single()."""

    def test_embed_single_returns_correct_shape(self) -> None:
        """embed_single('test') must return a 1-D array of length 384."""
        service = EmbeddingService()
        result: np.ndarray = service.embed_single("test")
        assert result.shape == (384,), (
            f"Expected shape (384,), got {result.shape}"
        )

    def test_output_is_l2_normalized(self) -> None:
        """The output vector of embed_single must have unit L2 norm (< 1e-5 error)."""
        service = EmbeddingService()
        result: np.ndarray = service.embed_single("test sentence for normalisation")
        norm: float = float(np.linalg.norm(result))
        assert abs(norm - 1.0) < 1e-5, (
            f"Expected L2 norm ≈ 1.0, got {norm:.8f}"
        )


class TestCosineSimilarity:
    """Tests for semantic similarity via cosine distance on unit-norm vectors."""

    def test_similar_texts_high_cosine(self) -> None:
        """Semantically similar OOM texts must have cosine similarity > 0.50."""
        service = EmbeddingService()
        v1: np.ndarray = service.embed_single("Out of memory: Kill process")
        v2: np.ndarray = service.embed_single(
            "OOM killer activated, process terminated"
        )
        # Since vectors are unit-norm, dot product == cosine similarity
        cosine: float = float(np.dot(v1, v2))
        assert cosine > 0.50, (
            f"Expected cosine similarity > 0.50 for similar texts, got {cosine:.4f}"
        )

    def test_dissimilar_texts_low_cosine(self) -> None:
        """Semantically unrelated texts must have cosine similarity < 0.50."""
        service = EmbeddingService()
        v1: np.ndarray = service.embed_single("kernel OOM panic memory error")
        v2: np.ndarray = service.embed_single("git commit pushed to repository")
        cosine: float = float(np.dot(v1, v2))
        assert cosine < 0.50, (
            f"Expected cosine similarity < 0.50 for dissimilar texts, got {cosine:.4f}"
        )


class TestLazyLoading:
    """Tests that EmbeddingService does not load the model at init time."""

    def test_lazy_loading(self) -> None:
        """_model must be None before the first call and non-None after."""
        service = EmbeddingService()
        assert service._model is None, (
            "Model should not be loaded at construction time (lazy loading violated)."
        )
        service.embed_single("trigger load")
        assert service._model is not None, (
            "Model should be loaded after embed_single() is called."
        )


class TestChunkText:
    """Tests for the chunk_text() utility function."""

    def test_chunk_text_splits_long_text(self) -> None:
        """chunk_text on 500 words must produce ≥ 3 chunks, each ≤ 250 chars."""
        text: str = "word " * 500  # 2 500 characters
        chunks: list[str] = chunk_text(text, chunk_size=200, chunk_overlap=20)

        assert len(chunks) >= 3, (
            f"Expected at least 3 chunks for a 2500-char input, got {len(chunks)}"
        )
        for chunk in chunks:
            assert len(chunk) <= 250, (  # 250 = 200 + 20 overlap slack + strip
                f"Chunk exceeds 250 chars: {len(chunk)} chars — '{chunk[:40]}…'"
            )
