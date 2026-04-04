from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from models.models import Zone, ZoneState
from services.risk_service import risk_engine
from services.route_service import route_intel_engine
from core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[Zone])
async def get_zones(db = Depends(get_db)):
    cursor = db["zones"].find()
    zones = await cursor.to_list(length=100)
    return zones

@router.get("/graph", response_model=Dict[str, Any])
async def get_zone_graph():
    """Returns the city zone graph managed by NetworkX."""
    return route_intel_engine.get_city_graph_data()

from pydantic import BaseModel

class RiskUpdateRequest(BaseModel):
    zone_id: str
    risk_score: float

@router.post("/update-risk")
async def update_zone_risk(request: RiskUpdateRequest, db = Depends(get_db)):
    """
    Update a zone's risk score and automatically propagate risk to neighbors.
    Transitions states based on score thresholds (RED > 0.7 > YELLOW >= 0.4 > GREEN).
    """
    try:
        result = await risk_engine.update_risk_and_propagate(request.zone_id, request.risk_score, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
