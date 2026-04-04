from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.database import get_db
from services.trigger_service import trigger_engine

router = APIRouter()

class WeatherTrigger(BaseModel):
    zone_id: str
    rain_intensity: float

class TrafficTrigger(BaseModel):
    zone_id: str
    delay_minutes: int

class StrikeTrigger(BaseModel):
    zone_id: str
    text_data: str

class RouteTrigger(BaseModel):
    source_zone: str
    target_zone: str

@router.post("/weather")
async def trigger_weather(request: WeatherTrigger, db = Depends(get_db)):
    try:
        result = await trigger_engine.process_weather(request.zone_id, request.rain_intensity, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/traffic")
async def trigger_traffic(request: TrafficTrigger, db = Depends(get_db)):
    try:
        result = await trigger_engine.process_traffic(request.zone_id, request.delay_minutes, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strike")
async def trigger_strike(request: StrikeTrigger, db = Depends(get_db)):
    try:
        result = await trigger_engine.process_strike(request.zone_id, request.text_data, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/route")
async def trigger_route(request: RouteTrigger, db = Depends(get_db)):
    try:
        result = await trigger_engine.process_route_block(request.source_zone, request.target_zone, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
