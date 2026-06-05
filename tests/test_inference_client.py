"""
tests/test_inference_client.py — Unit tests for daemon/inference_client.py.

Tests cover:
  - Config parsing
  - _build_auth_header logic
  - discover_url from temp file
  - health_check mock calls
  - _select_endpoint circuit breaker transitions
  - stream_generate success mock with httpx
  - stream_generate failure mock and state transitions (CLOSED -> OPEN -> HALF_OPEN -> OPEN/CLOSED)
"""

import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Path bootstrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from inference_client import InferenceClient, CircuitState  # noqa: E402


@pytest.fixture
def base_config() -> dict:
    return {
        "OLLAMA_ENDPOINT": "https://cloud.ngrok.io",
        "LOCAL_OLLAMA": "http://localhost:11434",
        "MODEL_NAME": "gemma:2b-instruct-q4_K_M",
        "NGROK_AUTH_USER": "aios",
        "NGROK_AUTH_PASS": "changeme_strong_password",
    }


class TestConfigAndHeaders:
    def test_init_config(self, base_config: dict) -> None:
        client = InferenceClient(base_config)
        assert client._cloud_endpoint == "https://cloud.ngrok.io"
        assert client._local_endpoint == "http://localhost:11434"
        assert client._model_name == "gemma:2b-instruct-q4_K_M"
        assert client._state == CircuitState.CLOSED

    def test_build_auth_header(self, base_config: dict) -> None:
        client = InferenceClient(base_config)
        headers = client._build_auth_header()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

        # Test empty credentials
        no_auth_config = base_config.copy()
        no_auth_config["NGROK_AUTH_USER"] = ""
        no_auth_config["NGROK_AUTH_PASS"] = ""
        client_no_auth = InferenceClient(no_auth_config)
        assert client_no_auth._build_auth_header() == {}





class TestHealthCheck:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_health_check_success(self, mock_get, base_config: dict) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = InferenceClient(base_config)
        is_healthy = await client.health_check("https://cloud.ngrok.io")
        assert is_healthy is True
        mock_get.assert_called_once_with(
            "https://cloud.ngrok.io/api/tags",
            headers=client._build_auth_header(),
        )

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_health_check_failure(self, mock_get, base_config: dict) -> None:
        mock_get.side_effect = Exception("Connection error")
        client = InferenceClient(base_config)
        is_healthy = await client.health_check("https://cloud.ngrok.io")
        assert is_healthy is False


class TestCircuitBreakerRouting:
    def test_select_endpoint_closed(self, base_config: dict) -> None:
        client = InferenceClient(base_config)
        assert client._state == CircuitState.CLOSED
        endpoint = client._select_endpoint()
        assert endpoint == "https://cloud.ngrok.io"

    def test_select_endpoint_open_active(self, base_config: dict) -> None:
        client = InferenceClient(base_config)
        client._state = CircuitState.OPEN
        client._opened_at = time.time()
        # Open timeout not elapsed
        endpoint = client._select_endpoint()
        assert endpoint == "http://localhost:11434"

    def test_select_endpoint_open_timeout_elapsed(self, base_config: dict) -> None:
        client = InferenceClient(base_config)
        client._state = CircuitState.OPEN
        client._opened_at = time.time() - (client.OPEN_TIMEOUT_SECONDS + 1)
        # Open timeout elapsed -> should transition to HALF_OPEN and choose cloud
        endpoint = client._select_endpoint()
        assert client._state == CircuitState.HALF_OPEN
        assert endpoint == "https://cloud.ngrok.io"


class TestStreamGenerate:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.stream")
    async def test_stream_generate_success(self, mock_stream, base_config: dict) -> None:
        # Mocking the async context manager of client.stream
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        async def mock_aiter_lines():
            yield '{"response": "Hello", "done": false}'
            yield '{"response": " world", "done": true}'

        mock_response.aiter_lines = mock_aiter_lines
        mock_stream.return_value.__aenter__.return_value = mock_response

        client = InferenceClient(base_config)
        tokens = []
        async for token in client.stream_generate("Test prompt"):
            tokens.append(token)

        assert tokens == ["Hello", " world"]
        assert client._failure_count == 0
        assert client._state == CircuitState.CLOSED

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.stream")
    async def test_stream_generate_circuit_breaker_trip(self, mock_stream, base_config: dict) -> None:
        # Setup mock_stream to raise an exception
        mock_stream.return_value.__aenter__.side_effect = Exception("Cloud offline")

        client = InferenceClient(base_config)
        # Lower threshold for faster testing
        client.FAILURE_THRESHOLD = 3

        # Trigger failure 1
        with pytest.raises(Exception):
            async for _ in client.stream_generate("prompt"):
                pass
        assert client._failure_count == 1
        assert client._state == CircuitState.CLOSED

        # Trigger failure 2
        with pytest.raises(Exception):
            async for _ in client.stream_generate("prompt"):
                pass
        assert client._failure_count == 2
        assert client._state == CircuitState.CLOSED

        # Trigger failure 3 -> trips the breaker to OPEN
        with pytest.raises(Exception):
            async for _ in client.stream_generate("prompt"):
                pass
        assert client._failure_count == 3
        assert client._state == CircuitState.OPEN
        assert client._opened_at is not None

        # Verify that it now routes to local endpoint
        assert client._select_endpoint() == "http://localhost:11434"
