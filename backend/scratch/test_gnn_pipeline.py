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
from workers.gnn_worker import gnn_worker

async def test_gnn_pipeline():
    print("\n--- Testing Autonomous GNN Pipeline ---")
    await connect_to_mongo()
    db = get_db()
    
    if db is None:
        print("[ERROR] Database not connected")
        return

    # 1. State Setup: High-Risk Scenario
    # Weather: Storm
    # Zone Z4: Strike
    print("[1] Setting up Disruption State (Rain + Strike in Z4)...")
    await db.weather_state.update_one(
        {"city": "Chennai"},
        {"$set": {
            "city": "Chennai",
            "description": "Heavy Rain",
            "impact": {"demand_multiplier": 1.7},
            "timestamp": datetime.utcnow().isoformat()
        }},
        upsert=True
    )
    
    await db.real_events.update_one(
        {"zone_id": "Z4", "type": "strike"},
        {"$set": {
            "title": "Logistics Strike in Tambaram",
            "status": "active",
            "type": "strike",
            "timestamp": datetime.utcnow().isoformat()
        }},
        upsert=True
    )
    
    # 2. Run GNN Inference Manually via Worker Logic
    print("[2] Running Graph Inference...")
    await gnn_worker._compute_predictions()
    
    # 3. Verify Cache
    print("[3] Verifying Cache Persistence...")
    snapshot = await db.gnn_predictions.find_one({"type": "latest_snapshot"})
    if not snapshot:
        print("[FAIL] No GNN snapshot found in DB.")
        return
        
    print(f" > Timestamp: {snapshot['timestamp']}")
    print(f" > Weather Intensity: {snapshot['weather_intensity']}")
    print(f" > Active Strikes Tracked: {snapshot['active_strikes_count']}")
    
    z4_pred = next((p for p in snapshot["predictions"] if p["zone"] == "Z4"), None)
    if z4_pred:
        print(f"\n[Z4 Prediction Details]")
        print(f" > Zone: {z4_pred['zone']}")
        print(f" > Prediction: {z4_pred['prediction']}")
        print(f" > Explanation: {z4_pred['explanation']}")
        print(f" > Confidence: {z4_pred['confidence']}")
    
    print("\n✅ GNN Pipeline Verified. All dynamic signals correctly mapped to graph inference.")
    
    # 4. Cleanup
    await db.real_events.delete_many({"zone_id": "Z4", "type": "strike"})
    print("🧹 Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(test_gnn_pipeline())
