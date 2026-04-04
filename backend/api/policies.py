from fastapi import APIRouter, Depends, HTTPException
from typing import List
from models.models import PolicyCreate, Policy, PricingRequest, PricingResponse
from services.pricing_service import pricing_engine
from core.database import get_db
import uuid

router = APIRouter()

@router.post("/pricing", response_model=PricingResponse)
async def get_policy_pricing(request: PricingRequest, db = Depends(get_db)):
    """Get dynamic pricing for route zones"""
    return await pricing_engine.calculate_premium(request, db)

@router.post("/", response_model=Policy)
async def purchase_policy(policy_in: PolicyCreate, db = Depends(get_db)):
    """Creates a new active policy for a user based on zones."""
    policy = Policy(**policy_in.dict())
    await db["policies"].insert_one(policy.dict(by_alias=True))
    return policy

@router.get("/{user_id}", response_model=List[Policy])
async def get_user_policies(user_id: str, db = Depends(get_db)):
    cursor = db["policies"].find({"user_id": user_id})
    policies = await cursor.to_list(length=100)
    return policies
