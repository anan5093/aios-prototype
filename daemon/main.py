"""
daemon/main.py — AIOS Python AI Daemon

Entry point: python daemon/main.py

Orchestrates all subsystems:
1. Environment loading
2. EmbeddingService (lazy, ThreadPoolExecutor)
3. FAISSStore
4. AtlasStore
5. HybridRetriever
6. TelemetrySanitiser
7. InferenceClient
8. IntentParser + DeterministicControlPlane
9. WebSocketBroadcaster
10. Watchdog file monitor (mock_logs/)
11. aiohttp IPC server on localhost:8765
12. Periodic metrics push (every 10s)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path manipulation — allow running from project root as
#   python daemon/main.py
# ---------------------------------------------------------------------------

_DAEMON_DIR = Path(__file__).resolve().parent
if str(_DAEMON_DIR) not in sys.path:
    sys.path.insert(0, str(_DAEMON_DIR))

# ---------------------------------------------------------------------------
# Third-party imports (installed in venv)
# ---------------------------------------------------------------------------

import aiohttp  # type: ignore
import psutil  # type: ignore
from aiohttp import web  # type: ignore
from dotenv import load_dotenv  # type: ignore
from watchdog.events import FileSystemEventHandler  # type: ignore
from watchdog.observers import Observer  # type: ignore

# ---------------------------------------------------------------------------
# Local daemon modules
# ---------------------------------------------------------------------------

from embedder import EmbeddingService, chunk_text
from faiss_store import FAISSStore
from atlas_store import AtlasStore, CachedMongoDB
from retriever import HybridRetriever
from sanitiser import TelemetrySanitiser
from inference_client import InferenceClient
from intent_parser import IntentParser
from control_plane import DeterministicControlPlane
from ws_broadcaster import WebSocketBroadcaster
from prompt_builder import build_prompt

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _setup_logging() -> None:
    """Configure root logging from LOG_LEVEL env var (default: INFO)."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format=_LOG_FORMAT)
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Daemon start time
# ---------------------------------------------------------------------------

_DAEMON_START: float = time.time()

# ---------------------------------------------------------------------------
# Module-level service singletons (initialised in main())
# ---------------------------------------------------------------------------

embedder: Optional[EmbeddingService] = None
faiss_store: Optional[FAISSStore] = None
atlas_store: Optional[CachedMongoDB] = None
retriever: Optional[HybridRetriever] = None
sanitiser: Optional[TelemetrySanitiser] = None
inference_client: Optional[InferenceClient] = None
intent_parser: Optional[IntentParser] = None
control_plane: Optional[DeterministicControlPlane] = None
broadcaster: Optional[WebSocketBroadcaster] = None
executor: Optional[ThreadPoolExecutor] = None
main_loop: Optional[asyncio.AbstractEventLoop] = None

# Track last-read positions per monitored file
_file_positions: dict[str, int] = {}

# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------


class LogFileChangeHandler(FileSystemEventHandler):
    """
    watchdog event handler that schedules an async task whenever a monitored
    log file grows.
    """

    def on_modified(self, event: object) -> None:  # type: ignore[override]
        """
        Called by watchdog on any file-system modification event.

        If the event target is a file (not a directory), schedule
        :func:`_process_log_delta` on the running event loop.
        """
        if getattr(event, "is_directory", False):
            return
        src_path: str = getattr(event, "src_path", "")
        if not src_path:
            return
        if main_loop is not None:
            main_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(_process_log_delta(src_path))
            )



async def _process_log_delta(path: str) -> None:
    """
    Read only newly-appended lines from *path*, chunk them, embed them,
    and ingest into both FAISS and Atlas.

    Args:
        path: Absolute path to the log file that was modified.
    """
    global _file_positions, faiss_store, atlas_store, embedder, sanitiser

    try:
        file_path = Path(path)
        if not file_path.exists():
            return

        last_pos: int = _file_positions.get(path, 0)

        with file_path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(last_pos)
            new_content = fh.read()
            new_pos = fh.tell()

        _file_positions[path] = new_pos

        if not new_content.strip():
            return

        logger.debug(
            f"_process_log_delta: {len(new_content)} new bytes from {path}"
        )

        # Chunk the new content
        chunks = chunk_text(new_content, chunk_size=512, chunk_overlap=50)
        if not chunks:
            return

        # Embed (off the event loop via executor)
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            executor, embedder.embed, chunks  # type: ignore[arg-type]
        )

        import numpy as np
        from datetime import datetime, timezone

        timestamp = datetime.now(tz=timezone.utc).isoformat()
        log_filename = file_path.name

        meta_list: list[dict] = [
            {
                "source_file": log_filename,
                "timestamp": timestamp,
                "log_level": _infer_log_level(chunk),
            }
            for chunk in chunks
        ]

        # Ingest into FAISS (sync, run in executor)
        if faiss_store is not None:
            await loop.run_in_executor(
                executor,
                faiss_store.ingest,
                chunks,
                embeddings,
                meta_list,
            )

        # Ingest into Atlas (async)
        if atlas_store is not None:
            import hashlib

            documents = [
                {
                    "chunk_id": hashlib.sha256(chunk.encode()).hexdigest()[:16],
                    "source_file": log_filename,
                    "timestamp": timestamp,
                    "log_level": _infer_log_level(chunk),
                    "content": chunk,
                    "embedding": embeddings[i].tolist(),
                }
                for i, chunk in enumerate(chunks)
            ]
            try:
                await atlas_store.ingest_batch(documents)
            except Exception as exc:
                logger.warning(f"Atlas ingest_batch failed: {exc!r}")

        logger.info(
            f"_process_log_delta: ingested {len(chunks)} chunks from {log_filename}"
        )

    except Exception as exc:
        logger.exception(f"_process_log_delta error for {path}: {exc!r}")


def _infer_log_level(text: str) -> str:
    """
    Heuristically detect the log level from the text content.

    Args:
        text: Log line or chunk text.

    Returns:
        One of ``ERROR``, ``WARNING``, ``INFO``, ``DEBUG``, or ``UNKNOWN``.
    """
    upper = text.upper()
    if "CRITICAL" in upper or "EMERG" in upper or "ALERT" in upper:
        return "ERROR"
    if "ERROR" in upper or "ERR" in upper:
        return "ERROR"
    if "WARN" in upper or "WARNING" in upper:
        return "WARNING"
    if "INFO" in upper:
        return "INFO"
    if "DEBUG" in upper:
        return "DEBUG"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Core query pipeline
# ---------------------------------------------------------------------------


async def handle_query(query: str, query_id: str) -> None:
    """
    14-step end-to-end query pipeline.

    1.  Log query start
    2.  Record start time
    3.  Retrieve RAG chunks from the hybrid store
    4.  Emit RAG chunks to WebSocket clients
    5.  Build the full prompt
    6.  Sanitise the prompt
    7.  Stream tokens from the inference backend
    8.  Record latency
    9.  Emit stream_done
    10. Parse the LLM completion for an AIIntent
    11. If parsed, emit intent_parsed
    12. Validate & log the intent through the control plane
    13. Emit the validation result
    14. Log pipeline summary with latency

    Args:
        query:    User query string.
        query_id: Unique identifier for this query session.
    """
    assert retriever is not None
    assert sanitiser is not None
    assert inference_client is not None
    assert intent_parser is not None
    assert control_plane is not None
    assert broadcaster is not None

    logger.info(f"handle_query start: query_id={query_id} query='{query[:80]}'")
    start_time = time.time()

    # Step 3: RAG retrieval
    try:
        chunks = await retriever.retrieve(query, k_each=5)
    except Exception as exc:
        logger.exception(f"Retrieval failed for query_id={query_id}: {exc!r}")
        chunks = []

    # Step 4: Emit RAG chunks (strip embedding field for WS payload)
    safe_chunks = [
        {k: v for k, v in c.items() if k != "embedding"} for c in chunks
    ]
    await broadcaster.emit_rag_retrieved(safe_chunks, query_id)

    # Step 5: Build prompt
    prompt = build_prompt(query, chunks)

    # Step 6: Sanitise
    sanitised = sanitiser.sanitise(prompt)

    # Step 7: Stream generation
    full_completion = ""
    try:
        async for token in inference_client.stream_generate(sanitised):
            full_completion += token
            await broadcaster.emit_token(token, query_id)
    except Exception as exc:
        logger.warning(
            f"stream_generate error for query_id={query_id}: {exc!r}"
        )
        # Emit circuit-breaker state change
        status = inference_client.get_status()
        await broadcaster.emit_circuit_breaker(
            status["circuit_state"],
            fallback=status["backend"] == "local",
        )

    # Step 8: Latency
    latency_ms = int((time.time() - start_time) * 1000)

    # Step 9: Stream done
    await broadcaster.emit_stream_done(query_id, latency_ms)

    # Step 10: Parse intent
    intent = intent_parser.parse(full_completion)

    # Step 11: Emit intent if parsed
    if intent is not None:
        await broadcaster.emit_intent_parsed(intent.model_dump(), query_id)

    # Step 12: Validate and log
    result = control_plane.validate_and_log(intent)

    # Step 13: Emit validation result
    await broadcaster.emit_validation_result(result.status, result.intent_id)

    # Step 14: Summary log
    logger.info(
        f"handle_query done: query_id={query_id} "
        f"latency_ms={latency_ms} "
        f"chunks={len(chunks)} "
        f"intent_status={result.status} "
        f"intent_id={result.intent_id}"
    )


# ---------------------------------------------------------------------------
# aiohttp IPC HTTP handlers
# ---------------------------------------------------------------------------


async def _post_query(request: web.Request) -> web.Response:
    """
    POST /query

    Body: {"query": "...", "query_id": "..."}
    Returns 202 immediately and runs the pipeline as a background task.
    """
    try:
        body = await request.json()
        query: str = body.get("query", "").strip()
        query_id: str = body.get("query_id", f"q_{int(time.time()*1000)}")

        if not query:
            return web.json_response(
                {"error": "query must be a non-empty string"}, status=400
            )

        asyncio.create_task(handle_query(query, query_id))

        return web.json_response(
            {"query_id": query_id, "status": "streaming"},
            status=202,
        )
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON body"}, status=400)


async def _get_metrics(request: web.Request) -> web.Response:
    """
    GET /metrics

    Returns current system metrics plus daemon-specific counters.
    """
    assert faiss_store is not None

    uptime_seconds = int(time.time() - _DAEMON_START)

    atlas_doc_count = 0
    if atlas_store is not None:
        try:
            atlas_doc_count = await atlas_store.get_doc_count()
        except Exception:
            atlas_doc_count = -1

    metrics = {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "memory_available_mb": psutil.virtual_memory().available // (1024 * 1024),
        "disk_percent": psutil.disk_usage("/").percent,
        "faiss_vector_count": faiss_store.get_vector_count(),
        "atlas_doc_count": atlas_doc_count,
        "daemon_uptime_seconds": uptime_seconds,
        "active_ws_connections": len(
            broadcaster._connections if broadcaster else []
        ),
    }
    return web.json_response(metrics)


async def _get_health(request: web.Request) -> web.Response:
    """
    GET /health

    Checks FAISS, Atlas, cloud Ollama, and local Ollama liveness.
    """
    assert faiss_store is not None
    assert inference_client is not None

    faiss_ok = faiss_store.index is not None

    atlas_ok = False
    if atlas_store is not None:
        try:
            await atlas_store.get_doc_count()
            atlas_ok = True
        except Exception:
            atlas_ok = False

    cloud_url = inference_client._cloud_endpoint
    local_url = inference_client._local_endpoint

    cloud_ok = await inference_client.health_check(cloud_url) if cloud_url else False
    local_ok = await inference_client.health_check(local_url)

    return web.json_response(
        {
            "faiss": {"ok": faiss_ok, "vector_count": faiss_store.get_vector_count()},
            "atlas": {"ok": atlas_ok},
            "cloud_ollama": {"ok": cloud_ok, "url": cloud_url},
            "local_ollama": {"ok": local_ok, "url": local_url},
        }
    )


async def _get_session(request: web.Request) -> web.Response:
    """
    GET /session

    Returns the current inference client circuit-breaker status.
    """
    assert inference_client is not None
    return web.json_response(inference_client.get_status())


async def _post_approve_intent(request: web.Request) -> web.Response:
    """
    POST /intents/{id}/approve

    Body: {"approved_by": "..."}
    Returns {"success": true/false}.
    """
    assert control_plane is not None

    try:
        intent_id = int(request.match_info["id"])
    except (KeyError, ValueError):
        return web.json_response({"error": "Invalid intent id"}, status=400)

    try:
        body = await request.json()
        approved_by: str = body.get("approved_by", "anonymous")
    except json.JSONDecodeError:
        approved_by = "anonymous"

    success = control_plane.approve_intent(intent_id, approved_by)
    return web.json_response({"success": success})


async def _get_intents(request: web.Request) -> web.Response:
    """
    GET /intents[?page=1&limit=20]

    Returns a paginated list of audit-log entries.
    """
    assert control_plane is not None

    try:
        page = int(request.rel_url.query.get("page", "1"))
        limit = int(request.rel_url.query.get("limit", "20"))
    except ValueError:
        page, limit = 1, 20

    return web.json_response(control_plane.get_intents(page=page, limit=limit))


async def _ws_handler(request: web.Request) -> web.WebSocketResponse:
    """
    GET /ws

    Upgrades the connection to WebSocket and registers it with the broadcaster.
    """
    assert broadcaster is not None

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Wrap the aiohttp WS in a thin adapter so broadcaster can call ws.send()
    class _WsAdapter:
        async def send(self, data: str) -> None:
            await ws.send_str(data)

    adapter = _WsAdapter()
    broadcaster.register(adapter)
    logger.info(f"WebSocket client connected from {request.remote}")

    try:
        async for msg in ws:
            # We don't process inbound WS messages from clients currently
            pass
    finally:
        broadcaster.unregister(adapter)
        logger.info(f"WebSocket client disconnected from {request.remote}")

    return ws


# ---------------------------------------------------------------------------
# Background periodic metrics push
# ---------------------------------------------------------------------------


async def _periodic_metrics(interval_seconds: int = 10) -> None:
    """
    Emit a metrics_update event to all WebSocket clients every
    *interval_seconds* seconds.

    Args:
        interval_seconds: Cadence for metrics pushes.
    """
    assert faiss_store is not None
    assert broadcaster is not None

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            uptime = int(time.time() - _DAEMON_START)
            atlas_count = 0
            if atlas_store is not None:
                try:
                    atlas_count = await atlas_store.get_doc_count()
                except Exception:
                    atlas_count = -1

            metrics = {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_available_mb": psutil.virtual_memory().available // (1024 * 1024),
                "faiss_vector_count": faiss_store.get_vector_count(),
                "atlas_doc_count": atlas_count,
                "daemon_uptime_seconds": uptime,
            }
            await broadcaster.emit_metrics_update(metrics)
        except Exception as exc:
            logger.warning(f"_periodic_metrics error: {exc!r}")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


async def main() -> None:
    """
    Bootstrap all AIOS daemon subsystems and start the aiohttp IPC server.

    Initialisation order:
    1.  Load .env
    2.  Setup logging
    3.  Ensure data/ directory exists
    4.  Build all service instances
    5.  Load FAISS index
    6.  Connect to Atlas (warn, don't crash if unavailable)
    7.  Setup watchdog observer on mock_logs/
    8.  Build aiohttp app with routes
    9.  Start watchdog observer
    10. Start periodic metrics push task
    11. Start aiohttp TCP site on localhost:8765
    12. Run forever
    """
    global embedder, faiss_store, atlas_store, retriever, sanitiser
    global inference_client, intent_parser, control_plane, broadcaster, executor

    # Step 1: Load environment variables from .env
    load_dotenv()

    # Step 2: Logging
    _setup_logging()

    logger.info("AIOS Daemon starting up…")

    # Step 3: Ensure data/ directory exists
    Path("data").mkdir(parents=True, exist_ok=True)
    Path("mock_logs").mkdir(parents=True, exist_ok=True)

    # Step 4: Initialise services
    executor = ThreadPoolExecutor(
        max_workers=int(os.getenv("DAEMON_THREADS", "4")),
        thread_name_prefix="aios-worker",
    )

    embedder = EmbeddingService(
        model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )

    faiss_store = FAISSStore(
        index_path=os.getenv("FAISS_INDEX_PATH", "data/faiss.index"),
        metadata_path=os.getenv("FAISS_META_PATH", "data/faiss_meta.pkl"),
        dimensions=int(os.getenv("EMBEDDING_DIM", "384")),
    )

    atlas_store = CachedMongoDB(
        uri=os.getenv("MONGODB_URI", ""),
        db_name=os.getenv("ATLAS_DB", "aios_memory"),
        collection_name=os.getenv("ATLAS_COLLECTION", "system_logs"),
    )

    sanitiser = TelemetrySanitiser()

    inference_client = InferenceClient(
        config={
            "OLLAMA_ENDPOINT": os.getenv("OLLAMA_ENDPOINT", ""),
            "LOCAL_OLLAMA": os.getenv("LOCAL_OLLAMA", "http://localhost:11434"),
            "MODEL_NAME": os.getenv("MODEL_NAME", "llama3"),
            "NGROK_AUTH_USER": os.getenv("NGROK_AUTH_USER", ""),
            "NGROK_AUTH_PASS": os.getenv("NGROK_AUTH_PASS", ""),
        }
    )

    intent_parser = IntentParser()
    control_plane = DeterministicControlPlane(
        db_path=os.getenv("AUDIT_DB_PATH", "data/aios_audit.db")
    )
    broadcaster = WebSocketBroadcaster()

    retriever = HybridRetriever(
        faiss_store=faiss_store,
        atlas_store=atlas_store,
        embedder=embedder,
        executor=executor,
    )

    # Step 5: Load FAISS index
    global main_loop
    loop = asyncio.get_event_loop()
    main_loop = loop
    await loop.run_in_executor(executor, faiss_store.load_or_create)
    logger.info(
        f"FAISS store ready. Vectors: {faiss_store.get_vector_count()}"
    )

    # Step 6: Connect Atlas (non-fatal)
    if atlas_store.uri:
        try:
            await atlas_store.connect()
        except RuntimeError as exc:
            logger.warning(f"Atlas unavailable: {exc!r}. Proceeding FAISS-only.")
            atlas_store = None  # type: ignore[assignment]
            retriever._atlas = None  # type: ignore[assignment]
    else:
        logger.warning(
            "MONGODB_URI not set — Atlas store disabled. Using FAISS only."
        )
        atlas_store = None  # type: ignore[assignment]

    # Step 7: Setup watchdog observer on mock_logs/
    mock_log_dir = Path("mock_logs").resolve()
    event_handler = LogFileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, str(mock_log_dir), recursive=True)

    # Step 8: Build aiohttp application
    app = web.Application()
    app.router.add_post("/query", _post_query)
    app.router.add_get("/metrics", _get_metrics)
    app.router.add_get("/health", _get_health)
    app.router.add_get("/session", _get_session)
    app.router.add_post("/intents/{id}/approve", _post_approve_intent)
    app.router.add_get("/intents", _get_intents)
    app.router.add_get("/ws", _ws_handler)

    # Step 9: Start watchdog observer
    observer.start()
    logger.info(f"Watchdog observer started on '{mock_log_dir}'")

    # Step 10: Start periodic metrics background task
    asyncio.create_task(_periodic_metrics(interval_seconds=10))
    logger.info("Periodic metrics task started (10s interval)")

    # Step 11: Start aiohttp site
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8765)
    await site.start()

    logger.info("AIOS Daemon started. IPC server on localhost:8765")

    # Step 12: Run forever
    try:
        await asyncio.Event().wait()
    finally:
        observer.stop()
        observer.join()
        executor.shutdown(wait=False)
        logger.info("AIOS Daemon shutting down.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
