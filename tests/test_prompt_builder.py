"""
tests/test_prompt_builder.py — Unit tests for daemon/prompt_builder.py.

Tests cover:
  - Permitted action keywords present in the prompt
  - All chunk contents embedded in the output
  - XML structure (<context>, <chunk ...>)
  - Word count budget enforcement
  - Minimum 3 chunks always preserved even under tight budget
  - Prompt starts with the system role prefix
"""

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from prompt_builder import SYSTEM_ROLE_PROMPT, build_prompt  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_chunks(n: int, score_start: float = 0.9) -> list[dict]:
    """Return *n* sample OOM chunk dicts with decreasing scores.

    Args:
        n:           Number of chunks to generate.
        score_start: Score of the first (highest-relevance) chunk.

    Returns:
        List of chunk dicts compatible with build_prompt().
    """
    return [
        {
            "chunk_id": f"c{i}",
            "source_file": "kern.log",
            "timestamp": "2026-06-04T10:00:00Z",
            "log_level": "ERROR",
            "content": f"OOM event {i} process chrome score {800 - i}",
            "score": score_start - i * 0.02,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPermittedAction:
    """Tests that the system role prompt contains permitted action strings."""

    def test_prompt_contains_permitted_action(self) -> None:
        """build_prompt output must reference at least one permitted action (suggest_renice)."""
        prompt = build_prompt("analyse memory", make_chunks(3))
        assert "suggest_renice" in prompt, (
            "Expected 'suggest_renice' in prompt — SYSTEM_ROLE_PROMPT is missing it."
        )


class TestChunkContentPresence:
    """Tests that all provided chunk contents appear verbatim in the prompt."""

    def test_prompt_contains_chunk_content(self) -> None:
        """Every chunk's 'content' string must appear literally in the built prompt."""
        chunks = make_chunks(3)
        prompt = build_prompt("test query", chunks)
        for chunk in chunks:
            assert chunk["content"] in prompt, (
                f"Chunk content not found in prompt: {chunk['content']!r}"
            )


class TestXMLFormat:
    """Tests that the context block uses the expected XML structure."""

    def test_chunks_are_in_xml_format(self) -> None:
        """The prompt must contain <context>, <chunk ...>, source=, score=, log_level= tags."""
        prompt = build_prompt("test", make_chunks(3))

        assert "<context>" in prompt, "Missing '<context>' tag in prompt."
        assert "<chunk " in prompt, "Missing '<chunk ' opening tag in prompt."
        assert "source=" in prompt, "Missing 'source=' attribute in chunk tag."
        assert "score=" in prompt, "Missing 'score=' attribute in chunk tag."
        assert "log_level=" in prompt, "Missing 'log_level=' attribute in chunk tag."


class TestWordCountLimit:
    """Tests that build_prompt respects the max_words budget."""

    def test_word_count_within_limit(self) -> None:
        """With max_words=2800 and 20 chunks, the total word count must not exceed 2800."""
        chunks = make_chunks(20)
        prompt = build_prompt("analyse", chunks, max_words=2800)
        word_count = len(prompt.split())
        assert word_count <= 2800, (
            f"Prompt exceeds max_words=2800: got {word_count} words."
        )


class TestMinimumChunks:
    """Tests that at least 3 chunks are always kept even under extreme budget pressure."""

    def test_minimum_3_chunks_preserved(self) -> None:
        """With max_words=100 (very tight), at least 3 chunks must still appear."""
        chunks = make_chunks(20)
        prompt = build_prompt("analyse", chunks, max_words=100)
        chunk_count = prompt.count("<chunk ")
        assert chunk_count >= 3, (
            f"Expected at least 3 <chunk ...> tags, got {chunk_count}."
        )


class TestSystemRolePrefix:
    """Tests that the prompt starts with the defined SYSTEM_ROLE_PROMPT."""

    def test_prompt_starts_with_system_role(self) -> None:
        """build_prompt output must begin with the first 50 chars of SYSTEM_ROLE_PROMPT."""
        prompt = build_prompt("test", make_chunks(3))
        prefix = SYSTEM_ROLE_PROMPT[:50]
        assert prompt.startswith(prefix), (
            f"Prompt does not start with SYSTEM_ROLE_PROMPT prefix.\n"
            f"Expected prefix: {prefix!r}\n"
            f"Prompt start:    {prompt[:60]!r}"
        )
