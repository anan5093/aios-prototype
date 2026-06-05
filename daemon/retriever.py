"""
daemon/retriever.py — Hybrid retriever combining FAISS (local) and Atlas (cloud).

FAISS search runs in ThreadPoolExecutor (sync C call).
Atlas search runs natively async.
Both are launched in parallel via asyncio.gather().
Results are merged, deduplicated, and re-ranked by weighted final_score.
"""

import asyncio
import logging
from concurrent.futures import Executor
from typing import Any


class HybridRetriever:
    """
    Parallel hybrid retriever that merges FAISS and Atlas results.

    FAISS is a synchronous C library; its search is off-loaded to a
    :class:`concurrent.futures.ThreadPoolExecutor` so the event loop is
    never blocked.  Atlas is queried with its native async driver.

    Scores are combined:
    * Both stores → ``0.6 × faiss_score + 0.4 × atlas_score``
    * FAISS only  → ``0.6 × faiss_score``
    * Atlas only  → ``0.4 × atlas_score``
    """

    def __init__(
        self,
        faiss_store: Any,
        atlas_store: Any,
        embedder: Any,
        executor: Executor,
    ) -> None:
        """
        Args:
            faiss_store: :class:`~daemon.faiss_store.FAISSStore` instance.
            atlas_store: :class:`~daemon.atlas_store.AtlasStore` instance.
            embedder:    :class:`~daemon.embedder.EmbeddingService` instance.
            executor:    ThreadPoolExecutor for off-loading sync FAISS calls.
        """
        self._faiss = faiss_store
        self._atlas = atlas_store
        self._embedder = embedder
        self._executor = executor
        self._logger = logging.getLogger(f"{__name__}.HybridRetriever")

    async def retrieve(
        self,
        query: str,
        k_each: int = 5,
    ) -> list[dict]:
        """
        Embed *query*, search both stores in parallel, and return up to 8
        deduplicated, re-ranked results.

        Args:
            query:  Natural-language query string.
            k_each: Number of results to request from each store.

        Returns:
            Up to 8 result dicts sorted by ``final_score`` (descending).
            Each dict is guaranteed to contain:
            ``chunk_id``, ``source_file``, ``timestamp``, ``log_level``,
            ``content``, ``score`` (= final_score), ``source_store``.
        """
        loop = asyncio.get_event_loop()

        # Step 1: Embed query off the event loop (FAISS/ST are sync/CPU-bound)
        query_embedding = await loop.run_in_executor(
            self._executor,
            self._embedder.embed_single,
            query,
        )

        # Step 2: Define the sync FAISS wrapper
        def _faiss_search() -> list[dict]:
            return self._faiss.search(query_embedding, k_each)

        # Step 3: Run both searches concurrently
        faiss_task = loop.run_in_executor(self._executor, _faiss_search)
        atlas_task = self._atlas.vector_search(
            query_embedding.tolist(), k_each
        )

        faiss_results: list[dict] = []
        atlas_results: list[dict] = []

        try:
            faiss_results, atlas_results = await asyncio.gather(
                faiss_task, atlas_task
            )
        except Exception as exc:
            self._logger.warning(
                f"One or both stores failed during retrieve: {exc!r}. "
                "Attempting partial results."
            )
            # Try to collect whatever completed
            if not faiss_results:
                try:
                    faiss_results = await asyncio.shield(faiss_task)
                except Exception:
                    faiss_results = []
            if not atlas_results:
                try:
                    atlas_results = await asyncio.shield(atlas_task)
                except Exception:
                    atlas_results = []

        # Step 4: Build score maps keyed by chunk_id
        faiss_map: dict[str, dict] = {
            r["chunk_id"]: r for r in faiss_results if "chunk_id" in r
        }
        atlas_map: dict[str, dict] = {
            r["chunk_id"]: r for r in atlas_results if "chunk_id" in r
        }

        # Step 5: Deduplicate and compute weighted final_score
        all_ids: set[str] = faiss_map.keys() | atlas_map.keys()
        merged: list[dict] = []

        for chunk_id in all_ids:
            in_faiss = chunk_id in faiss_map
            in_atlas = chunk_id in atlas_map

            if in_faiss and in_atlas:
                base = dict(faiss_map[chunk_id])
                faiss_score = float(faiss_map[chunk_id].get("score", 0.0))
                atlas_score = float(atlas_map[chunk_id].get("score", 0.0))
                final_score = 0.6 * faiss_score + 0.4 * atlas_score
                base["source_store"] = "both"
            elif in_faiss:
                base = dict(faiss_map[chunk_id])
                final_score = 0.6 * float(base.get("score", 0.0))
                base["source_store"] = "faiss"
            else:  # atlas only
                base = dict(atlas_map[chunk_id])
                final_score = 0.4 * float(base.get("score", 0.0))
                base["source_store"] = "atlas"

            base["score"] = final_score
            merged.append(base)

        # Step 6: Sort by final_score descending
        merged.sort(key=lambda x: x["score"], reverse=True)

        # Step 7: Return top 8
        top = merged[:8]
        self._logger.debug(
            f"HybridRetriever: query='{query[:60]}…', "
            f"faiss={len(faiss_results)}, atlas={len(atlas_results)}, "
            f"merged={len(merged)}, returned={len(top)}"
        )
        return top
