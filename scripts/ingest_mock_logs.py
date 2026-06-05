"""
ingest_mock_logs.py — Ingest mock log files into FAISS (local) and MongoDB Atlas (cloud).

Usage: python scripts/ingest_mock_logs.py
Requires: .env with ATLAS_URI, ATLAS_DB, ATLAS_COLLECTION, EMBEDDING_MODEL
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — must happen BEFORE any daemon imports
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Load .env from project root
# ---------------------------------------------------------------------------
from dotenv import load_dotenv  # type: ignore  # noqa: E402

_env_path = _PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=_env_path)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("ingest_mock_logs")

# ---------------------------------------------------------------------------
# Daemon imports (after sys.path update)
# ---------------------------------------------------------------------------
from daemon.embedder import EmbeddingService, chunk_text  # noqa: E402
from daemon.faiss_store import FAISSStore  # noqa: E402
from daemon.atlas_store import AtlasStore  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BATCH_SIZE = 32
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50

LOG_FILES = [
    "mock_logs/syslog",
    "mock_logs/kern.log",
    "mock_logs/bash_history",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_log_level(first_line: str) -> str:
    """
    Infer log level from the first line of a log chunk.

    Priority:
      - Contains 'ERROR'   → 'ERROR'
      - Contains 'WARN' or 'WARNING' → 'WARN'
      - Otherwise          → 'INFO'

    Args:
        first_line: The first line of the chunk text.

    Returns:
        One of 'ERROR', 'WARN', or 'INFO'.
    """
    upper = first_line.upper()
    if "ERROR" in upper:
        return "ERROR"
    if "WARN" in upper or "WARNING" in upper:
        return "WARN"
    return "INFO"


def _read_and_chunk_file(
    file_path: Path,
) -> tuple[list[str], list[dict]]:
    """
    Read a log file, chunk its content, and build metadata for each chunk.

    Args:
        file_path: Absolute path to the log file.

    Returns:
        Tuple of (chunks, metadata_list) where each entry in metadata_list
        is a dict with keys: source_file, timestamp, log_level, content.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError:           On other I/O errors.
    """
    logger.info(f"Reading log file: {file_path}")

    with file_path.open("r", encoding="utf-8", errors="replace") as fh:
        all_lines = fh.readlines()

    if not all_lines:
        logger.warning(f"Empty file: {file_path}")
        return [], []

    full_text = "".join(all_lines)
    chunks = chunk_text(full_text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    if not chunks:
        logger.warning(f"No chunks produced from {file_path}")
        return [], []

    # Determine log level from first line of the file
    first_line = all_lines[0].strip() if all_lines else ""
    log_level = _parse_log_level(first_line)
    now = datetime.now(timezone.utc)

    metadata_list: list[dict] = [
        {
            "source_file": str(file_path.name),
            "timestamp": now,
            "log_level": log_level,
            "content": chunk,
        }
        for chunk in chunks
    ]

    logger.info(
        f"  → {len(chunks)} chunks from {file_path.name} (log_level={log_level})"
    )
    return chunks, metadata_list


# ---------------------------------------------------------------------------
# Atlas async ingestion
# ---------------------------------------------------------------------------

async def _atlas_connect_and_ingest(
    atlas_store: AtlasStore,
    all_chunks: list[str],
    all_embeddings: "list",
    all_metadata: list[dict],
) -> int:
    """
    Connect to Atlas and ingest all chunks asynchronously.

    Builds the document list expected by ``AtlasStore.ingest_batch`` and
    calls it after establishing a connection.

    Args:
        atlas_store:    Configured AtlasStore instance (not yet connected).
        all_chunks:     All chunk strings.
        all_embeddings: Corresponding embedding arrays.
        all_metadata:   Corresponding metadata dicts.

    Returns:
        Total number of documents passed to ingest_batch (Atlas may deduplicate).
    """
    import hashlib
    from datetime import datetime, timezone

    await atlas_store.connect()
    logger.info("Atlas connection established")

    now = datetime.now(timezone.utc)
    documents: list[dict] = []
    for chunk, embedding, meta in zip(all_chunks, all_embeddings, all_metadata):
        chunk_id = hashlib.sha256(chunk.encode()).hexdigest()[:16]
        # Convert numpy arrays to plain list for BSON
        if hasattr(embedding, "tolist"):
            emb_list = embedding.tolist()
        else:
            emb_list = list(embedding)

        log_level = meta.get("log_level", "INFO")
        severity_map = {"ERROR": 3, "WARN": 2, "WARNING": 2, "INFO": 1}
        severity = severity_map.get(log_level.upper(), 1)

        documents.append(
            {
                "chunk_id": chunk_id,
                "source_file": meta.get("source_file", "unknown"),
                "timestamp": meta.get("timestamp", now),
                "log_level": log_level,
                "severity": severity,
                "host_id": "AIOS_HOST",
                "content": chunk,
                "embedding": emb_list,
                "ingested_at": now,
                "session_id": "session_ingest_001",
            }
        )

    await atlas_store.ingest_batch(documents)
    return len(documents)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Entry point: load log files, embed chunks, ingest into FAISS and Atlas.

    Steps:
      1. Read and chunk all three log files.
      2. Embed all chunks in batches of BATCH_SIZE.
      3. Ingest into FAISS (synchronous).
      4. If ATLAS_URI is set, ingest into Atlas (async).
      5. Print summary.
    """
    t_start = time.monotonic()

    # --- Resolve paths ------------------------------------------------------
    mock_logs_base = _PROJECT_ROOT / "mock_logs"
    data_dir = _PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # --- Read and chunk all log files ---------------------------------------
    all_chunks: list[str] = []
    all_metadata: list[dict] = []

    for rel_path in LOG_FILES:
        file_path = _PROJECT_ROOT / rel_path
        if not file_path.exists():
            logger.warning(f"Log file not found, skipping: {file_path}")
            continue
        try:
            chunks, metadata_list = _read_and_chunk_file(file_path)
            all_chunks.extend(chunks)
            all_metadata.extend(metadata_list)
        except OSError as exc:
            logger.error(f"Failed to read {file_path}: {exc}")

    if not all_chunks:
        logger.error("No chunks to ingest — did you run generate_mock_logs.py?")
        sys.exit(1)

    logger.info(f"Total chunks to embed: {len(all_chunks)}")

    # --- Embed in batches ---------------------------------------------------
    logger.info("Loading embedding model …")
    embedder = EmbeddingService()

    import numpy as np
    all_embeddings_list: list[np.ndarray] = []

    for batch_start in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[batch_start: batch_start + BATCH_SIZE]
        batch_vecs = embedder.embed(batch)
        all_embeddings_list.extend(batch_vecs)
        logger.info(
            f"  Embedded batch {batch_start // BATCH_SIZE + 1} "
            f"({batch_start + len(batch)}/{len(all_chunks)} chunks)"
        )

    all_embeddings = np.stack(all_embeddings_list, axis=0)
    logger.info(f"Embedding complete. Shape: {all_embeddings.shape}")

    # --- FAISS ingestion (synchronous) --------------------------------------
    faiss_store = FAISSStore(
        index_path=str(data_dir / "faiss_index.bin"),
        metadata_path=str(data_dir / "faiss_metadata.pkl"),
    )
    faiss_store.load_or_create()
    logger.info("Ingesting into FAISS …")
    faiss_store.ingest(all_chunks, all_embeddings, all_metadata)
    faiss_vector_count = faiss_store.get_vector_count()
    logger.info(f"FAISS now contains {faiss_vector_count} vectors")

    # --- Atlas ingestion (async, optional) ----------------------------------
    atlas_uri: str = os.environ.get("ATLAS_URI", "").strip()
    atlas_db: str = os.environ.get("ATLAS_DB", "aios_memory").strip()
    atlas_collection: str = os.environ.get(
        "ATLAS_COLLECTION", "system_logs"
    ).strip()

    atlas_doc_count = 0

    if not atlas_uri:
        logger.warning(
            "ATLAS_URI not set in environment — skipping Atlas ingestion. "
            "FAISS ingestion completed successfully."
        )
    else:
        logger.info("Connecting to MongoDB Atlas …")
        atlas_store = AtlasStore(
            uri=atlas_uri,
            db_name=atlas_db,
            collection_name=atlas_collection,
        )

        async def _run_atlas() -> int:
            docs_sent = await _atlas_connect_and_ingest(
                atlas_store, all_chunks, all_embeddings_list, all_metadata
            )
            count = await atlas_store.get_doc_count()
            return count

        try:
            atlas_doc_count = asyncio.run(_run_atlas())
            logger.info(f"Atlas collection now contains {atlas_doc_count} documents")
        except Exception as exc:
            logger.error(f"Atlas ingestion failed: {exc}")
            print(
                f"\n[WARNING] Atlas ingestion encountered an error: {exc}",
                file=sys.stderr,
            )

    # --- Summary ------------------------------------------------------------
    elapsed = time.monotonic() - t_start
    print("\n=== Ingest Summary ===")
    print(f"Total chunks processed : {len(all_chunks)}")
    print(f"FAISS vector count     : {faiss_vector_count}")
    print(f"Atlas document count   : {atlas_doc_count}")
    print(f"Time taken             : {elapsed:.2f}s")


if __name__ == "__main__":
    main()
