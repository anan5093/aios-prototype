"""
tests/conftest.py — Shared pytest fixtures for the AIOS Prototype test suite.

Adds the daemon directory to sys.path so that all daemon modules are
importable without installation.  Provides reusable fixtures for a
temporary SQLite path and a bank of sample metadata chunks.
"""

import os
import sys
import pytest


@pytest.fixture(autouse=True)
def mock_sniffio():
    """Ensure sniffio detects the asyncio library during tests under Python 3.14."""
    import sniffio
    token = sniffio.current_async_library_cvar.set("asyncio")
    yield
    sniffio.current_async_library_cvar.reset(token)

# ---------------------------------------------------------------------------
# Path bootstrap — ensure daemon modules are importable
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DAEMON_DIR = os.path.join(_PROJECT_ROOT, "daemon")

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _DAEMON_DIR not in sys.path:
    sys.path.insert(0, _DAEMON_DIR)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db_path(tmp_path: pytest.TempPathFactory) -> str:
    """Return an absolute path to a temporary SQLite database file.

    The file does not exist yet — the caller is expected to create it.
    The parent directory is guaranteed to exist (provided by pytest's
    ``tmp_path`` fixture).

    Returns:
        Absolute path string ending in ``/audit.db``.
    """
    return str(tmp_path / "audit.db")


@pytest.fixture
def sample_chunks() -> list[dict]:
    """Return 10 realistic OOM-log metadata dicts for use in tests.

    Each dict has the keys required by the retrieval pipeline:
    ``chunk_id``, ``source_file``, ``timestamp``, ``log_level``,
    ``content``, ``score``, and ``source_store``.

    Returns:
        List of 10 metadata dicts with decreasing relevance scores.
    """
    return [
        {
            "chunk_id": f"chunk_{i:04d}",
            "source_file": "kern.log",
            "timestamp": "2026-06-04T10:00:00Z",
            "log_level": "ERROR",
            "content": (
                f"Out of memory: Kill process {1000 + i} (chrome) "
                f"score {800 - i * 10} or sacrifice child"
            ),
            "score": 0.9 - i * 0.05,
            "source_store": "faiss",
        }
        for i in range(10)
    ]
