"""
tests/test_retriever.py — Unit tests for daemon/retriever.py (HybridRetriever).

All external dependencies (FAISSStore, AtlasStore, EmbeddingService) are
replaced with MagicMock / AsyncMock.  No real embedding or search is performed.

Tests cover:
  - Deduplication: same chunk_id from both stores appears only once (source_store='both')
  - Weighted score formula: 0.6 * faiss_score + 0.4 * atlas_score
  - Result cap at 8 items
  - Returns fewer than 8 when not enough unique chunks
  - Results are sorted by final score descending
  - Every result has the required set of keys
"""

import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from retriever import HybridRetriever  # noqa: E402

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {
    "chunk_id",
    "source_file",
    "timestamp",
    "log_level",
    "content",
    "score",
    "source_store",
}


def _make_chunk_dict(chunk_id: str, score: float, source: str = "faiss") -> dict:
    """Create a minimal chunk dict as returned by a store's search method."""
    return {
        "chunk_id": chunk_id,
        "source_file": "kern.log",
        "timestamp": "2026-06-04T10:00:00Z",
        "log_level": "ERROR",
        "content": f"OOM event for chunk {chunk_id}",
        "score": score,
        "source_store": source,
    }


def _make_retriever(
    faiss_results: list[dict],
    atlas_results: list[dict],
) -> HybridRetriever:
    """
    Build a HybridRetriever with mocked stores and embedder.

    The embedder.embed_single() returns np.zeros(384).
    FAISS search is mocked synchronously; Atlas search is mocked async.
    """
    mock_embedder = MagicMock()
    mock_embedder.embed_single = MagicMock(return_value=np.zeros(384, dtype=np.float32))

    mock_faiss = MagicMock()
    mock_faiss.search = MagicMock(return_value=faiss_results)

    mock_atlas = MagicMock()
    mock_atlas.vector_search = AsyncMock(return_value=atlas_results)

    executor = ThreadPoolExecutor(max_workers=2)

    return HybridRetriever(
        faiss_store=mock_faiss,
        atlas_store=mock_atlas,
        embedder=mock_embedder,
        executor=executor,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Tests for cross-store deduplication and weighted scoring."""

    @pytest.mark.asyncio
    async def test_deduplication_same_chunk_id_appears_once(self) -> None:
        """When both FAISS and Atlas return the same chunk_id, only one result is emitted.

        The source_store must be 'both' and the score must follow
        the formula: 0.6 * faiss_score + 0.4 * atlas_score.
        """
        faiss_chunk = _make_chunk_dict("abc123", score=0.8, source="faiss")
        atlas_chunk = _make_chunk_dict("abc123", score=0.7, source="atlas")

        retriever = _make_retriever([faiss_chunk], [atlas_chunk])
        results = await retriever.retrieve("test query", k_each=1)

        matching = [r for r in results if r["chunk_id"] == "abc123"]
        assert len(matching) == 1, (
            f"Expected exactly one result for chunk_id='abc123', got {len(matching)}"
        )

        result = matching[0]
        assert result["source_store"] == "both", (
            f"Expected source_store='both' for merged chunk, got {result['source_store']!r}"
        )

        expected_score = 0.6 * 0.8 + 0.4 * 0.7
        assert result["score"] == pytest.approx(expected_score, rel=1e-3), (
            f"Expected score {expected_score:.4f}, got {result['score']:.4f}"
        )


class TestResultCap:
    """Tests for the hard cap of 8 returned results."""

    @pytest.mark.asyncio
    async def test_returns_max_8_results(self) -> None:
        """When FAISS and Atlas each return 5 unique chunks, at most 8 are returned."""
        faiss_chunks = [_make_chunk_dict(f"f{i}", score=0.9 - i * 0.05) for i in range(5)]
        atlas_chunks = [_make_chunk_dict(f"a{i}", score=0.85 - i * 0.05) for i in range(5)]

        retriever = _make_retriever(faiss_chunks, atlas_chunks)
        results = await retriever.retrieve("test", k_each=5)

        assert len(results) <= 8, (
            f"Expected at most 8 results (cap), got {len(results)}"
        )

    @pytest.mark.asyncio
    async def test_returns_fewer_than_8_when_not_enough(self) -> None:
        """When only 4 unique chunks exist across both stores, exactly 4 are returned."""
        faiss_chunks = [_make_chunk_dict(f"f{i}", score=0.8 - i * 0.1) for i in range(2)]
        atlas_chunks = [_make_chunk_dict(f"a{i}", score=0.75 - i * 0.1) for i in range(2)]

        retriever = _make_retriever(faiss_chunks, atlas_chunks)
        results = await retriever.retrieve("test", k_each=2)

        assert len(results) == 4, (
            f"Expected exactly 4 results with 4 unique chunks, got {len(results)}"
        )


class TestOrdering:
    """Tests for descending score ordering of results."""

    @pytest.mark.asyncio
    async def test_results_sorted_by_final_score_descending(self) -> None:
        """Results must be in descending order of final score."""
        faiss_chunks = [
            _make_chunk_dict("f0", score=0.5),
            _make_chunk_dict("f1", score=0.9),
            _make_chunk_dict("f2", score=0.3),
            _make_chunk_dict("f3", score=0.7),
            _make_chunk_dict("f4", score=0.1),
        ]
        atlas_chunks = [
            _make_chunk_dict("a0", score=0.6),
            _make_chunk_dict("a1", score=0.8),
            _make_chunk_dict("a2", score=0.2),
            _make_chunk_dict("a3", score=0.4),
            _make_chunk_dict("a4", score=0.95),
        ]

        retriever = _make_retriever(faiss_chunks, atlas_chunks)
        results = await retriever.retrieve("test", k_each=5)

        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True), (
            f"Results are not sorted descending by score: {scores}"
        )


class TestRequiredKeys:
    """Tests that every result dict has the full required key set."""

    @pytest.mark.asyncio
    async def test_all_required_keys_present(self) -> None:
        """Every result dict must contain all required keys."""
        faiss_chunks = [_make_chunk_dict(f"f{i}", score=0.9 - i * 0.1) for i in range(3)]
        atlas_chunks = [_make_chunk_dict(f"a{i}", score=0.8 - i * 0.1) for i in range(3)]

        retriever = _make_retriever(faiss_chunks, atlas_chunks)
        results = await retriever.retrieve("test", k_each=3)

        for result in results:
            missing = REQUIRED_KEYS - result.keys()
            assert not missing, (
                f"Result for chunk_id={result.get('chunk_id')!r} "
                f"is missing required keys: {missing}"
            )
