from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.database import get_db
from services.risk_service import risk_engine

router = APIRouter()

class LiveRiskRequest(BaseModel):
    zone_id: str
    city: str
    transit_origin: str = "City Center"
    transit_destination: str = "Airport"

@router.post("/live-risk")
async def evaluate_live_risk(payload: LiveRiskRequest, db = Depends(get_db)):
    """
    Unified Risk Engine endpoint.
    Polls live OpenWeather, Google Maps, and News APIs simultaneously,
    computes a final risk score, updates the zone state in MongoDB,
    and automatically triggers payouts if RED/YELLOW.
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    result = await risk_engine.evaluate_live_risk(
        zone_id=payload.zone_id,
        city=payload.city,
        transit_origin=payload.transit_origin,
        transit_dest=payload.transit_destination,
        db=db
    )
    return result

@router.get("/zone-status")
async def get_zone_status(city: str = "Chennai"):
    """
    Returns the Unified Risk status for a given city.
    Combines Weather, Traffic, and NLP insights.
    """
    try:
        result = await risk_engine.get_unified_risk_for_city(city)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
