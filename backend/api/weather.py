from fastapi import APIRouter, HTTPException, Query
from services.weather_service import weather_service

router = APIRouter()

@router.get("/weather-risk", summary="Legacy Weather Risk Endpoint")
async def get_weather_risk(city: str = Query(default="Chennai", description="City name to fetch live weather risk for")):
    """
    Legacy endpoint — returns rainfall zone risk (GREEN / YELLOW / RED).
    For the full weather payload use GET /weather?city=Chennai instead.
    """
    try:
        result = await weather_service.get_weather(city)
        return {
            "city": city,
            "rainfall": result.get("rainfall_mm", 0),
            "rain": result.get("rain", False),
            "intensity": result.get("intensity", "none"),
            "zone": result.get("zone", "YELLOW"),
            "reason": result.get("condition", "Unknown"),
            "risk_score": result.get("risk_score", 0.5),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather service error: {str(e)}")
