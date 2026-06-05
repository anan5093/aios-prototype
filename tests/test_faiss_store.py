"""
tests/test_faiss_store.py — Unit tests for daemon/faiss_store.py.

Tests cover:
  - Ingesting 10 unique chunks and verifying vector count
  - Search results include 'score' in [0, 1] and 'source_store' == 'faiss'
  - Persistence and reload from disk
  - Deduplication (re-ingesting same chunks leaves count unchanged)
  - Searching an empty index returns an empty list
"""

import os
import sys

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from faiss_store import FAISSStore  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path, name: str = "test") -> FAISSStore:
    """Create a FAISSStore pointing at temporary file paths."""
    index_path = str(tmp_path / f"{name}.index")
    meta_path = str(tmp_path / f"{name}.pkl")
    return FAISSStore(index_path=index_path, metadata_path=meta_path)


def _random_embeddings(n: int, dim: int = 384) -> np.ndarray:
    """Return an (n, dim) float32 ndarray of random unit-norm vectors."""
    rng = np.random.default_rng(seed=42)
    vecs = rng.standard_normal((n, dim)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / norms


def _make_chunks_and_meta(n: int) -> tuple[list[str], list[dict]]:
    """Return n unique chunk strings and matching metadata dicts."""
    chunks = [f"unique log line number {i:04d} — OOM event on process {1000+i}" for i in range(n)]
    meta = [
        {
            "source_file": "kern.log",
            "timestamp": "2026-06-04T10:00:00Z",
            "log_level": "ERROR",
        }
        for _ in range(n)
    ]
    return chunks, meta


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIngest:
    """Tests for FAISSStore.ingest()."""

    def test_ingest_10_chunks(self, tmp_path) -> None:
        """Ingesting 10 unique chunks must result in get_vector_count() == 10."""
        store = _make_store(tmp_path)
        store.load_or_create()

        chunks, meta = _make_chunks_and_meta(10)
        embeddings = _random_embeddings(10)

        store.ingest(chunks, embeddings, meta)

        assert store.get_vector_count() == 10, (
            f"Expected 10 vectors after ingest, got {store.get_vector_count()}"
        )


class TestSearch:
    """Tests for FAISSStore.search()."""

    def test_search_returns_results_with_score(self, tmp_path) -> None:
        """search() must return exactly k results, each with a valid score and source_store."""
        store = _make_store(tmp_path)
        store.load_or_create()

        chunks, meta = _make_chunks_and_meta(10)
        embeddings = _random_embeddings(10)
        store.ingest(chunks, embeddings, meta)

        query = np.random.default_rng(seed=99).standard_normal(384).astype(np.float32)
        results = store.search(query, k=5)

        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        for result in results:
            assert "score" in result, "Result dict is missing 'score' key."
            assert 0.0 <= result["score"] <= 1.0, (
                f"score={result['score']} is not in [0, 1]"
            )
            assert result.get("source_store") == "faiss", (
                f"Expected source_store='faiss', got {result.get('source_store')!r}"
            )

    def test_search_empty_index_returns_empty_list(self, tmp_path) -> None:
        """Searching an empty index must return an empty list without raising."""
        store = _make_store(tmp_path)
        store.load_or_create()

        query = np.random.default_rng(seed=7).standard_normal(384).astype(np.float32)
        results = store.search(query, k=5)

        assert results == [], (
            f"Expected [] for empty index search, got {results}"
        )


class TestPersistence:
    """Tests for FAISSStore.persist() and reload via load_or_create()."""

    def test_persist_and_reload(self, tmp_path) -> None:
        """After persisting, a new FAISSStore instance must reload 10 vectors."""
        index_path = str(tmp_path / "persist.index")
        meta_path = str(tmp_path / "persist.pkl")

        # First store: ingest and auto-persist
        store1 = FAISSStore(index_path=index_path, metadata_path=meta_path)
        store1.load_or_create()
        chunks, meta = _make_chunks_and_meta(10)
        embeddings = _random_embeddings(10)
        store1.ingest(chunks, embeddings, meta)

        # Second store: reload from the same paths
        store2 = FAISSStore(index_path=index_path, metadata_path=meta_path)
        store2.load_or_create()

        assert store2.get_vector_count() == 10, (
            f"Expected 10 vectors after reload, got {store2.get_vector_count()}"
        )


class TestDeduplication:
    """Tests for chunk-level deduplication in FAISSStore.ingest()."""

    def test_deduplication(self, tmp_path) -> None:
        """Re-ingesting the same 10 chunks must not increase the vector count."""
        store = _make_store(tmp_path)
        store.load_or_create()

        chunks, meta = _make_chunks_and_meta(10)
        embeddings = _random_embeddings(10)

        # First ingest
        store.ingest(chunks, embeddings, meta)
        assert store.get_vector_count() == 10

        # Second ingest — same data; must remain 10
        store.ingest(chunks, embeddings, meta)
        assert store.get_vector_count() == 10, (
            f"Expected 10 vectors after duplicate ingest, got {store.get_vector_count()}"
        )
