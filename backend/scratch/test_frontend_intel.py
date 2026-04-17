import asyncio
import os
import sys
from datetime import datetime

# Add the backend directory to sys.path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
env_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=env_path)

async def trigger_mock_intelligence():
    print("\n--- Triggering Mock Intelligence for Frontend Verification ---")
    try:
        from core.event_bus import event_bus
        
        # 1. Trigger NLP Strike Event
        print("[1] Emitting 'event_update' (NLP Strike)...")
        await event_bus.emit("event_update", {
            "type": "event_update",
            "data": {
                "title": "Delivery Worker Strike in T.Nagar",
                "source": "Local News Poller",
                "zone_id": "Z1",
                "lat": 13.0418,
                "lon": 80.2341,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        await asyncio.sleep(2)
        
        # 2. Trigger Weather Alert
        print("[2] Emitting 'weather_update'...")
        await event_bus.emit("weather_update", {
            "type": "weather_update",
            "data": {
                "city": "Chennai",
                "description": "Heavy Thunderstorm Warning",
                "risk": "RED",
                "timestamp": datetime.utcnow().isoformat()
            }
        })

        await asyncio.sleep(2)
        
        # 3. Trigger ESG Reward
        print("[3] Emitting 'esg_update'...")
        await event_bus.emit("esg_update", {
            "type": "esg_update",
            "data": {
                "worker_id": "ZOM-1002",
                "worker_name": "Priya Sharma",
                "carbon_saved": 4.5,
                "total_carbon_saved": 108.0,
                "badge": "Green Elite",
                "discount": 0.10,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print("\n✅ All mock intelligence signals emitted. Check the React Dashboard for:")
        print(" - Megaphone marker on Map (Z1)")
        print(" - Intelligence Log alerts (Strike & Weather)")
        print(" - ESG Card update (108.0 kg/CO2)")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to trigger mock intelligence: {e}")

if __name__ == "__main__":
    asyncio.run(trigger_mock_intelligence())
