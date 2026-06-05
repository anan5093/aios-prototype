"""
daemon/inference_client.py — Colab/Ollama inference client with 3-state circuit breaker.

Primary: Google Colab T4 via ngrok tunnel (HTTPS + Basic Auth)
Fallback: Local Ollama at localhost:11434

Circuit Breaker States:
  CLOSED    — normal operation, using cloud endpoint
  OPEN      — cloud failed, using local fallback
  HALF_OPEN — testing if cloud has recovered
"""

import asyncio
import base64
import enum
import json
import logging
import os
import time
from typing import AsyncGenerator, Optional


class CircuitState(enum.Enum):
    """Three-state circuit breaker values."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class InferenceClient:
    """
    Async streaming inference client with cloud-first routing and a
    3-state circuit breaker for automatic fallback to local Ollama.

    Circuit Breaker behaviour:
    * **CLOSED** — all requests go to the cloud ngrok endpoint.
    * **OPEN** — cloud has failed ``FAILURE_THRESHOLD`` times.
      Requests fall back to local Ollama.  After ``OPEN_TIMEOUT_SECONDS``
      the breaker moves to HALF_OPEN to test recovery.
    * **HALF_OPEN** — the next request is sent to cloud as a probe.
      Success → CLOSED; failure → OPEN (reset timer).
    """

    FAILURE_THRESHOLD: int = 3
    OPEN_TIMEOUT_SECONDS: int = 30
    REQUEST_TIMEOUT_SECONDS: int = 30

    def __init__(self, config: dict) -> None:
        """
        Initialise the client from a configuration dict.

        Expected keys:
            ``OLLAMA_ENDPOINT``     — cloud ngrok base URL (e.g. ``https://abc.ngrok.io``)
            ``LOCAL_OLLAMA``        — local base URL (e.g. ``http://localhost:11434``)
            ``MODEL_NAME``          — Ollama model tag (e.g. ``llama3``)
            ``NGROK_AUTH_USER``     — Basic Auth username for the cloud endpoint
            ``NGROK_AUTH_PASS``     — Basic Auth password for the cloud endpoint
            ``NGROK_DISCOVERY_FILE``— path to a file containing the current ngrok URL

        Args:
            config: Dict of configuration values (typically from env vars).
        """
        self._cloud_endpoint: str = config.get("OLLAMA_ENDPOINT", "")
        self._local_endpoint: str = config.get(
            "LOCAL_OLLAMA", "http://localhost:11434"
        )
        self._model_name: str = config.get("MODEL_NAME", "llama3")
        self._auth_user: str = config.get("NGROK_AUTH_USER", "")
        self._auth_pass: str = config.get("NGROK_AUTH_PASS", "")

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._opened_at: Optional[float] = None
        self._active_endpoint: str = self._cloud_endpoint

        self._logger = logging.getLogger(f"{__name__}.InferenceClient")
        self._logger.info(
            f"InferenceClient initialised: cloud='{self._cloud_endpoint}', "
            f"local='{self._local_endpoint}', model='{self._model_name}'"
        )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self, url: str) -> bool:
        """
        Probe *url* to verify the Ollama server is alive.

        Args:
            url: Base URL to check (``/api/tags`` is appended).

        Returns:
            ``True`` if the server responds with HTTP 200, ``False`` otherwise.
        """
        import httpx  # type: ignore

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{url}/api/tags",
                    headers=self._build_auth_header(),
                )
                return response.status_code == 200
        except Exception as exc:
            self._logger.debug(f"health_check({url}) failed: {exc!r}")
            return False

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    async def stream_generate(
        self, prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens from Ollama's ``/api/generate`` endpoint.

        Routing is determined by the current circuit-breaker state:
        * CLOSED / HALF_OPEN → cloud endpoint (with Basic Auth)
        * OPEN (and not timed-out) → local Ollama endpoint

        The response is NDJSON; each line is parsed and the ``response``
        field is yielded until ``done == True``.

        Args:
            prompt: Fully-assembled prompt string.

        Yields:
            Partial text tokens from the model.

        Raises:
            Exception: Any httpx or JSON error is re-raised after the circuit
                       breaker state is updated.
        """
        import httpx  # type: ignore

        endpoint = self._select_endpoint()
        use_auth = self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

        headers = self._build_auth_header() if use_auth else {}
        body = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": True,
        }

        self._logger.debug(
            f"stream_generate: state={self._state.value}, endpoint={endpoint}"
        )

        try:
            async with httpx.AsyncClient(
                timeout=self.REQUEST_TIMEOUT_SECONDS
            ) as client:
                async with client.stream(
                    "POST",
                    f"{endpoint}/api/generate",
                    json=body,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token: str = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done", False):
                            break

            # Success path — reset failure counter
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._logger.info(
                    "Circuit breaker: HALF_OPEN → CLOSED (cloud recovered)"
                )
                self._state = CircuitState.CLOSED
                self._opened_at = None

        except Exception as exc:
            self._failure_count += 1
            self._logger.warning(
                f"stream_generate failed (failure #{self._failure_count}): {exc!r}"
            )

            if self._state == CircuitState.CLOSED:
                if self._failure_count >= self.FAILURE_THRESHOLD:
                    self._state = CircuitState.OPEN
                    self._opened_at = time.time()
                    self._logger.error(
                        f"Circuit breaker: CLOSED → OPEN after "
                        f"{self._failure_count} failures"
                    )
            elif self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
                self._logger.error(
                    "Circuit breaker: HALF_OPEN → OPEN (probe failed)"
                )

            raise

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """
        Return a snapshot of the circuit breaker state and routing info.

        Returns:
            Dict with keys: ``backend``, ``circuit_state``, ``failure_count``,
            ``active_endpoint``, ``fallback_endpoint``.
        """
        is_cloud = self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)
        return {
            "backend": "cloud" if is_cloud else "local",
            "circuit_state": self._state.value,
            "failure_count": self._failure_count,
            "active_endpoint": self._active_endpoint,
            "fallback_endpoint": self._local_endpoint,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_endpoint(self) -> str:
        """
        Choose the target endpoint based on the current circuit state.

        Side-effect: may transition OPEN → HALF_OPEN if the open timeout has
        elapsed.
        """
        if self._state == CircuitState.OPEN:
            elapsed = (
                time.time() - self._opened_at
                if self._opened_at is not None
                else float("inf")
            )
            if elapsed >= self.OPEN_TIMEOUT_SECONDS:
                self._state = CircuitState.HALF_OPEN
                self._logger.info(
                    f"Circuit breaker: OPEN → HALF_OPEN "
                    f"(timeout {self.OPEN_TIMEOUT_SECONDS}s elapsed)"
                )
                return self._cloud_endpoint
            return self._local_endpoint

        # CLOSED or HALF_OPEN — use cloud
        return self._cloud_endpoint

    def _build_auth_header(self) -> dict:
        """
        Build an HTTP Basic Auth header from the configured credentials.

        Returns:
            Dict with ``Authorization`` header, or empty dict if no credentials
            are configured.
        """
        if not self._auth_user and not self._auth_pass:
            return {}
        credentials = base64.b64encode(
            f"{self._auth_user}:{self._auth_pass}".encode()
        ).decode()
        return {"Authorization": f"Basic {credentials}"}
