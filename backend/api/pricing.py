from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.ml_pricing import ml_pricing_engine
from core.database import get_db

router = APIRouter()

class PremiumResponse(BaseModel):
    premium: float
    explanation: str

@router.get("/{user_id}", response_model=PremiumResponse)
async def get_dynamic_premium(user_id: str, db = Depends(get_db)):
    """Predicts a dynamic premium using the internal ML Regressor model."""
    try:
        result = await ml_pricing_engine.predict_premium(user_id, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
