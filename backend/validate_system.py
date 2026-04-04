import asyncio
import httpx
import time
import json

API_URL = "http://localhost:8000"
headers = {"Authorization": "Bearer TEST_TOKEN"}

async def test_pipeline():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚦 SNAPINSURE END-TO-END VALIDATION")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    async with httpx.AsyncClient() as client:
        # 1. Check State
        print("\n[1] Checking System State...")
        try:
            r = await client.get(f"{API_URL}/sim/state", timeout=2.0)
            state = r.json()
            print("  ✔ State fetched successfully")
            workers = state.get("workers", [])
            print(f"  ✔ Workers active: {len(workers)}")
        except Exception as e:
            print(f"  ❌ State fetch failed: {e}")
            return
            
        # 2. Trigger Event
        print("\n[2] Triggering Rain Simulation...")
        try:
            r = await client.post(f"{API_URL}/sim/trigger", json={"event_type": "rain"}, timeout=2.0)
            print(f"  ✔ Trigger command sent (Status: {r.status_code})")
        except Exception as e:
            print(f"  ❌ Trigger failed: {e}")
            return
            
        # 3. Wait for processing
        print("  ⏳ Waiting for pipelines (Risk -> Orchestrator -> Payout)...")
        await asyncio.sleep(2)
        
        # 4. Check Payouts
        print("\n[3] Checking Payout Engine Results...")
        try:
            r = await client.get(f"{API_URL}/sim/payouts", timeout=2.0)
            payouts = r.json().get("payouts", [])
            if payouts:
                p = payouts[0]
                print(f"  ✔ Payout generated: ₹{p.get('amount')} for {p.get('worker_id')}")
                print(f"  ✔ Reason: {p.get('reason')} - {p.get('calculation_details')}")
                print(f"  ✔ Pool Used: {p.get('pool_used')}")
            else:
                print("  ❌ No payout generated.")
        except Exception as e:
            print(f"  ❌ Payout check failed: {e}")
            
if __name__ == "__main__":
    asyncio.run(test_pipeline())
