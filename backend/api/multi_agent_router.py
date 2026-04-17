from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.database import get_db
from services.multi_agent_service import TelemetristAgent, EconomistAgent, AdjudicatorAgent
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/multi-agent", tags=["Multi-Agent System"])

class AdjudicateRequest(BaseModel):
    worker_id: str
    worker_lat: float
    worker_lon: float
    center_lat: float
    center_lon: float
    payout_request: float

@router.post("/adjudicate")
async def adjudicate_claim(request: AdjudicateRequest, db = Depends(get_db)):
    """
    Evaluates a payout request using the Multi-Agent System.
    """
    try:
        # Agent 1: Telemetrist
        tele_result = TelemetristAgent.evaluate(
            worker_lat=request.worker_lat,
            worker_lon=request.worker_lon,
            center_lat=request.center_lat,
            center_lon=request.center_lon
        )
        
        # Agent 2: Economist
        eco_result = await EconomistAgent.evaluate(
            worker_id=request.worker_id,
            payout_request=request.payout_request,
            db=db
        )
        
        # Agent 3: Adjudicator
        adj_result = AdjudicatorAgent.evaluate(
            telemetrist_result=tele_result,
            economist_result=eco_result
        )

        # JSON audit trail format
        audit_trail = {
            "worker_id": request.worker_id,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            "decision": "APPROVED" if adj_result["status"] == "PASS" else "REJECTED",
            "agents": [
                tele_result,
                eco_result,
                adj_result
            ],
            "final_confidence": adj_result["confidence"]
        }
        
        # Store in MongoDB
        await db["audit_trails"].insert_one(audit_trail.copy())
        
        # Strip ObjectId for valid json response
        if "_id" in audit_trail:
            audit_trail["_id"] = str(audit_trail["_id"])

        return {
            "success": True,
            "decision": audit_trail["decision"],
            "reason": adj_result["reason"],
            "audit_trail": audit_trail
        }

    except Exception as e:
        logger.error(f"Error in multi-agent adjudication: {e}")
        raise HTTPException(status_code=500, detail="Internal server error in multi-agent engine")

@router.get("/audit/{worker_id}")
async def get_audit_trail(worker_id: str, db = Depends(get_db)):
    """
    Retrieve human-readable audit trails for a specific worker.
    """
    try:
        cursor = db["audit_trails"].find({"worker_id": worker_id}).sort("timestamp", -1)
        trails = await cursor.to_list(length=100)
        
        if not trails:
            return {"success": True, "worker_id": worker_id, "audits": [], "message": "No audit trails found."}
            
        for trail in trails:
            trail["_id"] = str(trail["_id"])
            
        return {
            "success": True,
            "worker_id": worker_id,
            "audits": trails
        }
    except Exception as e:
        logger.error(f"Error fetching audit trail for {worker_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch audit trails")
