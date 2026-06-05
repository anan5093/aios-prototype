"""
daemon/faiss_store.py — Local FAISS vector store using IndexFlatIP (cosine similarity).

All vectors are L2-normalised before insertion and at query time.
Metadata stored in parallel Python list, pickled alongside the FAISS index.
Deduplication by chunk_id (sha256[:16] of content).
"""

import faiss  # type: ignore
import numpy as np
import pickle
import hashlib
import logging
from pathlib import Path
from typing import Optional


class FAISSStore:
    """
    Persistent FAISS-based vector store with cosine-similarity search.

    Uses ``IndexFlatIP`` (inner-product) on L2-normalised vectors so that
    the inner product equals the cosine similarity.  Metadata is stored in
    a parallel Python list and persisted via pickle.
    """

    def __init__(
        self,
        index_path: str,
        metadata_path: str,
        dimensions: int = 384,
    ) -> None:
        """
        Initialise paths and dimension; does NOT load from disk.

        Call :meth:`load_or_create` before any other method.

        Args:
            index_path:    File path for the FAISS index binary.
            metadata_path: File path for the pickled metadata list.
            dimensions:    Embedding dimensionality (must match the model).
        """
        self.index_path: str = index_path
        self.metadata_path: str = metadata_path
        self.dimensions: int = dimensions
        self.index: Optional[faiss.IndexFlatIP] = None
        self._metadata: list[dict] = []
        self._chunk_ids: set[str] = set()
        self._logger: logging.Logger = logging.getLogger(
            f"{__name__}.FAISSStore"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load_or_create(self) -> None:
        """
        Load the FAISS index and metadata from disk if they exist, or create
        a fresh empty index.
        """
        idx_path = Path(self.index_path)
        meta_path = Path(self.metadata_path)

        if idx_path.exists() and meta_path.exists():
            self.index = faiss.read_index(str(idx_path))
            with meta_path.open("rb") as fh:
                self._metadata = pickle.load(fh)
            # Rebuild the deduplication set
            self._chunk_ids = {
                m["chunk_id"] for m in self._metadata if "chunk_id" in m
            }
            self._logger.info(
                f"Loaded FAISS index with {self.index.ntotal} vectors from disk "
                f"({idx_path})"
            )
        else:
            self.index = faiss.IndexFlatIP(self.dimensions)
            self._metadata = []
            self._chunk_ids = set()
            self._logger.info("Created new empty FAISS IndexFlatIP")

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(
        self,
        chunks: list[str],
        embeddings: np.ndarray,
        metadata_list: list[dict],
    ) -> None:
        """
        Add chunks to the index, skipping any already present.

        Each chunk is de-duplicated by the first 16 hex characters of the
        SHA-256 digest of its UTF-8 encoding.

        Args:
            chunks:        Raw text strings (parallel with embeddings).
            embeddings:    Float32 ndarray of shape (n, dimensions).
            metadata_list: Per-chunk metadata dicts (parallel with chunks).
        """
        if self.index is None:
            raise RuntimeError("Call load_or_create() before ingest()")

        new_count = 0
        for chunk, embedding, meta in zip(chunks, embeddings, metadata_list):
            chunk_id: str = hashlib.sha256(chunk.encode()).hexdigest()[:16]
            if chunk_id in self._chunk_ids:
                continue  # deduplicate

            # L2-normalise; handle zero-norm gracefully
            norm = float(np.linalg.norm(embedding))
            if norm == 0.0:
                self._logger.warning(
                    f"Zero-norm embedding for chunk_id={chunk_id}; skipping"
                )
                continue
            v: np.ndarray = (embedding / norm).astype(np.float32)

            self.index.add(v.reshape(1, -1))

            enriched_meta = {**meta, "chunk_id": chunk_id, "content": chunk}
            self._metadata.append(enriched_meta)
            self._chunk_ids.add(chunk_id)
            new_count += 1

        if new_count > 0:
            self.persist()

        self._logger.info(
            f"Ingested {new_count} new chunks. "
            f"Total vectors: {self.index.ntotal}"
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
    ) -> list[dict]:
        """
        Find the *k* most similar chunks to *query_embedding*.

        Args:
            query_embedding: Float32 ndarray of shape (dimensions,) or (1, dimensions).
            k:               Number of results requested.

        Returns:
            List of metadata dicts, each augmented with ``score`` (float in
            [0, 1]) and ``source_store='faiss'``.  Empty list if the index is
            empty or not yet initialised.
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # L2-normalise query
        q = query_embedding.flatten().astype(np.float32)
        norm = float(np.linalg.norm(q))
        if norm > 0.0:
            q = q / norm

        k_actual = min(k, self.index.ntotal)
        scores, indices = self.index.search(q.reshape(1, -1), k_actual)

        results: list[dict] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue  # FAISS returns -1 for padded results
            meta = dict(self._metadata[idx])
            # Clamp to [0, 1]; inner-product on unit vectors is in [-1, 1]
            meta["score"] = float(max(0.0, min(1.0, score)))
            meta["source_store"] = "faiss"
            results.append(meta)

        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist(self) -> None:
        """
        Write the FAISS index and metadata to disk.  Parent directories
        are created automatically.
        """
        if self.index is None:
            raise RuntimeError("Nothing to persist — index not initialised")

        idx_path = Path(self.index_path)
        meta_path = Path(self.metadata_path)

        idx_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(idx_path))
        with meta_path.open("wb") as fh:
            pickle.dump(self._metadata, fh)

        self._logger.info(
            f"Persisted {self.index.ntotal} vectors to {self.index_path}"
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_vector_count(self) -> int:
        """Return the total number of vectors stored in the index."""
        return self.index.ntotal if self.index is not None else 0
