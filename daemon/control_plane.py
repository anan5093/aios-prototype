"""
daemon/control_plane.py — Deterministic Control Plane for AI intent validation.

All AI intents must pass this gate before any action is taken.
Every intent (including rejected ones) is written to an append-only SQLite audit log
with a SHA-256 tamper-evident record hash.

Validation chain (fail-fast):
  1. Null check          → REJECTED (PARSE_ERROR)
  2. Allowlist check     → REJECTED (DISALLOWED_ACTION_TYPE)
  3. Confidence gate     → PENDING_REVIEW (if < 0.75)
  4. All pass            → VALIDATED
"""

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from intent_parser import AIIntent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERMITTED_ACTIONS: frozenset[str] = frozenset(
    {
        "suggest_renice",
        "suggest_swap_adjust",
        "suggest_log_rotate",
        "suggest_cgroup_limit",
    }
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS aios_audit (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TEXT    NOT NULL,
    intent_json       TEXT    NOT NULL,
    action_type       TEXT    NOT NULL,
    confidence_score  REAL    NOT NULL,
    validation_result TEXT    NOT NULL,
    rejection_reason  TEXT,
    execution_status  TEXT    NOT NULL DEFAULT 'PENDING',
    approved_by       TEXT,
    approved_at       TEXT,
    record_hash       TEXT    NOT NULL
)
"""


# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Outcome of :meth:`DeterministicControlPlane.validate_and_log`."""

    status: str
    intent_id: int
    rejection_reason: Optional[str] = field(default=None)


# ---------------------------------------------------------------------------
# Control Plane
# ---------------------------------------------------------------------------


class DeterministicControlPlane:
    """
    Gate that validates every :class:`~intent_parser.AIIntent` before action
    and maintains an append-only, tamper-evident SQLite audit log.

    Validation is fail-fast in this order:
    1. Null check -> REJECTED (PARSE_ERROR)
    2. Allowlist check -> REJECTED (DISALLOWED_ACTION_TYPE)
    3. Confidence gate -> PENDING_REVIEW (confidence < threshold)
    4. All pass -> VALIDATED

    Every row is protected by a SHA-256 hash of its key fields so that
    tampering with the database can be detected.
    """

    CONFIDENCE_THRESHOLD: float = 0.75

    def __init__(self, db_path: str = "data/aios_audit.db") -> None:
        """
        Initialise the control plane and ensure the audit table exists.

        Args:
            db_path: File-system path to the SQLite database.  Parent
                     directories are created automatically.
        """
        self._db_path = db_path
        self._logger = logging.getLogger(f"{__name__}.DeterministicControlPlane")

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn: sqlite3.Connection = sqlite3.connect(
            db_path, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()

        self._logger.info(
            f"Control plane initialised with SQLite audit at {db_path}"
        )

    # ------------------------------------------------------------------
    # Validation & Logging
    # ------------------------------------------------------------------

    def validate_and_log(self, intent: Optional[AIIntent]) -> ValidationResult:
        """
        Run the validation chain for *intent* and append one row to the audit
        table regardless of outcome.

        Args:
            intent: Parsed :class:`~intent_parser.AIIntent`, or ``None`` if
                    parsing failed.

        Returns:
            :class:`ValidationResult` with the decision and the new row ID.
        """
        created_at = datetime.now(tz=timezone.utc).isoformat()

        # Step 1 — Null check
        if intent is None:
            action_type = "UNKNOWN"
            confidence = 0.0
            intent_json = "{}"
            status = "REJECTED"
            reason: Optional[str] = "PARSE_ERROR"
        else:
            action_type = intent.action_type
            confidence = intent.confidence_score
            intent_json = intent.model_dump_json()
            reason = None

            # Step 2 — Allowlist check
            if action_type not in PERMITTED_ACTIONS:
                status = "REJECTED"
                reason = "DISALLOWED_ACTION_TYPE"
            # Step 3 — Confidence gate
            elif confidence < self.CONFIDENCE_THRESHOLD:
                status = "PENDING_REVIEW"
            # Step 4 — All pass
            else:
                status = "VALIDATED"

        record_hash = self._compute_hash(
            created_at,
            intent_json,
            action_type,
            str(confidence),
            status,
            str(reason),
        )

        cursor = self._conn.execute(
            """
            INSERT INTO aios_audit
                (created_at, intent_json, action_type, confidence_score,
                 validation_result, rejection_reason, record_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                intent_json,
                action_type,
                confidence,
                status,
                reason,
                record_hash,
            ),
        )
        self._conn.commit()
        row_id: int = cursor.lastrowid or 0

        self._logger.info(
            f"validate_and_log: id={row_id} action={action_type} "
            f"confidence={confidence:.2f} status={status} reason={reason}"
        )
        return ValidationResult(status=status, intent_id=row_id, rejection_reason=reason)

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------

    def approve_intent(self, intent_id: int, approved_by: str) -> bool:
        """
        Approve a previously VALIDATED intent for (simulated) execution.

        The row is updated to SIMULATED_EXECUTED and a
        data/simulation_state.json file is written so the frontend can
        reflect the last executed intent.

        Args:
            intent_id:   Primary-key of the audit row to approve.
            approved_by: Identifier of the human approver.

        Returns:
            True on success, False if the row is not found, not in
            PENDING execution status, or not VALIDATED.
        """
        row = self._conn.execute(
            "SELECT * FROM aios_audit WHERE id = ?", (intent_id,)
        ).fetchone()

        if row is None:
            self._logger.warning(f"approve_intent: intent_id={intent_id} not found")
            return False

        if row["execution_status"] != "PENDING" or row["validation_result"] != "VALIDATED":
            self._logger.warning(
                f"approve_intent: intent_id={intent_id} is not PENDING+VALIDATED "
                f"(execution_status={row['execution_status']}, "
                f"validation_result={row['validation_result']})"
            )
            return False

        approved_at = datetime.now(tz=timezone.utc).isoformat()
        self._conn.execute(
            """
            UPDATE aios_audit
               SET execution_status = 'SIMULATED_EXECUTED',
                   approved_by      = ?,
                   approved_at      = ?
             WHERE id = ?
            """,
            (approved_by, approved_at, intent_id),
        )
        self._conn.commit()

        # Parse intent for the simulation-state file
        try:
            intent_data: dict = json.loads(row["intent_json"])
        except (json.JSONDecodeError, TypeError):
            intent_data = {}

        simulation_state = {
            "last_executed": {
                "intent_id": intent_id,
                "action_type": intent_data.get("action_type", row["action_type"]),
                "target_resource": intent_data.get("target_resource", ""),
                "proposed_value": intent_data.get("proposed_value", ""),
                "approved_by": approved_by,
                "approved_at": approved_at,
            }
        }

        sim_path = Path("data/simulation_state.json")
        sim_path.parent.mkdir(parents=True, exist_ok=True)
        sim_path.write_text(json.dumps(simulation_state, indent=2))

        self._logger.info(
            f"approve_intent: intent_id={intent_id} approved by '{approved_by}' "
            f"-> SIMULATED_EXECUTED"
        )
        return True

    # ------------------------------------------------------------------
    # Read / list
    # ------------------------------------------------------------------

    def get_intents(self, page: int = 1, limit: int = 20) -> dict:
        """
        Paginate audit-log entries, newest first.

        Args:
            page:  1-based page number.
            limit: Maximum rows per page.

        Returns:
            Dict with total (int), page (int), and intents (list of row dicts).
        """
        offset = (page - 1) * limit
        total: int = self._conn.execute(
            "SELECT COUNT(*) FROM aios_audit"
        ).fetchone()[0]

        rows = self._conn.execute(
            "SELECT * FROM aios_audit ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

        return {
            "total": total,
            "page": page,
            "intents": [dict(row) for row in rows],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_hash(self, *fields: str) -> str:
        """
        Compute a SHA-256 digest over the concatenation of *fields*.

        Args:
            *fields: Arbitrary strings to hash together.

        Returns:
            64-character lowercase hex digest.
        """
        return hashlib.sha256("".join(fields).encode()).hexdigest()
