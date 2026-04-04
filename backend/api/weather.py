from fastapi import APIRouter, HTTPException, Query
from services.weather_service import weather_service
import requests

router = APIRouter()

@router.get("/weather-risk")
async def get_weather_risk(city: str = Query(..., description="City name to fetch live weather risk for")):
    """
    Fetches real-time rainfall and weather condition from OpenWeatherMap.
    
    Logic:
    - rain > 10mm → RED  (heavy rain detected)
    - rain 3–10mm → YELLOW  (moderate rain detected)
    - else      → GREEN
    """
    try:
        result = weather_service.get_weather_risk(city)
        return {
            "city": city,
            "rainfall": result.get("rainfall", 0),
            "zone": result.get("zone", result.get("status", "YELLOW")),
            "reason": result.get("reason", "Unknown")
        }
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 500
        if status == 404:
            raise HTTPException(status_code=404, detail=f"City '{city}' not found in OpenWeatherMap. Check spelling.")
        raise HTTPException(status_code=502, detail=f"OpenWeatherMap API error: HTTP {status}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error fetching weather: {str(e)}")
