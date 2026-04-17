import logging
from datetime import datetime
from core.database import get_db
from core.mock_workers import get_worker_by_id
from core.event_bus import event_bus

logger = logging.getLogger(__name__)

# Constants (Emissions Factors)
EF_PETROL = 2.3  # kg CO2 / unit distance (assumed per liter equivalent)
EF_EV = 0.4      # kg CO2 / unit distance (assumed per kWh equivalent)
EF_BICYCLE = 0.0 # kg CO2 / unit distance

# Premium discount threshold for ESG
ESG_SCORE_THRESHOLD = 5.0 # Example threshold in kg of carbon saved
MAX_DISCOUNT = 0.10       # 10% premium discount

def calculate_esg_score(distance_km: float, vehicle_type: str) -> dict:
    """
    Calculates the ESG score based on distance driven and vehicle type.
    Rewards EV and bicycle users with carbon savings and potential premium discounts.
    """
    try:
        vehicle_type = vehicle_type.strip().lower()
        
        # Determine the current emission factor based on vehicle type
        if vehicle_type in ["ev", "electric", "electric scooter"]:
            ef_current = EF_EV
        elif vehicle_type in ["bicycle", "bike", "walking"]:
            ef_current = EF_BICYCLE
        else:
            # Assumes petrol by default for carbon baselining
            ef_current = EF_PETROL
            
        # Carbon savings calculation
        # formula: distance * (Baseline_Petrol - EF_current)
        carbon_saved = distance_km * (EF_PETROL - ef_current)
        
        # Ensure we don't have negative savings for non-standard inputs
        carbon_saved = max(0.0, carbon_saved)
        
        # Define the ESG score as the direct carbon saved metric
        esg_score = carbon_saved
        
        # Calculate discount
        discount_percentage = 0.0
        if esg_score > ESG_SCORE_THRESHOLD:
            discount_percentage = MAX_DISCOUNT
            
        return {
            "esg_score": round(esg_score, 2),
            "carbon_saved": round(carbon_saved, 2),
            "discount": round(discount_percentage, 2)
        }
        
    except Exception as e:
        logger.error(f"Error calculating ESG score: {e}")
        return {
            "esg_score": 0.0,
            "carbon_saved": 0.0,
            "discount": 0.0
        }

async def update_worker_esg_stats(worker_id: str, distance_km: float, vehicle_type: str) -> dict:
    """
    Atomic update for worker ESG stats.
    Increments total_carbon_saved, updates esg_discount, and logs the record.
    """
    db = get_db()
    if db is None:
        logger.warning("[ESG] Database not available for ESG update.")
        return {"success": False}

    # 1. Calculate trip score
    trip_data = calculate_esg_score(distance_km, vehicle_type)
    carbon_saved = trip_data["carbon_saved"]

    # 2. Persist trip record
    record = {
        "worker_id": worker_id,
        "distance_km": distance_km,
        "vehicle_type": vehicle_type,
        "carbon_saved": carbon_saved,
        "timestamp": datetime.utcnow().isoformat()
    }
    await db["esg_records"].insert_one(record)

    # 3. Update aggregate worker stats
    # We fetch current worker to decide badge/discount thresholds
    worker = await db["workers"].find_one({"worker_id": worker_id})
    if not worker:
        # Fallback to in-memory if not in DB yet (for simulation safety)
        worker = get_worker_by_id(worker_id)
        if not worker:
            return {"success": False, "reason": "Worker not found"}

    new_total = round(worker.get("total_carbon_saved", 0) + carbon_saved, 2)
    
    # Logic: >15kg = Green Elite (10% discount), >5kg = Silver (5% discount), else Bronze (0%)
    new_discount = 0.0
    badge = "Bronze"
    if new_total >= 15.0:
        new_discount = 0.10
        badge = "Green Elite"
    elif new_total >= 5.0:
        new_discount = 0.05
        badge = "Silver"

    update_fields = {
        "total_carbon_saved": new_total,
        "esg_discount": new_discount,
        "esg_badge": badge
    }

    await db["workers"].update_one(
        {"worker_id": worker_id},
        {"$set": update_fields}
    )

    # Update in-memory registry as well for consistency during same-session simulation
    worker.update(update_fields)

    # 4. Broadcast ESG event for real-time UI updates
    try:
        await event_bus.emit("esg_update", {
            "type": "esg_update",
            "data": {
                "worker_id": worker_id,
                "worker_name": worker.get("name", "Worker"),
                "carbon_saved": carbon_saved,
                "total_carbon_saved": new_total,
                "badge": badge,
                "discount": new_discount,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"[ESG] Failed to emit ESG update: {e}")

    logger.info(f"[ESG] Updated {worker_id}: +{carbon_saved}kg (Total: {new_total}kg, Badge: {badge})")

    
    return {
        "success": True,
        "trip_carbon_saved": carbon_saved,
        "total_carbon_saved": new_total,
        "discount": new_discount,
        "badge": badge
    }

