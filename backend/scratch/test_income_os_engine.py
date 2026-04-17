import asyncio
import os
import sys
from datetime import datetime

# Add the backend directory to sys.path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
env_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=env_path)

from core.database import connect_to_mongo, get_db
from services.income_os_decision_engine import income_os_decision_engine

async def test_decision_logic():
    print("\n--- Testing Income OS Decision Engine Logic ---")
    await connect_to_mongo()
    db = get_db()
    
    if db is None:
        print("[ERROR] Database not connected")
        return

    # Scenario 1: Quiet Zone (Low Demand, No Surge, Low Risk)
    # Demand 0.5 + Surge 1.0 - Risk 0.1 = 1.4 (Threshold 2.2) -> MOVE
    worker_id = "TEST-1001"
    zone_id = "Z5" 
    
    print(f"\n[Test 1] Regular Day (Zone {zone_id}):")
    result = await income_os_decision_engine.generate_decision(worker_id, zone_id)
    print(f" > Score: {result['score']}")
    print(f" > Decision: {result['decision']}")
    print(f" > Reason: {result['reason']}")
    
    # Scenario 2: Intelligence-Driven Opportunity (High Surge)
    # We'll simulate a strike in Zone 1 to boost surge
    print(f"\n[Test 2] Strike Detection in Zone Z1:")
    # Insert mock strike
    await db.real_events.update_one(
        {"zone_id": "Z1", "type": "strike"},
        {"$set": {
            "title": "Delivery Hunger Strike",
            "status": "active",
            "type": "strike",
            "lat": 13.0418,
            "lon": 80.2341,
            "timestamp": datetime.utcnow().isoformat()
        }},
        upsert=True
    )
    
    # Recalculate decision for worker in Z1
    # Demand ~0.7 + Surge ~1.8 (event) - Risk 0.1 = ~2.4 -> STAY
    result = await income_os_decision_engine.generate_decision(worker_id, "Z1")
    print(f" > Score: {result['score']}")
    print(f" > Decision: {result['decision']}")
    print(f" > Reason: {result['reason']}")
    
    # Scenario 3: Weather Disruption
    # Mock weather
    await db.weather_state.update_one(
        {"city": "Chennai"},
        {"$set": {
            "city": "Chennai",
            "description": "Heavy Rain & Floods",
            "risk": "RED",
            "impact": {"demand_multiplier": 1.5},
            "timestamp": datetime.utcnow().isoformat()
        }},
        upsert=True
    )
    
    print(f"\n[Test 3] Weather + Strike in Zone Z1:")
    result = await income_os_decision_engine.generate_decision(worker_id, "Z1")
    print(f" > Score: {result['score']}")
    print(f" > Decision: {result['decision']}")
    print(f" > Reason: {result['reason']}")
    
    # Verify DB storage
    await db.income_os_decisions.update_one(
        {"worker_id": worker_id},
        {"$set": result},
        upsert=True
    )
    print("\n✅ Verification data persisted to 'income_os_decisions'")
    
    # Clean up
    await db.real_events.delete_many({"zone_id": "Z1", "type": "strike"})
    print("🧹 Cleaned up test events.")

if __name__ == "__main__":
    asyncio.run(test_decision_logic())
