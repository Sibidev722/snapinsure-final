from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.database import get_db
from services.route_service import route_intel_engine

router = APIRouter()

class RouteCheckRequest(BaseModel):
    source_zone: str
    destination_zone: str

class RouteCheckResponse(BaseModel):
    status: str
    time_loss: Optional[int] = None

@router.post("/route-check", response_model=RouteCheckResponse)
async def check_route(request: RouteCheckRequest, db = Depends(get_db)):
    """
    Check if a safe route exists avoiding actively RED zones.
    Returns GREEN if the optimal path has no impediments.
    Returns YELLOW with time loss if rerouted around a RED zone.
    Returns RED if delivery is completely blocked.
    """
    try:
        result = await route_intel_engine.check_delivery_route(
            request.source_zone, request.destination_zone, db
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
