"""
daemon/inference_client.py — Local Ollama inference client.

Primary & Only Endpoint: Local Ollama at localhost:11434
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional


class InferenceClient:
    """
    Async streaming inference client for local Ollama endpoint.
    """

    def __init__(self, config: dict) -> None:
        """
        Initialise the client from a configuration dict.

        Expected keys:
            ``LOCAL_OLLAMA``        — local base URL (e.g. ``http://localhost:11434``)
            ``MODEL_NAME``          — Ollama model tag (e.g. ``llama3``)

        Args:
            config: Dict of configuration values (typically from env vars).
        """
        self._local_endpoint: str = config.get(
            "LOCAL_OLLAMA", "http://localhost:11434"
        )
        self._model_name: str = config.get("MODEL_NAME", "llama3")

        self._logger = logging.getLogger(f"{__name__}.InferenceClient")
        self._logger.info(
            f"InferenceClient initialised: local='{self._local_endpoint}', model='{self._model_name}'"
        )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self, url: str, timeout: float = 1.0) -> bool:
        """
        Probe *url* to verify the Ollama server is alive.

        Args:
            url: Base URL to check (``/api/tags`` is appended).
            timeout: Max seconds to wait for response.

        Returns:
            ``True`` if the server responds with HTTP 200, ``False`` otherwise.
        """
        import httpx  # type: ignore

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{url}/api/tags",
                    headers={"ngrok-skip-browser-warning": "true"}
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
        Stream tokens from local Ollama's ``/api/generate`` endpoint.

        The response is NDJSON; each line is parsed and the ``response``
        field is yielded until ``done == True``.

        Args:
            prompt: Fully-assembled prompt string.

        Yields:
            Partial text tokens from the model.

        Raises:
            Exception: Any httpx or JSON error is re-raised.
        """
        import httpx  # type: ignore

        body = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": True,
        }

        self._logger.debug(
            f"stream_generate: endpoint={self._local_endpoint}"
        )

        try:
            # Set connection timeout to 3s and read timeout to 10s to fail fast
            timeout_config = httpx.Timeout(
                connect=3.0,
                read=10.0,
                write=5.0,
                pool=5.0
            )
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                async with client.stream(
                    "POST",
                    f"{self._local_endpoint}/api/generate",
                    json=body,
                    headers={"ngrok-skip-browser-warning": "true"}
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

        except Exception as exc:
            self._logger.warning(
                f"stream_generate failed: {exc!r}"
            )
            raise

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """
        Return a mock circuit breaker status pointing to local Ollama for backward compatibility.
        """
        return {
            "backend": "local",
            "circuit_state": "CLOSED",
            "failure_count": 0,
            "active_endpoint": self._local_endpoint,
            "fallback_endpoint": self._local_endpoint,
        }
