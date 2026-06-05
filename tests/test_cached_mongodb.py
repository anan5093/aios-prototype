"""
tests/test_cached_mongodb.py — Unit tests for CachedMongoDB wrapper in daemon/atlas_store.py.
"""

import os
import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from atlas_store import CachedMongoDB, AtlasStore

pytestmark = pytest.mark.asyncio


def _make_cached_store() -> CachedMongoDB:
    return CachedMongoDB(
        uri="mongodb://test-host:27017",
        db_name="testdb",
        collection_name="testcol",
    )


class TestCachedMongoDB:
    @pytest.mark.asyncio
    async def test_non_blocking_connect(self) -> None:
        """connect() must return immediately and create a background task."""
        store = _make_cached_store()
        
        # Mock the underlying _do_connect method
        do_connect_mock = AsyncMock()
        store._do_connect = do_connect_mock
        
        await store.connect()
        
        assert store._connect_task is not None
        await store._connect_task
        do_connect_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_lazy_connection_on_operation(self) -> None:
        """Operations must ensure connection is initialized lazily if not already connected."""
        store = _make_cached_store()
        
        # Mock self._store
        mock_store = MagicMock()
        mock_store.connect = AsyncMock()
        mock_store.get_doc_count = AsyncMock(return_value=42)
        store._store = mock_store
        
        # Initially not connected
        assert not store._connected
        assert store._connect_task is None
        
        # Try retrieving doc count - should connect and succeed
        count = await store.get_doc_count()
        
        assert count == 42
        assert store._connected
        mock_store.connect.assert_called_once()
        mock_store.get_doc_count.assert_called_once()

    @pytest.mark.asyncio
    async def test_lazy_connection_failure(self) -> None:
        """If lazy connection fails, the operation must raise RuntimeError and reset task."""
        store = _make_cached_store()
        
        mock_store = MagicMock()
        mock_store.connect = AsyncMock(side_effect=Exception("connection timed out"))
        store._store = mock_store
        
        with pytest.raises(RuntimeError, match="Failed lazy connection to MongoDB"):
            await store.get_doc_count()
            
        assert not store._connected
        assert store._connect_task is None
