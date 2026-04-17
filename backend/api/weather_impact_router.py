"""
Weather Impact Router
---------------------
POST /weather-impact          — Compute impact from a raw weather payload
GET  /weather-impact/{city}   — Fetch live weather for city + compute impact in one step
POST /weather-impact/custom   — Compute impact with a custom config override
"""

from fastapi import APIRouter, Path, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
import datetime

from core.database import get_db
from services.weather_service import weather_service
from services.weather_impact_engine import WeatherImpactEngine, WeatherImpactConfig, weather_impact_engine

router = APIRouter(prefix="/weather-impact", tags=["Weather Impact Engine"])


# ── Request / Response schemas ─────────────────────────────────────────────────

class WeatherInput(BaseModel):
    """Raw weather payload — matches the output of GET /weather"""
    city:        str    = Field("Chennai", description="City name")
    rain:        bool   = Field(False, description="Whether it is currently raining")
    intensity:   str    = Field("none", description="none | light | moderate | heavy")
    temperature: float  = Field(30.0, description="Temperature in °C")
    zone:        str    = Field("GREEN", description="City zone: GREEN | YELLOW | RED")
    risk_score:  float  = Field(0.1, description="Raw risk score 0.0 – 1.0")
    condition:   str    = Field("Clear", description="Human-readable weather condition")
    source:      str    = Field("manual", description="Data source label")

    class Config:
        json_schema_extra = {
            "example": {
                "city": "Chennai",
                "rain": True,
                "intensity": "moderate",
                "temperature": 30.2,
                "zone": "YELLOW",
                "risk_score": 0.6,
                "condition": "Rain (Light Rain)",
                "source": "openweathermap"
            }
        }


class ConfigOverride(BaseModel):
    """Optional config overrides — only supply what you want to change"""
    demand_none:                     Optional[float] = None
    demand_light:                    Optional[float] = None
    demand_moderate:                 Optional[float] = None
    demand_heavy:                    Optional[float] = None
    surge_none:                      Optional[float] = None
    surge_light:                     Optional[float] = None
    surge_moderate:                  Optional[float] = None
    surge_heavy:                     Optional[float] = None
    risk_low_max:                    Optional[float] = None
    risk_medium_max:                 Optional[float] = None
    risk_high_max:                   Optional[float] = None
    payout_threshold_risk_score:     Optional[float] = None
    temp_extreme_heat_threshold:     Optional[float] = None
    temp_extreme_cold_threshold:     Optional[float] = None
    temp_risk_boost:                 Optional[float] = None
    weight_intensity:                Optional[float] = None
    weight_temperature:              Optional[float] = None
    weight_zone:                     Optional[float] = None


class CustomImpactRequest(BaseModel):
    weather: WeatherInput
    config:  ConfigOverride = Field(default_factory=ConfigOverride)

    class Config:
        json_schema_extra = {
            "example": {
                "weather": {
                    "city": "Chennai",
                    "rain": True,
                    "intensity": "heavy",
                    "temperature": 28.0,
                    "zone": "RED",
                    "risk_score": 0.92,
                    "condition": "Thunderstorm",
                    "source": "openweathermap"
                },
                "config": {
                    "demand_heavy": 2.0,
                    "surge_heavy": 2.5,
                    "payout_threshold_risk_score": 0.5
                }
            }
        }


class ImpactResponse(BaseModel):
    demand_multiplier:  float
    surge_multiplier:   float
    risk_level:         str
    risk_score:         float
    payout_eligible:    bool
    recommended_action: str
    factors:            List[str]
    input_summary:      dict


# ── DB Helpers ─────────────────────────────────────────────────────────────────

async def _save_weather_state(db, city: str, result: dict):
    if db is None:
        return
        
    city_name = city.strip().title()
    
    # Check existing to archive
    existing = await db["weather_state"].find_one({"city": city_name})
    if existing:
        await db["weather_state_archive"].insert_one(existing)
        await db["weather_state"].delete_one({"_id": existing["_id"]})
        
    # Insert new
    doc = {
        "city": city_name,
        "rain": result["input_summary"]["rain"],
        "impact": {
            "demand_multiplier": result["demand_multiplier"],
            "risk_level": result["risk_level"]
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    await db["weather_state"].insert_one(doc)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ImpactResponse,
    summary="Compute Weather Impact from Payload",
    description=(
        "Accepts a raw weather payload and returns demand/surge multipliers, "
        "risk classification, and payout eligibility. "
        "Use GET `/weather?city=Chennai` first to fetch the weather payload."
    ),
)
async def compute_impact_from_payload(weather: WeatherInput, db = Depends(get_db)):
    result = weather_impact_engine.compute(weather.model_dump())
    await _save_weather_state(db, weather.city, result)
    return ImpactResponse(**result)


@router.get(
    "/{city}",
    response_model=ImpactResponse,
    summary="Live Weather → Impact (One-shot)",
    description=(
        "Fetches live weather for the given city, then immediately computes "
        "demand/surge multipliers and risk classification — all in a single call."
    ),
)
async def compute_impact_for_city(
    city: str = Path(..., description="City name e.g. Chennai, Mumbai, Delhi"),
    db = Depends(get_db)
):
    try:
        weather_data = await weather_service.get_weather(city)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Weather fetch failed: {str(e)}")

    result = weather_impact_engine.compute(weather_data)
    await _save_weather_state(db, city, result)
    return ImpactResponse(**result)


@router.post(
    "/custom",
    response_model=ImpactResponse,
    summary="Compute Impact with Custom Config",
    description=(
        "Compute weather impact with **custom multiplier overrides**. "
        "Only supply the config fields you want to override — the rest use defaults. "
        "Useful for A/B testing different pricing strategies."
    ),
)
async def compute_impact_custom(body: CustomImpactRequest, db = Depends(get_db)):
    # Build a config starting from defaults, then apply overrides
    base   = WeatherImpactConfig()
    patch  = body.config.model_dump(exclude_none=True)

    for field_name, value in patch.items():
        if hasattr(base, field_name):
            setattr(base, field_name, value)

    engine = WeatherImpactEngine(config=base)
    result = engine.compute(body.weather.model_dump())
    await _save_weather_state(db, body.weather.city, result)
    return ImpactResponse(**result)
