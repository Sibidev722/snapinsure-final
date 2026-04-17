import asyncio
import os
import sys
from datetime import datetime

# Add the backend directory to sys.path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
env_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=env_path)

async def test_pricing_engine():
    print("\n--- Testing Zone Pricing Engine ---")
    try:
        from core.database import connect_to_mongo, get_db
        from services.zone_pricing_engine import zone_pricing_engine
        
        await connect_to_mongo()
        db = get_db()
        zone_id = "Z1"
        
        # 1. Clear existing mocks for a clean test
        await db.weather_state.delete_many({"city": "Chennai"})
        await db.real_events.delete_many({"zone_id": zone_id})
        
        # 2. Baseline Test (No Weather, No Events)
        print(f"\n[1] Testing Baseline for {zone_id}...")
        res_base = await zone_pricing_engine.compute_price(zone_id)
        print(f"Result: {res_base}")
        
        # 3. Weather Test
        print("\n[2] Injecting Heavy Rain Weather Impact...")
        await db.weather_state.insert_one({
            "city": "Chennai",
            "impact": {"demand_multiplier": 1.5, "risk_level": "RED"},
            "timestamp": datetime.utcnow().isoformat()
        })
        res_weather = await zone_pricing_engine.compute_price(zone_id)
        print(f"Result (with weather): {res_weather}")
        
        # 4. Strike Event Test
        print("\n[3] Injecting Active Strike Event in Zone...")
        await db.real_events.insert_one({
            "zone_id": zone_id,
            "type": "strike",
            "status": "active",
            "severity": "high",
            "confidence": 0.9
        })
        res_full = await zone_pricing_engine.compute_price(zone_id)
        print(f"Result (weather + strike): {res_full}")
        
        # Verify surge logic
        if res_full['surge'] > res_weather['surge'] > res_base['surge']:
            print("\n✅ SUCCESS: Pricing engine correctly compounding multipliers!")
        else:
            print("\n❌ FAILURE: Multipliers not compounding as expected.")
            
        print("\n--- Pricing Engine Test Completed ---")
        
    except Exception as e:
        print(f"\n[ERROR] Pricing test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pricing_engine())
