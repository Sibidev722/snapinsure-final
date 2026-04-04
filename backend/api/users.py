from fastapi import APIRouter, Depends, HTTPException
from models.models import UserCreate, User
from core.database import get_db

router = APIRouter()

from services.ml_pricing import ml_pricing_engine
from models.models import Policy
from datetime import datetime, timedelta

@router.post("/register")
async def register_user(user_in: UserCreate, db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
        
    # 1. Create DB User
    user = User(**user_in.dict())
    await db["users"].insert_one(user.dict(by_alias=True))
    
    # 2. Predict Initial ML Premium
    ml_result = await ml_pricing_engine.predict_premium(user.id, db)
    premium_value = ml_result["premium"]

    # 3. Auto-Create Intelligent Policy based on user inputs
    policy = Policy(
        user_id=user.id,
        route_zones=[],
        premium_paid=premium_value,
        coverage_amount=premium_value * 20, 
        avg_peak_income=user.avg_income * 1.5,
        avg_normal_income=user.avg_income * 1.0,
        working_hours=user.peak_hours + 6, 
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow() + timedelta(days=30)
    )
    
    await db["policies"].insert_one(policy.dict(by_alias=True))
    
    return {
        "user": user,
        "policy": policy,
        "pricing_explanation": ml_result["explanation"]
    }

@router.get("/{user_id}", response_model=User)
async def get_user(user_id: str, db = Depends(get_db)):
    user = await db["users"].find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
