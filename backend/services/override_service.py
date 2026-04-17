"""
Override Service — Human-in-the-Loop Decision Management
=========================================================
Allows authorised admins to override a FAIL decision produced by the
multi-agent adjudication pipeline.

Design principles
-----------------
• Pure business logic — no FastAPI, no HTTP, fully unit-testable.
• Immutable audit trail — original decision is NEVER mutated; overrides are
  written as a separate document linked by claim_id.
• Strict guard rails — only FAIL decisions can be overridden.
• Every override action (apply, reject invalid, query) is structured-logged.
• Async-first for MongoDB I/O; apply_override() is usable standalone or via
  the REST router.

Collections
-----------
  audit_trails    — existing claim adjudication records (read)
  claim_overrides — override records (write)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OverrideResult:
    """Structured result returned by apply_override()."""
    success:            bool
    claim_id:           str
    original_decision:  str
    overridden_decision: str
    admin_id:           str
    override_reason:    str
    timestamp:          str           # ISO-8601 UTC
    override_id:        Optional[str] = None   # MongoDB ObjectId (populated after persist)
    error:              Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Only decisions in this set are eligible for override.
_OVERRIDABLE_DECISIONS: frozenset[str] = frozenset({"FAIL", "REJECTED"})

# The decision that replaces a FAIL when an admin overrides it.
_OVERRIDE_TARGET_DECISION: str = "APPROVED_BY_OVERRIDE"

# Minimum reason length — prevents empty/vague override rationales.
_MIN_REASON_LENGTH: int = 10


# ─────────────────────────────────────────────────────────────────────────────
# Input validation
# ─────────────────────────────────────────────────────────────────────────────

def _validate_admin_input(admin_input: Dict[str, Any]) -> Optional[str]:
    """
    Validates the admin_input payload.

    Required fields
    ---------------
    admin_id      : str — non-empty identifier of the authorised admin
    override_reason : str — human justification, minimum 10 characters

    Returns an error string if invalid, or None if valid.
    """
    admin_id = str(admin_input.get("admin_id", "")).strip()
    reason   = str(admin_input.get("override_reason", "")).strip()

    if not admin_id:
        return "admin_id is required and must not be empty."

    if len(reason) < _MIN_REASON_LENGTH:
        return (
            f"override_reason must be at least {_MIN_REASON_LENGTH} characters. "
            f"Received: '{reason}'"
        )

    return None   # valid


# ─────────────────────────────────────────────────────────────────────────────
# Core function
# ─────────────────────────────────────────────────────────────────────────────

async def apply_override(
    *,
    claim_id:    str,
    decision:    Dict[str, Any],
    admin_input: Dict[str, Any],
    db: Any,
) -> OverrideResult:
    """
    Apply a human-in-the-loop override to a FAIL decision.

    Parameters
    ----------
    claim_id
        Unique identifier of the claim (matches audit_trails.claim_id or _id).
        Used to link the override record back to the original adjudication.

    decision
        The adjudication result dict from AdjudicatorAgent.evaluate().
        Must contain 'decision' or 'status' key with value 'FAIL'/'REJECTED'.

    admin_input
        Dict containing:
          admin_id        : str  — who is performing the override
          override_reason : str  — mandatory justification (min 10 chars)

    db
        AsyncIOMotorDatabase instance (from get_db()).

    Returns
    -------
    OverrideResult
        Structured result with success flag, full audit record, and any errors.

    Side effects
    ------------
    • Inserts one document into db['claim_overrides'].
    • Updates the 'override_status' field on the matching audit_trails doc.
    • Emits structured log lines at INFO (success) and WARNING (rejection).
    """
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    # ── 1. Extract decision label (handle both 'decision' and 'status' keys) ─
    original_decision: str = (
        decision.get("decision")
        or decision.get("status")
        or "UNKNOWN"
    ).upper()

    # ── 2. Guard: only FAIL decisions can be overridden ───────────────────────
    if original_decision not in _OVERRIDABLE_DECISIONS:
        msg = (
            f"Override denied for claim '{claim_id}': "
            f"decision '{original_decision}' is not eligible for override. "
            f"Only {sorted(_OVERRIDABLE_DECISIONS)} decisions can be overridden."
        )
        logger.warning(
            "[OVERRIDE] DENIED | claim_id=%s | decision=%s | admin=%s | reason=%s",
            claim_id, original_decision,
            admin_input.get("admin_id", "<unknown>"),
            msg,
        )
        return OverrideResult(
            success=False,
            claim_id=claim_id,
            original_decision=original_decision,
            overridden_decision=original_decision,  # unchanged
            admin_id=str(admin_input.get("admin_id", "")),
            override_reason=str(admin_input.get("override_reason", "")),
            timestamp=timestamp,
            error=msg,
        )

    # ── 3. Validate admin_input ───────────────────────────────────────────────
    validation_error = _validate_admin_input(admin_input)
    if validation_error:
        logger.warning(
            "[OVERRIDE] INVALID INPUT | claim_id=%s | error=%s",
            claim_id, validation_error,
        )
        return OverrideResult(
            success=False,
            claim_id=claim_id,
            original_decision=original_decision,
            overridden_decision=original_decision,
            admin_id=str(admin_input.get("admin_id", "")),
            override_reason=str(admin_input.get("override_reason", "")),
            timestamp=timestamp,
            error=validation_error,
        )

    admin_id        = str(admin_input["admin_id"]).strip()
    override_reason = str(admin_input["override_reason"]).strip()

    # ── 4. Build the immutable override audit record ──────────────────────────
    # This document is APPEND-ONLY — the original adjudication record is
    # never mutated.  The link is maintained via claim_id.
    override_record: Dict[str, Any] = {
        # ── Identity ──────────────────────────────────────────────────────────
        "record_type":          "human_override",
        "claim_id":             claim_id,

        # ── Override metadata ─────────────────────────────────────────────────
        "admin_id":             admin_id,
        "override_reason":      override_reason,
        "timestamp":            timestamp,

        # ── Decision trail ────────────────────────────────────────────────────
        "original_decision":    original_decision,
        "overridden_decision":  _OVERRIDE_TARGET_DECISION,

        # ── Snapshot of what was overridden ───────────────────────────────────
        # Stores the full adjudication result for replay / forensics.
        "adjudication_snapshot": {
            "final_score":    decision.get("final_score"),
            "decision":       decision.get("decision"),
            "status":         decision.get("status"),
            "confidence":     decision.get("confidence"),
            "gates":          decision.get("gates", {}),
            "combined_explanation": decision.get("combined_explanation", ""),
        },

        # ── System provenance ─────────────────────────────────────────────────
        "source":               "human_in_the_loop",
        "override_version":     "1.0",
    }

    # ── 5. Persist the override record ────────────────────────────────────────
    override_id: Optional[str] = None
    try:
        insert_result = await db["claim_overrides"].insert_one(override_record.copy())
        override_id = str(insert_result.inserted_id)

        # ── 6. Tag the original audit_trail document (non-blocking) ──────────
        # We do NOT replace the original — we annotate it with override metadata.
        await db["audit_trails"].update_one(
            {"claim_id": claim_id},
            {
                "$set": {
                    "override_applied":    True,
                    "override_id":         override_id,
                    "override_admin":      admin_id,
                    "override_timestamp":  timestamp,
                    "effective_decision":  _OVERRIDE_TARGET_DECISION,
                }
            },
        )

    except Exception as db_exc:
        logger.error(
            "[OVERRIDE] DB ERROR | claim_id=%s | error=%s",
            claim_id, db_exc, exc_info=True,
        )
        return OverrideResult(
            success=False,
            claim_id=claim_id,
            original_decision=original_decision,
            overridden_decision=original_decision,
            admin_id=admin_id,
            override_reason=override_reason,
            timestamp=timestamp,
            error=f"Database error: {db_exc}",
        )

    # ── 7. Structured audit log (machine-parseable) ───────────────────────────
    logger.info(
        "[OVERRIDE] APPLIED | "
        "claim_id=%s | "
        "admin=%s | "
        "original=%s | "
        "new=%s | "
        "override_id=%s | "
        "reason=%r",
        claim_id,
        admin_id,
        original_decision,
        _OVERRIDE_TARGET_DECISION,
        override_id,
        override_reason,
    )

    return OverrideResult(
        success=True,
        claim_id=claim_id,
        original_decision=original_decision,
        overridden_decision=_OVERRIDE_TARGET_DECISION,
        admin_id=admin_id,
        override_reason=override_reason,
        timestamp=timestamp,
        override_id=override_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Query helpers (used by the admin audit endpoint)
# ─────────────────────────────────────────────────────────────────────────────

async def get_overrides_for_claim(claim_id: str, db: Any) -> list:
    """Return all override records linked to a claim_id, newest first."""
    cursor  = db["claim_overrides"].find(
        {"claim_id": claim_id}
    ).sort("timestamp", -1)
    records = await cursor.to_list(length=50)
    for r in records:
        r["_id"] = str(r["_id"])
    return records


async def get_overrides_by_admin(admin_id: str, db: Any, limit: int = 100) -> list:
    """Return all overrides performed by a specific admin_id."""
    cursor  = db["claim_overrides"].find(
        {"admin_id": admin_id}
    ).sort("timestamp", -1)
    records = await cursor.to_list(length=limit)
    for r in records:
        r["_id"] = str(r["_id"])
    return records
