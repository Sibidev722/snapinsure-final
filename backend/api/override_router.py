"""
Override Router — Human-in-the-Loop REST API
=============================================
Exposes three endpoints:

  POST /override/apply
    Apply an admin override to a FAIL adjudication decision.

  GET  /override/claim/{claim_id}
    Retrieve all override records for a specific claim.

  GET  /override/admin/{admin_id}
    Retrieve all overrides performed by a specific admin.
"""

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional
from core.database import get_db
from services.override_service import (
    apply_override,
    get_overrides_for_claim,
    get_overrides_by_admin,
    _MIN_REASON_LENGTH,
)
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/override", tags=["Human Override"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class OverrideRequest(BaseModel):
    """
    Payload for POST /override/apply.

    claim_id
        The ID of the claim that received a FAIL decision.
        Must match an existing record in audit_trails.

    decision
        The full adjudication result dict (from AdjudicatorAgent).
        Must contain at least 'decision' or 'status' key.

    admin_id
        Non-empty string identifying the authorised admin.

    override_reason
        Mandatory human justification — minimum 10 characters.
        Forces reviewers to write a meaningful rationale.
    """
    claim_id:        str = Field(..., min_length=1,   description="Claim identifier")
    decision:        dict = Field(...,                 description="Full AdjudicatorAgent result")
    admin_id:        str = Field(..., min_length=1,   description="Admin user identifier")
    override_reason: str = Field(..., min_length=_MIN_REASON_LENGTH,
                                 description=f"Override justification (min {_MIN_REASON_LENGTH} chars)")

    @field_validator("override_reason")
    @classmethod
    def reason_not_trivial(cls, v: str) -> str:
        """Reject single-word or all-caps 'reasons' that carry no information."""
        stripped = v.strip()
        if stripped.lower() in {"ok", "yes", "pass", "override", "approve"}:
            raise ValueError(
                "override_reason must be a meaningful justification, "
                f"not a single-word acknowledgement like '{stripped}'."
            )
        return stripped


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/apply",
    summary="Apply admin override to a FAIL decision",
    status_code=http_status.HTTP_200_OK,
)
async def override_apply(request: OverrideRequest, db: Any = Depends(get_db)):
    """
    **Human-in-the-Loop Override**

    Allows an authorised admin to reverse a FAIL adjudication decision.

    Rules enforced by the service layer:
    - Only FAIL / REJECTED decisions are eligible.
    - `admin_id` must be non-empty.
    - `override_reason` must be at least 10 non-trivial characters.
    - The original decision is **never mutated** — an immutable override record
      is appended to `claim_overrides` and the `audit_trail` is annotated.

    Returns the full override record on success.
    Returns HTTP 422 on validation failure (Pydantic).
    Returns HTTP 403 if the decision is not eligible for override.
    Returns HTTP 500 on unexpected DB errors.
    """
    result = await apply_override(
        claim_id=request.claim_id,
        decision=request.decision,
        admin_input={
            "admin_id":        request.admin_id,
            "override_reason": request.override_reason,
        },
        db=db,
    )

    if not result.success:
        # Distinguish between authorisation failures and unexpected errors
        if "not eligible" in (result.error or ""):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail=result.error,
            )
        if "Database error" in (result.error or ""):
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error,
            )
        # Validation / input error
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.error,
        )

    logger.info(
        "[OVERRIDE API] claim=%s admin=%s override_id=%s",
        result.claim_id, result.admin_id, result.override_id,
    )

    return {
        "success":              True,
        "override_id":          result.override_id,
        "claim_id":             result.claim_id,
        "original_decision":    result.original_decision,
        "overridden_decision":  result.overridden_decision,
        "admin_id":             result.admin_id,
        "override_reason":      result.override_reason,
        "timestamp":            result.timestamp,
        "message": (
            f"Claim '{result.claim_id}' override applied. "
            f"Decision changed from {result.original_decision} "
            f"to {result.overridden_decision}."
        ),
    }


@router.get(
    "/claim/{claim_id}",
    summary="Fetch all overrides for a claim",
)
async def get_claim_overrides(claim_id: str, db: Any = Depends(get_db)):
    """
    Returns all human override records linked to `claim_id`, newest first.
    Useful for auditors reviewing a specific claim's correction history.
    """
    records = await get_overrides_for_claim(claim_id, db)
    return {
        "success":   True,
        "claim_id":  claim_id,
        "total":     len(records),
        "overrides": records,
    }


@router.get(
    "/admin/{admin_id}",
    summary="Fetch all overrides performed by an admin",
)
async def get_admin_overrides(
    admin_id: str,
    limit: int = 100,
    db: Any = Depends(get_db),
):
    """
    Returns all override records performed by `admin_id`, newest first.
    Useful for monitoring admin activity and detecting policy violations.
    """
    records = await get_overrides_by_admin(admin_id, db, limit=min(limit, 500))
    return {
        "success":   True,
        "admin_id":  admin_id,
        "total":     len(records),
        "overrides": records,
    }


@router.get(
    "/all",
    summary="Fetch the global audit log of all overrides",
)
async def get_all_overrides(limit: int = 100, db: Any = Depends(get_db)):
    """
    Returns the global queue of all overrides. 
    Used by the Admin Override Panel to render the historical audit table.
    """
    cursor = db["claim_overrides"].find({}).sort("timestamp", -1)
    records = await cursor.to_list(length=min(limit, 500))
    for r in records:
        r["_id"] = str(r["_id"])
    return {
        "success": True,
        "total": len(records),
        "overrides": records
    }
