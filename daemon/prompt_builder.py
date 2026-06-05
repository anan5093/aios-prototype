"""
daemon/prompt_builder.py — Structured prompt construction for AIOS AI inference.

Builds fully-formed prompts from system role, RAG context chunks, and user query.
Enforces word-count limits by trimming lowest-scoring chunks (keeps minimum 3).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System-role prompt — MUST NOT be modified
# ---------------------------------------------------------------------------

SYSTEM_ROLE_PROMPT: str = (
    "You are the AIOS Intelligence Daemon — a highly privileged AI middleware "
    "that analyses Linux system telemetry and proposes optimisation intents.\n\n"
    "Your task is to:\n"
    "1. Study the system context provided below (retrieved from real log history).\n"
    "2. Identify the most pressing system issue.\n"
    "3. Propose exactly ONE optimisation intent in valid JSON format.\n\n"
    "PERMITTED ACTIONS (you may ONLY suggest one of these exact strings):\n"
    "- suggest_renice        → Change process scheduling priority via renice\n"
    "- suggest_swap_adjust   → Adjust swappiness or swap partition parameters\n"
    "- suggest_log_rotate    → Force log rotation to reclaim disk space\n"
    "- suggest_cgroup_limit  → Suggest a cgroup memory or CPU limit for a process\n\n"
    "RESPONSE FORMAT — you MUST respond with ONLY a JSON object, no prose before or after:\n"
    "{\n"
    '  "action_type": "<one of the four permitted actions>",\n'
    '  "target_resource": "<specific process name or system parameter>",\n'
    '  "proposed_value": "<concrete recommended value, e.g. \'10\' for renice, \'40\' for swappiness>",\n'
    '  "confidence_score": <float between 0.0 and 1.0>,\n'
    '  "reasoning_summary": "<1-2 sentences citing specific evidence from the context chunks>"\n'
    "}\n\n"
    "CRITICAL RULES:\n"
    "- You MUST cite specific log entries from the context to justify your suggestion.\n"
    "- If you cannot identify a clear issue with high confidence, set confidence_score below 0.75.\n"
    "- NEVER suggest actions outside the permitted list.\n"
    "- NEVER include prose outside the JSON block.\n"
    "- NEVER suggest actions that modify security settings, delete files, or change user permissions."
)


def _format_chunk(index: int, chunk: dict) -> str:
    """
    Render a single RAG chunk as an XML element.

    Args:
        index: 1-based chunk index (used as the ``id`` attribute).
        chunk: Dict with at least ``content`` and optionally ``source_file``,
               ``timestamp``, ``score``, ``log_level``.

    Returns:
        Formatted XML string for the chunk.
    """
    source = chunk.get("source_file", "unknown")
    timestamp = chunk.get("timestamp", "")
    score = chunk.get("score", 0.0)
    log_level = chunk.get("log_level", "")
    content = chunk.get("content", "").strip()

    return (
        f'<chunk id="{index}" source="{source}" timestamp="{timestamp}" '
        f'score="{score:.4f}" log_level="{log_level}">\n'
        f"{content}\n"
        f"</chunk>"
    )


def _assemble_prompt(chunks: list[dict], query: str) -> str:
    """
    Assemble the full prompt from *chunks* (already sorted) and *query*.

    Args:
        chunks: Chunk dicts sorted by score descending.
        query:  User query string.

    Returns:
        Fully assembled prompt string.
    """
    formatted_chunks = [_format_chunk(i + 1, c) for i, c in enumerate(chunks)]
    context_block = "<context>\n" + "\n".join(formatted_chunks) + "\n</context>"
    return SYSTEM_ROLE_PROMPT + "\n\n" + context_block + "\n\nUser Query: " + query


def build_prompt(
    query: str,
    chunks: list[dict],
    max_words: int = 2800,
) -> str:
    """
    Build a complete LLM prompt combining the system role, RAG context, and
    the user query.

    Chunks are sorted by ``score`` descending.  If the total word count
    exceeds *max_words* and more than 3 chunks remain, the lowest-scoring
    chunk is removed iteratively until the prompt fits or only 3 chunks
    remain.

    Args:
        query:     User query string.
        chunks:    List of RAG result dicts from :class:`~daemon.retriever.HybridRetriever`.
        max_words: Maximum permitted word count for the returned prompt.

    Returns:
        Fully assembled, word-count-compliant prompt string.
    """
    if not chunks:
        # No context — return minimal prompt
        return SYSTEM_ROLE_PROMPT + "\n\nUser Query: " + query

    # Sort by score descending (highest relevance first)
    sorted_chunks = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)

    prompt = _assemble_prompt(sorted_chunks, query)
    word_count = len(prompt.split())

    # Trim lowest-scoring chunks until within budget or only 3 remain
    while word_count > max_words and len(sorted_chunks) > 3:
        removed = sorted_chunks.pop()  # remove lowest-scoring (last element)
        logger.debug(
            f"build_prompt: trimmed chunk '{removed.get('chunk_id', '?')}' "
            f"(score={removed.get('score', 0):.4f}). "
            f"Remaining chunks: {len(sorted_chunks)}"
        )
        prompt = _assemble_prompt(sorted_chunks, query)
        word_count = len(prompt.split())

    logger.debug(
        f"build_prompt: final prompt has {word_count} words "
        f"using {len(sorted_chunks)} chunks"
    )
    return prompt
