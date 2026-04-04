from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from services.route_risk_service import get_route_risk

router = APIRouter()


class RouteRiskRequest(BaseModel):
    source_lat: float = Field(..., example=12.9716, description="Source latitude")
    source_lng: float = Field(..., example=77.5946, description="Source longitude")
    destination_lat: float = Field(..., example=13.0827, description="Destination latitude")
    destination_lng: float = Field(..., example=80.2707, description="Destination longitude")


class RouteRiskResponse(BaseModel):
    status: str = Field(..., description="GREEN | YELLOW | RED")
    duration: Optional[float] = Field(None, description="Actual travel time in minutes (with traffic)")
    time_loss: Optional[float] = Field(None, description="Extra delay vs free-flow baseline, in minutes")
    reason: str = Field(..., description="Human-readable explanation")


@router.post(
    "/route-risk",
    response_model=RouteRiskResponse,
    tags=["Route Risk (Mapbox)"],
    summary="Analyse route risk between two coordinates",
    description=(
        "Calls the Mapbox Directions API to compute real-world travel time "
        "(with live traffic) vs the free-flow baseline and classifies the route as:\n\n"
        "- **GREEN** — route exists, delay ≤ 10 minutes\n"
        "- **YELLOW** — route exists, delay > 10 minutes (traffic congestion)\n"
        "- **RED** — no route found or API failure"
    )
)
async def analyse_route_risk(request: RouteRiskRequest) -> RouteRiskResponse:
    """
    POST /route-risk

    Inputs: source & destination coordinates (lat/lng)
    Output: { status, duration, time_loss, reason }
    """
    try:
        result = await get_route_risk(
            src_lng=request.source_lng,
            src_lat=request.source_lat,
            dst_lng=request.destination_lng,
            dst_lat=request.destination_lat,
        )
        return RouteRiskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route risk analysis failed: {str(e)}")
