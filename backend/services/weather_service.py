import httpx
from core.logger import logger
from datetime import datetime

class WeatherService:
    # Open-Meteo public API requires no key
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
    
    @classmethod
    async def get_weather_risk(cls, city: str = "Chennai", lat: float = None, lon: float = None) -> dict:
        """
        Fetches live weather from Open-Meteo and translates it into a risk multiplier.
        Uses precise coordinates if provided, else falls back to city center.
        """
        try:
            # Step 1: Geocode if no lat/lon provided
            if lat is None or lon is None:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    geo_resp = await client.get(cls.GEOCODE_URL, params={"name": city, "count": 1, "language": "en"})
                    geo_resp.raise_for_status()
                    geo_data = geo_resp.json()
                    
                    if not geo_data.get("results"):
                        return {"rainfall": 0, "zone": "YELLOW", "reason": "City coordinates not found; safe YELLOW applied.", "risk_score": 0.5, "confidence": 50}
                    
                    lat = geo_data["results"][0]["latitude"]
                    lon = geo_data["results"][0]["longitude"]

            # Step 2: Fetch current weather & precipitation
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": ["precipitation", "weather_code"]
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(cls.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
            
            current = data.get("current", {})
            rain_1h = current.get("precipitation", 0.0)
            w_code = current.get("weather_code", 0)

            # WMO Weather interpretation codes
            severe_codes = [95, 96, 99] # Thunderstorm
            moderate_codes = [61, 63, 65, 80, 81, 82, 71, 73, 75] # Rain & Snow
            
            if rain_1h > 10.0 or w_code in severe_codes:
                 return {"rainfall": rain_1h, "zone": "RED",    "reason": f"Severe weather code {w_code} or heavy rain ({rain_1h}mm)", "risk_score": 0.98, "confidence": 92}
            elif rain_1h >= 2.0 or w_code in moderate_codes:
                 return {"rainfall": rain_1h, "zone": "YELLOW", "reason": f"Moderate weather code {w_code} or rain ({rain_1h}mm)", "risk_score": 0.55, "confidence": 85}
            else:
                 return {"rainfall": rain_1h, "zone": "GREEN",  "reason": "Clear skies measured by public radar", "risk_score": 0.1, "confidence": 95}
        
        except httpx.HTTPError as e:
            logger.error(f"Weather API HTTP error for '{city}': {str(e)}")
            return {"rainfall": 0, "zone": "YELLOW", "reason": "Weather API offline; cautious YELLOW applied.", "risk_score": 0.5, "confidence": 40}
        except Exception as e:
            logger.error(f"Weather API unexpected error: {str(e)}")
            return {"rainfall": 0, "zone": "YELLOW", "reason": "Weather API error; cautious YELLOW applied.",   "risk_score": 0.5, "confidence": 40}

weather_service = WeatherService()
