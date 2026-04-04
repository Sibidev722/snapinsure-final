import asyncio
import sys
import os

# Add backend to sys path
sys.path.append('c:/Users/Sibi/SnapInsure/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from core.config import settings
from services.auth_service import seed_verified_workers, login_worker, get_fraud_logs
from fastapi import HTTPException

async def test():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    
    # ensure db drops previous workers to get clean state
    await db["verified_workers"].delete_many({})
    await db["active_sessions"].delete_many({})
    await db["fraud_logs"].delete_many({})

    # Seed
    await seed_verified_workers(db)

    print("--- Test 1: Valid User Login ---")
    try:
        res = await login_worker("9876543210", "Swiggy", "Chennai", "SWG123", db, "127.0.0.1")
        print("Success!", res["user"])
    except Exception as e:
        print("Failed:", e)

    print("\n--- Test 2: Fake User ---")
    try:
        res = await login_worker("1111111111", "Swiggy", "Chennai", None, db, "127.0.0.1")
        print("Unexpected success", res)
    except HTTPException as e:
        print("Expected Failure:", e.detail)

    print("\n--- Test 3: City Mismatch ---")
    try:
        res = await login_worker("9876543211", "Zomato", "Chennai", "ZOM123", db, "127.0.0.1")
        print("Unexpected success", res)
    except HTTPException as e:
        print("Expected Failure:", e.detail)

    print("\n--- Test 4: Multiple Logins (Location jump) ---")
    try:
        # User already logged into Chennai (Test 1), now trying Bangalore
        res = await login_worker("9876543210", "Swiggy", "Bangalore", "SWG123", db, "127.0.0.1")
        print("Unexpected success", res)
    except HTTPException as e:
        print("Expected Failure:", e.detail)

    print("\n--- Fraud Logs ---")
    logs = await get_fraud_logs(db)
    for log in logs:
        print(f"[{log['timestamp']}] {log['phone']}: {log['reason']}")

    client.close()

if __name__ == "__main__":
    asyncio.run(test())
