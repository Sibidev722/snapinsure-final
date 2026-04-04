from fastapi import APIRouter, Depends, HTTPException
from typing import List
from models.models import Payout, ZoneState
from core.database import get_db
from pydantic import BaseModel, Field
from services.payout_service import payout_engine
from datetime import datetime

router = APIRouter()

class AutoPayoutRequest(BaseModel):
    user_id: str
    zone: ZoneState
    time_loss: float

class AutoPayoutResponse(BaseModel):
    payout: float
    status: str
    reason: str
    confidence: str = "100%"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

@router.post("/auto-payout", response_model=AutoPayoutResponse)
async def create_auto_payout(request: AutoPayoutRequest, db = Depends(get_db)):
    """
    Automatically calculate and trigger a zero-claim payout for a user.
    Strictly automated — no manual claims.
    """
    try:
        result = await payout_engine.calculate_automated_payout(
            request.user_id, request.zone, request.time_loss, db
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{user_id}", response_model=List[Payout])
async def get_user_payouts(user_id: str, db = Depends(get_db)):
    """Returns all automated payouts generated for the user."""
    cursor = db["payouts"].find({"user_id": user_id})
    payouts = await cursor.to_list(length=100)
    return payouts
