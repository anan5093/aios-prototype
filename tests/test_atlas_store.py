"""
tests/test_atlas_store.py — Unit tests for daemon/atlas_store.py.

All motor / MongoDB interactions are mocked with AsyncMock.
No real network connections are made.

Tests cover:
  - Successful connect() call
  - connect() raising RuntimeError on server failure
  - ingest_batch() calling bulk_write with the right operations
  - vector_search() returning correctly shaped results with 'source_store' == 'atlas'
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from atlas_store import AtlasStore  # noqa: E402

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store() -> AtlasStore:
    """Return an AtlasStore pointed at a fake URI."""
    return AtlasStore(
        uri="mongodb://test-host:27017",
        db_name="testdb",
        collection_name="testcol",
    )


def _make_motor_client_mock(ping_side_effect=None):
    """
    Build a mock that mimics the AsyncIOMotorClient API.

    Returns (mock_client_class, mock_client_instance, mock_collection).
    """
    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    mock_client = MagicMock()
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    mock_client.admin = MagicMock()
    mock_client.admin.command = AsyncMock(
        side_effect=ping_side_effect if ping_side_effect else None,
        return_value={"ok": 1},
    )

    mock_client_class = MagicMock(return_value=mock_client)
    return mock_client_class, mock_client, mock_collection


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConnect:
    """Tests for AtlasStore.connect()."""

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """connect() must succeed when the server responds to ping with {ok: 1}."""
        mock_client_class, mock_client, mock_collection = _make_motor_client_mock()

        with patch("atlas_store.AsyncIOMotorClient", mock_client_class, create=True):
            # Patch the import inside connect()
            with patch(
                "motor.motor_asyncio.AsyncIOMotorClient", mock_client_class
            ):
                store = _make_store()
                await store.connect()

        assert store._collection is not None, (
            "store._collection should not be None after successful connect()"
        )

    @pytest.mark.asyncio
    async def test_connect_failure_raises_runtime_error(self) -> None:
        """connect() must raise RuntimeError containing 'Failed to connect' on failure."""
        mock_client_class, _, _ = _make_motor_client_mock(
            ping_side_effect=Exception("timeout")
        )

        with patch(
            "motor.motor_asyncio.AsyncIOMotorClient", mock_client_class
        ):
            store = _make_store()
            with pytest.raises(RuntimeError, match="Failed to connect"):
                await store.connect()


class TestIngestBatch:
    """Tests for AtlasStore.ingest_batch()."""

    @pytest.mark.asyncio
    async def test_ingest_batch(self) -> None:
        """ingest_batch() must call collection.bulk_write exactly once."""
        mock_client_class, mock_client, mock_collection = _make_motor_client_mock()
        mock_collection.bulk_write = AsyncMock(return_value=MagicMock())

        with patch("motor.motor_asyncio.AsyncIOMotorClient", mock_client_class):
            store = _make_store()
            await store.connect()

        # Inject the mocked collection directly
        store._collection = mock_collection

        docs = [
            {
                "chunk_id": f"c{i:04d}",
                "source_file": "kern.log",
                "timestamp": "2026-06-04T10:00:00Z",
                "log_level": "ERROR",
                "content": f"OOM event {i}",
                "embedding": [0.1] * 384,
            }
            for i in range(3)
        ]

        await store.ingest_batch(docs)

        mock_collection.bulk_write.assert_called_once()
        call_args = mock_collection.bulk_write.call_args
        operations = call_args[0][0]  # first positional arg = list of UpdateOne
        assert len(operations) == 3, (
            f"Expected 3 bulk_write operations, got {len(operations)}"
        )


class TestVectorSearch:
    """Tests for AtlasStore.vector_search()."""

    @pytest.mark.asyncio
    async def test_vector_search_returns_correct_schema(self) -> None:
        """vector_search() must return results with all required keys and source_store='atlas'."""
        mock_client_class, mock_client, mock_collection = _make_motor_client_mock()

        # Build fake docs returned by the aggregate cursor
        fake_docs = [
            {
                "chunk_id": f"chunk_{i:04d}",
                "source_file": "kern.log",
                "timestamp": "2026-06-04T10:00:00Z",
                "log_level": "ERROR",
                "content": f"OOM event {i} process chrome",
                "score": 0.95 - i * 0.05,
            }
            for i in range(2)
        ]

        # Mock cursor with async to_list
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=fake_docs)
        mock_collection.aggregate = MagicMock(return_value=mock_cursor)

        with patch("motor.motor_asyncio.AsyncIOMotorClient", mock_client_class):
            store = _make_store()
            await store.connect()

        store._collection = mock_collection

        results = await store.vector_search([0.1] * 384, k=2)

        assert len(results) == 2, f"Expected 2 results, got {len(results)}"

        required_keys = {
            "chunk_id",
            "source_file",
            "timestamp",
            "log_level",
            "content",
            "score",
            "source_store",
        }
        for result in results:
            assert "source_store" in result, "Missing 'source_store' key in result."
            assert result["source_store"] == "atlas", (
                f"Expected source_store='atlas', got {result['source_store']!r}"
            )
            missing_keys = required_keys - result.keys()
            assert not missing_keys, (
                f"Result is missing required keys: {missing_keys}"
            )
