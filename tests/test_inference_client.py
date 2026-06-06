"""
tests/test_inference_client.py — Unit tests for daemon/inference_client.py.

Tests cover:
  - Config parsing
  - health_check mock calls
  - stream_generate success mock
  - stream_generate failure mock
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Path bootstrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from inference_client import InferenceClient  # noqa: E402


@pytest.fixture
def base_config() -> dict:
    return {
        "LOCAL_OLLAMA": "http://localhost:11434",
        "MODEL_NAME": "gemma:2b-instruct-q4_K_M",
    }


class TestConfigAndHeaders:
    def test_init_config(self, base_config: dict) -> None:
        client = InferenceClient(base_config)
        assert client._local_endpoint == "http://localhost:11434"
        assert client._model_name == "gemma:2b-instruct-q4_K_M"

    def test_get_status(self, base_config: dict) -> None:
        client = InferenceClient(base_config)
        status = client.get_status()
        assert status["backend"] == "local"
        assert status["circuit_state"] == "CLOSED"
        assert status["active_endpoint"] == "http://localhost:11434"


class TestHealthCheck:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_health_check_success(self, mock_client_class, base_config: dict) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        client = InferenceClient(base_config)
        is_healthy = await client.health_check("http://localhost:11434")
        assert is_healthy is True
        mock_client.get.assert_called_once_with(
            "http://localhost:11434/api/tags",
            headers={"ngrok-skip-browser-warning": "true"}
        )

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_health_check_failure(self, mock_client_class, base_config: dict) -> None:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection error")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        client = InferenceClient(base_config)
        is_healthy = await client.health_check("http://localhost:11434")
        assert is_healthy is False


class TestStreamGenerate:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_stream_generate_success(self, mock_client_class, base_config: dict) -> None:
        mock_client = AsyncMock()
        mock_client.stream = MagicMock()
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        async def mock_aiter_lines():
            yield '{"response": "Hello", "done": false}'
            yield '{"response": " world", "done": true}'

        mock_response.aiter_lines = mock_aiter_lines
        mock_client.stream.return_value.__aenter__.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        client = InferenceClient(base_config)
        tokens = []
        async for token in client.stream_generate("Test prompt"):
            tokens.append(token)

        assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_stream_generate_failure(self, mock_client_class, base_config: dict) -> None:
        mock_client = AsyncMock()
        mock_client.stream = MagicMock()
        mock_client.stream.return_value.__aenter__.side_effect = Exception("Ollama offline")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        client = InferenceClient(base_config)
        with pytest.raises(Exception):
            async for _ in client.stream_generate("prompt"):
                pass
