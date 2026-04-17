from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.database import get_db
from services.esg_service import calculate_esg_score, update_worker_esg_stats
from core.mock_workers import get_worker_by_id
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/esg", tags=["ESG Engine"])


class ESGRequest(BaseModel):
    worker_id: str
    distance_km: float
    vehicle_type: str   # "petrol" | "ev" | "bicycle"


@router.post("/score")
async def get_esg_score(request: ESGRequest, db=Depends(get_db)):
    """
    Calculate and persist an ESG score for a worker trip.
    Returns carbon saved, ESG score, and applicable premium discount.
    """
    try:
        result = calculate_esg_score(request.distance_km, request.vehicle_type)

        record = {
            "worker_id": request.worker_id,
            "distance_km": request.distance_km,
            "vehicle_type": request.vehicle_type,
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
        await db["esg_records"].insert_one(record.copy())
        if "_id" in record:
            record["_id"] = str(record["_id"])

        badge = "Bronze"
        if result["esg_score"] >= 15:
            badge = "Green Elite"
        elif result["esg_score"] >= 5:
            badge = "Silver"

        return {
            "success": True,
            "worker_id": request.worker_id,
            "badge": badge,
            "low_risk_unlocked": result["esg_score"] >= 15,
            **result,
        }

    except Exception as e:
        logger.error(f"ESG score error: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute ESG score")


@router.get("/history/{worker_id}")
async def get_esg_history(worker_id: str, db=Depends(get_db)):
    """
    Retrieve the ESG trip history for a worker (most recent 50 records).
    """
    try:
        cursor = db["esg_records"].find({"worker_id": worker_id}).sort("timestamp", -1)
        records = await cursor.to_list(length=50)
        for r in records:
            r["_id"] = str(r["_id"])

        total_carbon = round(sum(r.get("carbon_saved", 0) for r in records), 2)
        return {
            "success": True,
            "worker_id": worker_id,
            "total_carbon_saved_kg": total_carbon,
            "records": records,
        }
    except Exception as e:
        logger.error(f"ESG history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch ESG history")


@router.get("/{worker_id}")
async def get_worker_esg_summary(worker_id: str, db=Depends(get_db)):
    """
    Get current summarized ESG stats for a worker.
    """
    try:
        worker = await db["workers"].find_one({"worker_id": worker_id})
        if not worker:
            # Fallback to in-memory during simulation startup
            worker = get_worker_by_id(worker_id)
            if not worker:
                raise HTTPException(status_code=404, detail="Worker not found")

        return {
            "success": True,
            "worker_id": worker_id,
            "name": worker.get("name"),
            "vehicle_type": worker.get("vehicle_type", "petrol"),
            "total_carbon_saved_kg": worker.get("total_carbon_saved", 0.0),
            "esg_discount": worker.get("esg_discount", 0.0),
            "esg_badge": worker.get("esg_badge", "Bronze"),
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ESG summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch ESG summary")


@router.post("/update")
async def manual_esg_update(request: ESGRequest, db=Depends(get_db)):
    """
    Manually trigger an ESG update for a worker trip.
    """
    try:
        result = await update_worker_esg_stats(request.worker_id, request.distance_km, request.vehicle_type)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("reason", "Update failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual ESG update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update ESG stats")

