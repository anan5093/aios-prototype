"""
daemon/ws_broadcaster.py — WebSocket broadcaster for real-time event streaming.

Maintains a set of active WebSocket connections.
Broadcasts typed events to all connected clients.
Silently removes dead connections.
"""

import asyncio
import json
import logging
from typing import Any, Optional


class WebSocketBroadcaster:
    """
    Manages a set of active WebSocket connections and provides typed
    broadcast helpers for every AIOS event type.

    Dead connections are silently removed when a send fails, so callers
    never need to manage connection lifecycle beyond initial registration.
    """

    def __init__(self) -> None:
        self._connections: set[Any] = set()
        self._logger = logging.getLogger(f"{__name__}.WebSocketBroadcaster")

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def register(self, ws: Any) -> None:
        """
        Register *ws* as an active subscriber.

        Args:
            ws: An open WebSocket connection object (must have an async
                ``send(data: str)`` coroutine method).
        """
        self._connections.add(ws)
        self._logger.debug(
            f"WebSocket registered. Active connections: {len(self._connections)}"
        )

    def unregister(self, ws: Any) -> None:
        """
        Remove *ws* from the active set (no-op if not present).

        Args:
            ws: The WebSocket connection to remove.
        """
        self._connections.discard(ws)
        self._logger.debug(
            f"WebSocket unregistered. Active connections: {len(self._connections)}"
        )

    # ------------------------------------------------------------------
    # Core broadcast
    # ------------------------------------------------------------------

    async def broadcast(self, event_type: str, payload: dict) -> None:
        """
        Send a typed JSON message to all active connections.

        The outgoing message merges *event_type* into *payload*::

            {"type": event_type, **payload}

        Dead connections (any send error) are silently removed.

        Args:
            event_type: String identifier for the event kind.
            payload:    Additional key/value data to include in the message.
        """
        if not self._connections:
            return

        message = json.dumps({"type": event_type, **payload})
        # Iterate over a snapshot to avoid mutation-during-iteration errors
        dead: list[Any] = []
        for ws in list(self._connections):
            try:
                await ws.send(message)
            except Exception as exc:
                self._logger.debug(
                    f"broadcast: send failed for {ws!r}: {exc!r} — removing"
                )
                dead.append(ws)

        for ws in dead:
            self.unregister(ws)

    # ------------------------------------------------------------------
    # Typed event helpers
    # ------------------------------------------------------------------

    async def emit_token(self, token: str, query_id: str) -> None:
        """
        Emit a single streaming token to all clients.

        Args:
            token:    The partial text token from the LLM.
            query_id: Identifier linking this token to a specific query.
        """
        await self.broadcast(
            "token",
            {"token": token, "query_id": query_id},
        )

    async def emit_stream_done(self, query_id: str, latency_ms: int) -> None:
        """
        Notify clients that the streaming generation is complete.

        Args:
            query_id:   Identifier of the completed query.
            latency_ms: End-to-end latency in milliseconds.
        """
        await self.broadcast(
            "stream_done",
            {"query_id": query_id, "latency_ms": latency_ms},
        )

    async def emit_intent_parsed(self, intent: dict, query_id: str) -> None:
        """
        Broadcast the parsed AI intent to all clients.

        Args:
            intent:   The :class:`~intent_parser.AIIntent` dict representation.
            query_id: Identifier of the query that produced this intent.
        """
        await self.broadcast(
            "intent_parsed",
            {"intent": intent, "query_id": query_id},
        )

    async def emit_validation_result(
        self,
        result: str,
        intent_id: int,
    ) -> None:
        """
        Broadcast the control-plane validation result.

        Args:
            result:    Validation status string (e.g. ``VALIDATED``,
                       ``REJECTED``, ``PENDING_REVIEW``).
            intent_id: Audit-log row ID for the intent.
        """
        await self.broadcast(
            "validation_result",
            {"result": result, "intent_id": intent_id},
        )

    async def emit_circuit_breaker(self, state: str, fallback: bool) -> None:
        """
        Broadcast a circuit-breaker state-change event.

        Args:
            state:    New circuit state string (e.g. ``OPEN``, ``CLOSED``).
            fallback: ``True`` if the daemon is currently using local Ollama.
        """
        await self.broadcast(
            "circuit_breaker",
            {"state": state, "fallback": fallback},
        )

    async def emit_rag_retrieved(
        self,
        chunks: list[dict],
        query_id: str,
    ) -> None:
        """
        Broadcast the list of RAG chunks retrieved for a query.

        Args:
            chunks:   Retrieved context chunks (embedding field omitted).
            query_id: Identifier of the query that triggered retrieval.
        """
        await self.broadcast(
            "rag_retrieved",
            {"chunks": chunks, "query_id": query_id},
        )

    async def emit_metrics_update(self, metrics: dict) -> None:
        """
        Broadcast a system-metrics snapshot.

        Args:
            metrics: Dict of current metrics (CPU, memory, vector counts, etc.).
        """
        await self.broadcast("metrics_update", {"metrics": metrics})
