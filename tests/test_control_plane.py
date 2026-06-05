"""
tests/test_control_plane.py — Unit tests for daemon/control_plane.py.

Tests cover:
  - Valid high-confidence intent → VALIDATED
  - Low confidence → PENDING_REVIEW
  - Boundary conditions at threshold (0.74 / 0.75)
  - Disallowed action type → REJECTED / DISALLOWED_ACTION_TYPE
  - None input → REJECTED / PARSE_ERROR
  - Each call creates exactly one new audit row in SQLite
  - Hash tamper detection: recomputed hash on modified data != stored hash
"""

import hashlib
import json
import os
import sqlite3
import sys
import pytest

# Path bootstrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from control_plane import DeterministicControlPlane  # noqa: E402
from intent_parser import AIIntent  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_intent(
    action: str = "suggest_renice",
    confidence: float = 0.91,
) -> AIIntent:
    """Create a valid AIIntent for use in control plane tests."""
    return AIIntent(
        action_type=action,
        target_resource="chrome",
        proposed_value="10",
        confidence_score=confidence,
        reasoning_summary="High memory usage detected in kern.log OOM events.",
    )


def make_cp(tmp_path) -> DeterministicControlPlane:
    """Return a fresh DeterministicControlPlane backed by a temp SQLite db."""
    db_path = str(tmp_path / "audit.db")
    return DeterministicControlPlane(db_path=db_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidatedIntents:
    """Tests for intents that should be VALIDATED."""

    def test_valid_high_confidence_validated(self, tmp_path) -> None:
        """Valid intent with confidence 0.91 must be VALIDATED with no rejection reason."""
        cp = make_cp(tmp_path)
        result = cp.validate_and_log(make_intent(confidence=0.91))

        assert result.status == "VALIDATED", (
            f"Expected status='VALIDATED', got {result.status!r}"
        )
        assert result.rejection_reason is None, (
            f"Expected rejection_reason=None for VALIDATED, got {result.rejection_reason!r}"
        )

    def test_boundary_at_threshold(self, tmp_path) -> None:
        """Confidence 0.75 (exactly at threshold) must be VALIDATED (inclusive boundary)."""
        cp = make_cp(tmp_path)
        result = cp.validate_and_log(make_intent(confidence=0.75))

        assert result.status == "VALIDATED", (
            f"Expected status='VALIDATED' at threshold=0.75, got {result.status!r}"
        )


class TestPendingReview:
    """Tests for intents that should be PENDING_REVIEW due to low confidence."""

    def test_low_confidence_pending_review(self, tmp_path) -> None:
        """Confidence 0.60 (< threshold) must produce PENDING_REVIEW status."""
        cp = make_cp(tmp_path)
        result = cp.validate_and_log(make_intent(confidence=0.60))

        assert result.status == "PENDING_REVIEW", (
            f"Expected status='PENDING_REVIEW', got {result.status!r}"
        )

    def test_boundary_below_threshold(self, tmp_path) -> None:
        """Confidence 0.74 (just below 0.75 threshold) must be PENDING_REVIEW."""
        cp = make_cp(tmp_path)
        result = cp.validate_and_log(make_intent(confidence=0.74))

        assert result.status == "PENDING_REVIEW", (
            f"Expected status='PENDING_REVIEW' for confidence=0.74, "
            f"got {result.status!r}"
        )


class TestRejectedIntents:
    """Tests for intents that should be REJECTED."""

    def test_disallowed_action_type(self, tmp_path) -> None:
        """action_type='rm_rf' must be REJECTED with reason 'DISALLOWED_ACTION_TYPE'."""
        cp = make_cp(tmp_path)
        result = cp.validate_and_log(make_intent(action="rm_rf", confidence=0.99))

        assert result.status == "REJECTED", (
            f"Expected status='REJECTED' for disallowed action, got {result.status!r}"
        )
        assert result.rejection_reason == "DISALLOWED_ACTION_TYPE", (
            f"Expected rejection_reason='DISALLOWED_ACTION_TYPE', "
            f"got {result.rejection_reason!r}"
        )

    def test_none_input_parse_error(self, tmp_path) -> None:
        """None input must be REJECTED with reason 'PARSE_ERROR'."""
        cp = make_cp(tmp_path)
        result = cp.validate_and_log(None)

        assert result.status == "REJECTED", (
            f"Expected status='REJECTED' for None input, got {result.status!r}"
        )
        assert result.rejection_reason == "PARSE_ERROR", (
            f"Expected rejection_reason='PARSE_ERROR', "
            f"got {result.rejection_reason!r}"
        )


class TestAuditLog:
    """Tests for SQLite audit logging correctness."""

    def test_each_validation_produces_one_row(self, tmp_path) -> None:
        """Three separate validate_and_log calls must produce exactly 3 audit rows."""
        cp = make_cp(tmp_path)

        cp.validate_and_log(make_intent(action="suggest_renice", confidence=0.91))
        cp.validate_and_log(make_intent(action="suggest_swap_adjust", confidence=0.60))
        cp.validate_and_log(None)

        res = cp.get_intents(page=1, limit=10)
        rows = res["intents"]
        assert len(rows) == 3, (
            f"Expected 3 audit rows after 3 validate_and_log calls, got {len(rows)}"
        )


class TestTamperDetection:
    """Tests for the SHA-256 hash tamper-detection mechanism."""

    def test_hash_tamper_detection(self, tmp_path) -> None:
        """Modifying the stored intent_json must cause hash mismatch on re-computation."""
        cp = make_cp(tmp_path)
        cp.validate_and_log(make_intent(confidence=0.91))

        res = cp.get_intents(page=1, limit=10)
        rows = res["intents"]
        assert len(rows) == 1, "Expected exactly one audit row."
        row = rows[0]

        stored_hash: str = row["record_hash"]

        # Simulate tampering: change action_type in the stored JSON
        original_json: str = row["intent_json"]
        tampered_json: str = original_json.replace("suggest_renice", "rm_rf")

        # Recompute hash using the tampered data
        tampered_hash: str = cp._compute_hash(
            row["created_at"],
            tampered_json,
            row["action_type"],
            str(row["confidence_score"]),
            row["validation_result"],
            str(row["rejection_reason"]),
        )

        assert tampered_hash != stored_hash, (
            "Tampered record hash must not equal stored hash — tamper detection failed."
        )
