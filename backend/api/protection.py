from fastapi import APIRouter, Depends, HTTPException
from core.database import get_db
from models.models import ZoneState
from typing import Dict, Any

router = APIRouter()

@router.get("/protection-summary/{user_id}", response_model=Dict[str, Any])
async def get_protection_summary(user_id: str, db = Depends(get_db)):
    """
    Returns a unified summary of protected income, payout history, and risk levels for a user.
    """
    # 1. Total Protected (sum of coverage_amount for all active policies)
    active_policies = await db["policies"].find({"user_id": user_id, "is_active": True}).to_list(length=100)
    total_protected = sum(p.get("coverage_amount", 0.0) for p in active_policies)

    # 2. Last Payout (most recent payout for the user)
    last_payout_record = await db["payouts"].find({"user_id": user_id}).sort("timestamp", -1).limit(1).to_list(length=1)
    last_payout = last_payout_record[0].get("amount", 0.0) if last_payout_record else 0.0

    # 3. Active Zone and Risk Level (from the most recent active policy)
    active_zone = "GREEN"
    risk_level = 0.0
    
    if active_policies:
        # Get the latest active policy
        latest_policy = active_policies[-1]
        route_zones = latest_policy.get("route_zones", [])
        
        if route_zones:
            # Fetch the high-risk zone from the route
            zone_cursor = db["zones"].find({"_id": {"$in": route_zones}}).sort("risk_score", -1).limit(1)
            high_risk_zone = await zone_cursor.to_list(length=1)
            
            if high_risk_zone:
                active_zone = high_risk_zone[0].get("state", "GREEN")
                risk_level = high_risk_zone[0].get("risk_score", 0.0)

    # 4. Total Disruptions and Average Payout
    all_payouts = await db["payouts"].find({"user_id": user_id}).to_list(length=1000)
    total_disruptions = len(all_payouts)
    avg_payout = sum(p.get("amount", 0.0) for p in all_payouts) / total_disruptions if total_disruptions > 0 else 0.0

    from datetime import datetime
    now_iso = datetime.utcnow().isoformat()
    
    return {
        "total_protected": total_protected,
        "last_payout": last_payout,
        "active_zone": active_zone,
        "risk_level": risk_level,
        "total_disruptions": total_disruptions,
        "avg_payout": round(avg_payout, 2),
        "confidence": "98%",
        "timestamp": now_iso,
        "last_updated": now_iso
    }
