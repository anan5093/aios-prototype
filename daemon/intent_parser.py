"""
daemon/intent_parser.py — Extracts and validates structured AI intents from LLM completions.

Attempts JSON extraction twice before giving up:
  Attempt 1: Regex extraction of JSON object containing 'action_type'
  Attempt 2: Strip markdown code fences and retry
"""

import json
import logging
import re
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, ValidationError


class AIIntent(BaseModel):
    """
    Pydantic v2 model representing a validated AI optimisation intent.

    Attributes:
        action_type:        One of the four permitted action strings.
        target_resource:    The specific process or system parameter to act on.
        proposed_value:     The concrete recommended value (e.g. ``'10'`` for renice).
        confidence_score:   Model's self-reported confidence in [0.0, 1.0].
        reasoning_summary:  1-2 sentence justification citing log evidence.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    action_type: str
    target_resource: str
    proposed_value: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str


class IntentParser:
    """
    Two-attempt parser that extracts and validates an :class:`AIIntent`
    from raw LLM completion text.

    Attempt 1: A ``re.DOTALL`` regex locates the first JSON object that
               contains ``"action_type"`` and tries to validate it.
    Attempt 2: Markdown code fences (`` ```json ... ``` `` or `` ``` ... ``` ``)
               are stripped and the parse is retried.
    If both attempts fail the parser logs a warning and returns ``None``.
    """

    # Matches the first JSON object containing "action_type" (greedy)
    JSON_PATTERN: re.Pattern[str] = re.compile(
        r'\{[^{}]*"action_type"[^{}]*\}', re.DOTALL
    )

    # Matches markdown code fences with optional language tag
    FENCE_PATTERN: re.Pattern[str] = re.compile(
        r"```(?:json)?\s*([\s\S]*?)```", re.DOTALL
    )

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.IntentParser")

    def parse(self, completion: str) -> Optional[AIIntent]:
        """
        Extract and validate an :class:`AIIntent` from *completion*.

        Args:
            completion: Raw text output from the language model.

        Returns:
            Validated :class:`AIIntent` instance, or ``None`` if extraction
            or validation fails after two attempts.
        """
        # Attempt 1: regex extraction
        intent = self._try_extract(completion)
        if intent is not None:
            return intent

        # Attempt 2: strip markdown fences, then retry
        fence_match = self.FENCE_PATTERN.search(completion)
        if fence_match:
            inner_text = fence_match.group(1).strip()
            intent = self._try_extract(inner_text)
            if intent is not None:
                return intent

        # Both attempts failed
        self._logger.warning(
            f"IntentParser: failed to extract a valid AIIntent. "
            f"Completion preview: {completion[:200]!r}"
        )
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_extract(self, text: str) -> Optional[AIIntent]:
        """
        Try to find, parse, and validate a JSON object in *text*.

        Args:
            text: String that may contain a JSON object with ``action_type``.

        Returns:
            Validated :class:`AIIntent`, or ``None`` on any error.
        """
        match = self.JSON_PATTERN.search(text)
        if not match:
            return None

        raw_json = match.group(0)
        try:
            data = json.loads(raw_json)
            intent = AIIntent(**data)
            self._logger.debug(
                f"Parsed intent: {intent.action_type} "
                f"(confidence={intent.confidence_score:.2f})"
            )
            return intent
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            self._logger.debug(
                f"_try_extract failed for '{raw_json[:120]}': {exc!r}"
            )
            return None
