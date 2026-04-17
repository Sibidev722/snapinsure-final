"""
POST /evaluate-claim
────────────────────
The master autonomous claim evaluation endpoint.
Runs the full Multi-Agent pipeline in parallel:
  1. TelemetristAgent  – GPS spoofing detection
  2. EconomistAgent    – Income anomaly detection
  3. AdjudicatorAgent  – Final approval gate

Stores a complete XAI audit trail in MongoDB.
Returns a human-readable, demo-friendly JSON response.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any
from core.database import get_db
from services.multi_agent_service import TelemetristAgent, EconomistAgent, AdjudicatorAgent, EnvironmentAgent
from services.esg_service import calculate_esg_score
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Claim Evaluation"])


class ClaimRequest(BaseModel):
    worker_id: str
    worker_lat: float
    worker_lon: float
    center_lat: float
    center_lon: float
    payout_request: float = Field(..., gt=0, description="Requested payout amount in INR")
    distance_km: Optional[float] = 0.0
    vehicle_type: Optional[str] = "petrol"


@router.post("/evaluate-claim")
async def evaluate_claim(request: ClaimRequest, db=Depends(get_db)):
    """
    🚀 Master Autonomous Claim Evaluation Pipeline

    Runs 3 AI agents in parallel and returns a complete, explainable decision.
    Every result is persisted to MongoDB for full audit transparency.
    """
    start_time = datetime.utcnow()

    try:
        # ── Agent 1: Telemetrist (GPS spoofing check) ────────────────────────
        tele_result = TelemetristAgent.evaluate(
            request.worker_lat, request.worker_lon,
            request.center_lat, request.center_lon,
        )

        # ── Agent 2: Economist (earnings anomaly check) ──────────────────────
        eco_result = await EconomistAgent.evaluate(
            request.worker_id, request.payout_request, db
        )

        # ── Agent 3: Environment (GNN × Telemetrist fusion) ──────────────────
        # Fetch the latest GNN risk score for the worker's zone from MongoDB.
        # Falls back to 0.0 if no GNN snapshot exists yet (e.g. cold-start).
        gnn_risk_score: float = 0.0
        try:
            worker_doc = await db["workers"].find_one(
                {"worker_id": request.worker_id},
                {"zone_id": 1},
            )
            if worker_doc:
                zone_id = worker_doc.get("zone_id", "")
                gnn_snapshot = await db["gnn_predictions"].find_one(
                    {"type": "latest_snapshot"}
                )
                if gnn_snapshot:
                    for pred in gnn_snapshot.get("predictions", []):
                        if pred.get("zone") == zone_id:
                            # Use calibrated HIGH-class probability as the risk scalar
                            class_probs = pred.get("class_probs") or {}
                            gnn_risk_score = float(
                                class_probs.get("HIGH", pred.get("confidence", 0.0))
                            )
                            break
        except Exception as gnn_exc:
            logger.warning(f"[CLAIM] GNN risk lookup failed: {gnn_exc} — defaulting to 0.0")

        env_result = EnvironmentAgent.evaluate(
            gnn_risk_score=gnn_risk_score,
            telemetrist_result=tele_result,
        )

        # ── Agent 4: Adjudicator (three-way consensus gate) ──────────────────
        adj_result = AdjudicatorAgent.evaluate(tele_result, eco_result, env_result)

        # ── ESG bonus calculation ────────────────────────────────────────────
        esg = calculate_esg_score(request.distance_km or 0.0, request.vehicle_type or "petrol")
        badge = "Bronze"
        if esg["esg_score"] >= 15:
            badge = "Green Elite"
        elif esg["esg_score"] >= 5:
            badge = "Silver"

        # ── Compute processing latency ───────────────────────────────────────
        latency_ms = round((datetime.utcnow() - start_time).total_seconds() * 1000, 1)

        decision = "APPROVED" if adj_result["status"] == "PASS" else (
            "ESCALATED" if adj_result["status"] == "ESCALATE" else "REJECTED"
        )

        # ── XAI Audit Trail ──────────────────────────────────────────────────
        audit_trail = {
            "worker_id":        request.worker_id,
            "timestamp":        start_time.isoformat(),
            "decision":         decision,
            "payout_request":   request.payout_request,
            "agents": [
                tele_result,
                eco_result,
                env_result,
                adj_result,
            ],
            "environment": {
                "gnn_risk_input":        round(gnn_risk_score, 4),
                "risk_score":            env_result["environment_risk_score"],
                "regime":               env_result["regime"],
                "mismatch_detected":    env_result["debug"].get("mismatch", False),
            },
            "final_confidence": round(adj_result["confidence"], 4),
            "esg": {
                "badge":        badge,
                "carbon_saved": esg["carbon_saved"],
                "discount":     esg["discount"],
            },
            "latency_ms": latency_ms,
        }

        await db["audit_trails"].insert_one(audit_trail.copy())

        # ── Human-Readable Explanation ───────────────────────────────────────
        agent_summaries = []
        for agent in [tele_result, eco_result, env_result, adj_result]:
            icon = "✅" if agent.get("status") == "PASS" else "❌"
            reason_text = agent.get("reason") or agent.get("explanation") or "Decision logged."
            agent_summaries.append(f"{icon} {agent.get('agent', 'UnknownAgent')}: {reason_text}")

        explanation = "\n".join(agent_summaries)

        logger.info(f"[CLAIM] {request.worker_id} → {decision} ({latency_ms}ms)")

        return {
            "success":          True,
            "worker_id":        request.worker_id,
            "decision":         decision,
            "explanation":      explanation,
            "final_confidence": audit_trail["final_confidence"],
            "latency_ms":       latency_ms,
            "esg_badge":        badge,
            "carbon_saved_kg":  esg["carbon_saved"],
            "premium_discount": f"{int(esg['discount'] * 100)}%",
            "audit_trail":      audit_trail,
        }

    except Exception as e:
        logger.error(f"[CLAIM ERROR] {request.worker_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Claim evaluation failed: {str(e)}")


@router.get("/evaluate-claim/rejected")
async def get_rejected_claims(limit: int = 50, db: Any = Depends(get_db)):
    """
    Fetches the queue of recent claim traces that resulted in a FAIL or REJECTED
    decision and have NOT YET been overridden. Used by the Back-Office Admin Panel.
    """
    try:
        # Fetch audit trails that failed and are not overridden
        cursor = db["audit_trails"].find({
            "decision": {"$in": ["FAIL", "REJECTED", "ESCALATED"]},
            "override_applied": {"$ne": True}
        }).sort("timestamp", -1).limit(limit)
        
        fails = await cursor.to_list(length=limit)
        
        for f in fails:
            f["_id"] = str(f["_id"])
            # Ensure claim_id exists for the UI override function
            if "claim_id" not in f:
                f["claim_id"] = f["worker_id"] + "-" + str(f["_id"])[-4:]
                
        return {
            "success": True,
            "count": len(fails),
            "queue": fails
        }
    except Exception as e:
        logger.error(f"[QUEUE ERROR] fetching rejected claims: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch rejection queue")


@router.get("/audit/{worker_id}")
async def get_audit(worker_id: str, db=Depends(get_db)):
    """
    Retrieve all XAI audit records for a worker.
    Returns human-readable agent reasoning for every past claim.
    """
    cursor = db["audit_trails"].find({"worker_id": worker_id}).sort("timestamp", -1)
    records = await cursor.to_list(length=50)
    for r in records:
        r["_id"] = str(r["_id"])
    return {
        "success":    True,
        "worker_id":  worker_id,
        "total":      len(records),
        "audits":     records,
    }
