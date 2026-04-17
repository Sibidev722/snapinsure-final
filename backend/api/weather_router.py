"""
Weather Router
--------------
GET /weather               — Live weather (default: Chennai, or ?city=...)
GET /weather/debug/cache   — Inspect per-city cache state (must come BEFORE /{city})
GET /weather/{city}        — Live weather for any city by path param

All responses are cached 5 minutes per city.
Dual-source: OpenWeatherMap (if key set) → Open-Meteo free fallback.
"""

import time
from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import BaseModel
from services.weather_service import weather_service

router = APIRouter(prefix="/weather", tags=["Live Weather"])


# ── Response schema ────────────────────────────────────────────────────────────

class WeatherResponse(BaseModel):
    city:              str
    rain:              bool
    intensity:         str    # "none" | "light" | "moderate" | "heavy"
    temperature:       float  # °C
    condition:         str    # human-readable label
    zone:              str    # "GREEN" | "YELLOW" | "RED"
    risk_score:        float  # 0.0 – 1.0
    confidence:        int    # %
    rainfall_mm:       float
    source:            str    # "openweathermap" | "open-meteo" | "fallback"
    cache_ttl_seconds: int


# ── Helper ─────────────────────────────────────────────────────────────────────

async def _fetch_and_wrap(city: str) -> WeatherResponse:
    try:
        data = await weather_service.get_weather(city)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Weather service unavailable: {str(e)}")

    # Defensive defaults in case any field is missing from the service
    return WeatherResponse(
        city              = city.strip().title(),
        rain              = data.get("rain", False),
        intensity         = data.get("intensity", "none"),
        temperature       = data.get("temperature", 30.0),
        condition         = data.get("condition", "Unknown"),
        zone              = data.get("zone", "YELLOW"),
        risk_score        = data.get("risk_score", 0.5),
        confidence        = data.get("confidence", 50),
        rainfall_mm       = data.get("rainfall_mm", 0.0),
        source            = data.get("source", "unknown"),
        cache_ttl_seconds = 300,
    )


# ── Routes (ORDER MATTERS — specific before parameterized) ────────────────────

@router.get(
    "",
    response_model=WeatherResponse,
    summary="Live Weather — Query by City",
    description=(
        "Fetches real-time weather data. Uses **OpenWeatherMap** if `OPENWEATHER_API_KEY` "
        "is configured, otherwise falls back to **Open-Meteo** (free, no key needed). "
        "Responses are cached **5 minutes** per city to avoid rate limits.\n\n"
        "**Example response:**\n"
        "```json\n"
        "{\n"
        "  \"city\": \"Chennai\",\n"
        "  \"rain\": true,\n"
        "  \"intensity\": \"moderate\",\n"
        "  \"temperature\": 30.2,\n"
        "  \"condition\": \"Rain (Light Rain)\",\n"
        "  \"zone\": \"YELLOW\",\n"
        "  \"risk_score\": 0.6,\n"
        "  \"confidence\": 85,\n"
        "  \"rainfall_mm\": 3.4,\n"
        "  \"source\": \"openweathermap\",\n"
        "  \"cache_ttl_seconds\": 300\n"
        "}\n"
        "```"
    ),
)
async def get_weather_default(
    city: str = Query(default="Chennai", description="City name (default: Chennai)"),
):
    return await _fetch_and_wrap(city)


@router.get(
    "/debug/cache",
    summary="Inspect Weather Cache",
    description="Returns the internal per-city cache state for debugging. Shows age, TTL remaining, and summary data.",
)
async def inspect_cache():
    """Shows all cities currently stored in the 5-minute in-memory cache."""
    now = time.time()
    entries = {}
    for city_key, entry in weather_service._cache.items():
        age = int(now - entry["ts"])
        entries[city_key] = {
            "age_seconds":    age,
            "ttl_remaining":  max(0, weather_service.CACHE_TTL - age),
            "is_fresh":       age < weather_service.CACHE_TTL,
            "source":         entry["data"].get("source"),
            "zone":           entry["data"].get("zone"),
            "temperature_c":  entry["data"].get("temperature"),
            "rain":           entry["data"].get("rain"),
            "intensity":      entry["data"].get("intensity"),
            "condition":      entry["data"].get("condition"),
        }
    return {
        "cached_cities":    len(entries),
        "cache_ttl_seconds": weather_service.CACHE_TTL,
        "cities":           entries,
    }


@router.get(
    "/{city}",
    response_model=WeatherResponse,
    summary="Live Weather — Path City",
    description=(
        "Fetch live weather for any city by path parameter. "
        "Same dual-source strategy and 5-minute per-city cache as the query-param endpoint."
    ),
)
async def get_weather_for_city(
    city: str = Path(..., description="City name e.g. Chennai, Mumbai, Delhi, Bangalore"),
):
    return await _fetch_and_wrap(city)
