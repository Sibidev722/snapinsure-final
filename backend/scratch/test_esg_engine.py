import asyncio
import os
import sys

# Add the backend directory to sys.path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
env_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=env_path)

async def test_esg_engine():
    print("\n--- Testing ESG Engine & Persistence ---")
    try:
        from core.database import connect_to_mongo, get_db
        from services.esg_service import update_worker_esg_stats
        
        await connect_to_mongo()
        db = get_db()
        
        # Test worker
        worker_id = "ZOM-1002" # Priya Sharma (EV user)
        
        print(f"\n[1] Initial State for {worker_id}...")
        worker = await db.workers.find_one({"worker_id": worker_id})
        if not worker:
            print("Worker not found in DB. Seeding...")
            from core.mock_workers import get_worker_by_id
            worker = get_worker_by_id(worker_id)
            await db.workers.insert_one(worker)
            
        print(f"Total Carbon: {worker.get('total_carbon_saved', 0)}kg, Discount: {worker.get('esg_discount', 0)*100}%")

        # 2. Simulate 5 trips
        print("\n[2] Simulating 5 EV trips (10km each)...")
        for i in range(5):
            res = await update_worker_esg_stats(worker_id, 10.0, "ev")
            print(f"  Trip {i+1}: +{res['trip_carbon_saved']}kg (New Total: {res['total_carbon_saved']}kg, Badge: {res['badge']})")

        # 3. Final Verification
        final_worker = await db.workers.find_one({"worker_id": worker_id})
        print(f"\n[3] Final Aggregate State:")
        print(f"Total Carbon Saved: {final_worker['total_carbon_saved']}kg")
        print(f"Current Discount: {final_worker['esg_discount']*100}%")
        print(f"Badge: {final_worker['esg_badge']}")
        
        if final_worker['total_carbon_saved'] > worker.get('total_carbon_saved', 0):
             print("\n✅ SUCCESS: ESG engine correctly accumulating and persisting environmental rewards!")
        else:
             print("\n❌ FAILURE: ESG stats not persisting.")
        
        print("\n--- ESG Engine Test Completed ---")
        
    except Exception as e:
        print(f"\n[ERROR] ESG test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_esg_engine())
