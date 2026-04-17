from fastapi import APIRouter
from services.zone_pricing_engine import zone_pricing_engine

router = APIRouter()

@router.get("/price")
async def get_zone_price(zone_id: str):
    """
    Returns the real-time dynamic gig-worker pricing for a specific zone.
    It combines internal zone demand, external weather risk, and active NLP events
    to securely compute a final baseline surge factor.
    """
    result = await zone_pricing_engine.compute_price(zone_id)
    return result
