"""
daemon/atlas_store.py — Async MongoDB Atlas vector store using motor.

Collection: aios_memory.system_logs
Vector index: vector_index (384 dimensions, cosine)
All methods are async.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Any


class AtlasStore:
    """
    Async MongoDB Atlas client that supports bulk ingestion and
    Atlas Vector Search via the ``$vectorSearch`` aggregation stage.
    """

    def __init__(
        self,
        uri: str,
        db_name: str,
        collection_name: str,
    ) -> None:
        """
        Initialise Atlas store configuration without opening a connection.

        Call :meth:`connect` before any other method.

        Args:
            uri:             MongoDB connection string (Atlas or local).
            db_name:         Database name (e.g. ``aios_memory``).
            collection_name: Collection name (e.g. ``system_logs``).
        """
        self.uri: str = uri
        self.db_name: str = db_name
        self.collection_name: str = collection_name
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._logger: logging.Logger = logging.getLogger(
            f"{__name__}.AtlasStore"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Open an async connection to MongoDB Atlas and verify it with a ping.

        Raises:
            RuntimeError: If the server cannot be reached within the timeout.
        """
        try:
            from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

            self._client = AsyncIOMotorClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
            )
            # Verify connection
            await self._client.admin.command("ping")
            self._collection = self._client[self.db_name][self.collection_name]
            self._logger.info("Connected to MongoDB Atlas successfully")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Atlas: {e}") from e

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest_batch(self, documents: list[dict]) -> None:
        """
        Upsert a batch of documents into the collection.

        Each document must contain the following keys:
        ``chunk_id``, ``source_file``, ``timestamp``, ``log_level``,
        ``content``, ``embedding``.

        Duplicate documents (same ``chunk_id``) are silently ignored via
        ``$setOnInsert`` + upsert semantics.

        Args:
            documents: List of document dicts to upsert.

        Raises:
            ValueError:  If any document is missing required fields.
        """
        if self._collection is None:
            raise RuntimeError("Not connected — call connect() first")

        required_fields = {
            "chunk_id",
            "source_file",
            "timestamp",
            "log_level",
            "content",
            "embedding",
        }

        from pymongo import UpdateOne  # type: ignore
        from pymongo.errors import BulkWriteError  # type: ignore

        operations: list[UpdateOne] = []
        for doc in documents:
            missing = required_fields - doc.keys()
            if missing:
                raise ValueError(f"Missing required keys: {missing}")
            operations.append(
                UpdateOne(
                    filter={"chunk_id": doc["chunk_id"]},
                    update={"$setOnInsert": doc},
                    upsert=True,
                )
            )

        if not operations:
            return

        try:
            await self._collection.bulk_write(operations, ordered=False)
            self._logger.info(
                f"Ingested batch of {len(documents)} documents"
            )
        except BulkWriteError as bwe:
            # Log details but don't re-raise; duplicates are acceptable
            self._logger.warning(
                f"BulkWriteError during ingest (likely duplicates): "
                f"{bwe.details.get('writeErrors', [])}"
            )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def vector_search(
        self,
        query_embedding: list[float],
        k: int = 5,
    ) -> list[dict]:
        """
        Run an Atlas ``$vectorSearch`` aggregation against the collection.

        Args:
            query_embedding: L2-normalised query vector as a plain Python list.
            k:               Maximum number of results to return.

        Returns:
            List of result dicts with keys ``chunk_id``, ``source_file``,
            ``timestamp``, ``log_level``, ``content``, ``score``, and
            ``source_store='atlas'``.

        Raises:
            RuntimeError: If :meth:`connect` has not been called yet.
        """
        if self._collection is None:
            raise RuntimeError("Not connected — call connect() first")

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": k * 10,
                    "limit": k,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "chunk_id": 1,
                    "source_file": 1,
                    "timestamp": 1,
                    "log_level": 1,
                    "content": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        cursor = self._collection.aggregate(pipeline)
        results: list[dict] = await cursor.to_list(length=k)

        for result in results:
            result["source_store"] = "atlas"

        self._logger.debug(
            f"Atlas vector search returned {len(results)} results for k={k}"
        )
        return results

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def get_doc_count(self) -> int:
        """
        Return the total number of documents in the collection.

        Raises:
            RuntimeError: If :meth:`connect` has not been called yet.
        """
        if self._collection is None:
            raise RuntimeError("Not connected — call connect() first")
        return await self._collection.count_documents({})


class CachedMongoDB:
    """
    A cached/lazy wrapper for AtlasStore that prevents database connection pings
    from blocking the main thread / event loop during server startup.
    """

    def __init__(
        self,
        uri: str,
        db_name: str,
        collection_name: str,
    ) -> None:
        """
        Initialise the cached MongoDB instance.

        Args:
            uri:             MongoDB connection string.
            db_name:         Database name.
            collection_name: Collection name.
        """
        import asyncio
        self.uri: str = uri
        self.db_name: str = db_name
        self.collection_name: str = collection_name
        self._store: AtlasStore = AtlasStore(uri, db_name, collection_name)
        self._connect_task: Optional[asyncio.Task] = None
        self._connected: bool = False
        self._connect_lock: asyncio.Lock = asyncio.Lock()
        self._logger: logging.Logger = logging.getLogger(
            f"{__name__}.CachedMongoDB"
        )

    async def connect(self) -> None:
        """
        Start the connection in the background so it doesn't block startup.
        """
        import asyncio
        if self._connect_task is None:
            self._logger.info("Scheduling MongoDB connection in the background…")
            self._connect_task = asyncio.create_task(self._do_connect())

    async def _do_connect(self) -> None:
        async with self._connect_lock:
            if not self._connected:
                try:
                    await self._store.connect()
                    self._connected = True
                    self._logger.info("Background MongoDB connection established successfully")
                except Exception as e:
                    self._logger.warning(
                        f"Background connection to MongoDB failed: {e}. "
                        "Retries will occur lazily upon request."
                    )

    async def _ensure_connected(self) -> None:
        import asyncio
        if not self._connected:
            async with self._connect_lock:
                if not self._connected:
                    if self._connect_task is None:
                        self._logger.info("Lazily initiating MongoDB connection…")
                        self._connect_task = asyncio.create_task(self._do_connect())
            try:
                await self._connect_task
            except Exception as e:
                # Reset task so subsequent operations can retry connecting
                self._connect_task = None
                raise RuntimeError(
                    f"Failed lazy connection to MongoDB: {e}"
                ) from e
            if not self._connected:
                self._connect_task = None
                raise RuntimeError("Failed lazy connection to MongoDB: connection not established")

    async def ingest_batch(self, documents: list[dict]) -> None:
        """
        Ensure connection is open, then delegate to underlying store.
        """
        await self._ensure_connected()
        await self._store.ingest_batch(documents)

    async def vector_search(
        self,
        query_embedding: list[float],
        k: int = 5,
    ) -> list[dict]:
        """
        Ensure connection is open, then delegate search.
        """
        try:
            await self._ensure_connected()
            return await self._store.vector_search(query_embedding, k)
        except Exception as e:
            self._logger.warning(
                f"Vector search failed due to connection error: {e}. Returning empty list."
            )
            return []

    async def get_doc_count(self) -> int:
        """
        Ensure connection is open, then delegate count.
        """
        await self._ensure_connected()
        return await self._store.get_doc_count()

