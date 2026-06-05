"""
daemon/embedder.py — CPU-based embedding service using sentence-transformers.

Lazy model loading: model is NOT imported/loaded at module import time.
Thread-safe for asyncio ThreadPoolExecutor usage.
All output vectors are L2-normalised (inner product == cosine similarity).
"""

import threading
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Wraps a SentenceTransformer model with thread-safe lazy loading."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """
        Initialise the embedding service without loading the model.

        Args:
            model_name: HuggingFace model identifier for sentence-transformers.
        """
        self.model_name: str = model_name
        self._model: Optional[object] = None
        self._lock: threading.Lock = threading.Lock()
        self._logger: logging.Logger = logging.getLogger(
            f"{__name__}.EmbeddingService"
        )

    def _ensure_model_loaded(self) -> None:
        """
        Thread-safe double-checked locking to load the model exactly once.

        Uses the classic double-check pattern so that after the model is loaded
        no thread ever acquires the lock again.
        """
        if self._model is None:
            with self._lock:
                # Second check inside the lock
                if self._model is None:
                    import time

                    t0 = time.time()
                    from sentence_transformers import SentenceTransformer  # type: ignore

                    self._model = SentenceTransformer(self.model_name)
                    self._logger.info(
                        f"Model '{self.model_name}' loaded in {time.time() - t0:.2f}s"
                    )

    def embed(self, texts: list[str]) -> np.ndarray:
        """
        Embed a list of texts and return L2-normalised vectors.

        Args:
            texts: Non-empty list of strings to embed.

        Returns:
            Float32 ndarray of shape (n, 384) with unit-norm rows.
        """
        self._ensure_model_loaded()
        vectors: np.ndarray = self._model.encode(  # type: ignore[union-attr]
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        self._logger.debug(f"Embedded {len(texts)} texts → shape {vectors.shape}")
        return vectors

    def embed_single(self, text: str) -> np.ndarray:
        """
        Embed a single string and return a 1-D normalised vector.

        Args:
            text: The string to embed.

        Returns:
            Float32 ndarray of shape (384,).
        """
        return self.embed([text])[0]


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[str]:
    """
    Split *text* into overlapping chunks suitable for vector indexing.

    Strategy (applied in order):
      1. Split on ``\\n\\n`` (paragraph boundaries).
      2. For any segment longer than *chunk_size* chars, split further on ``\\n``.
      3. For any part still longer than *chunk_size*, split on whitespace and
         build chunks greedily.
      4. Enforce an overlap: every new chunk is prefixed with the last
         *chunk_overlap* characters of the previous chunk.
      5. Strip whitespace; skip empty chunks.

    Args:
        text:          Raw text to be chunked.
        chunk_size:    Maximum character length of a single chunk.
        chunk_overlap: Number of characters from the end of the previous chunk
                       to prepend to the current chunk.

    Returns:
        List of non-empty, whitespace-stripped chunk strings.
    """
    _log = logging.getLogger(f"{__name__}.chunk_text")

    def _split_by_words(segment: str) -> list[str]:
        """Greedily split *segment* into word-boundary chunks."""
        words = segment.split(" ")
        parts: list[str] = []
        current: list[str] = []
        current_len = 0
        for word in words:
            word_len = len(word) + (1 if current else 0)
            if current_len + word_len > chunk_size and current:
                parts.append(" ".join(current))
                current = []
                current_len = 0
            current.append(word)
            current_len += word_len
        if current:
            parts.append(" ".join(current))
        return parts

    # Step 1 — paragraph split
    raw_parts: list[str] = []
    for para in text.split("\n\n"):
        if len(para) <= chunk_size:
            raw_parts.append(para)
        else:
            # Step 2 — line split within oversized paragraph
            for line in para.split("\n"):
                if len(line) <= chunk_size:
                    raw_parts.append(line)
                else:
                    # Step 3 — word-level greedy split
                    raw_parts.extend(_split_by_words(line))

    # Step 4 — enforce overlap and collect
    chunks: list[str] = []
    prev_tail: str = ""
    for part in raw_parts:
        candidate = (prev_tail + part) if prev_tail else part
        stripped = candidate.strip()
        if not stripped:
            continue
        chunks.append(stripped)
        # Keep last chunk_overlap chars as prefix for the next chunk
        prev_tail = stripped[-chunk_overlap:] + " " if chunk_overlap > 0 else ""

    _log.debug(
        f"chunk_text: {len(text)} chars → {len(chunks)} chunks "
        f"(chunk_size={chunk_size}, overlap={chunk_overlap})"
    )
    return chunks
