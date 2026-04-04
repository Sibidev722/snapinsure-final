import asyncio
import sys
import os

# Add the backend directory to the path so we can import services
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.payout_service import payout_engine
from models.models import ZoneState

# Mock DB
class MockDB:
    def __getitem__(self, name):
        return self
    async def insert_one(self, data):
        print(f"Mock DB: Inserted payout record: {data}")
        return None

async def test_payout_logic():
    db = MockDB()
    
    print("--- Testing RED Zone Payout ---")
    red_result = await payout_engine.calculate_automated_payout("U123", ZoneState.RED, 5.0, db)
    print("RED Result:", red_result)
    assert red_result["payout"] == 230.0
    
    print("\n--- Testing YELLOW Zone Payout ---")
    yellow_result = await payout_engine.calculate_automated_payout("U123", ZoneState.YELLOW, 2.5, db)
    print("YELLOW Result:", yellow_result)
    assert yellow_result["payout"] == 50.0 # 20.0 * 2.5
    
    print("\n--- Testing GREEN Zone Payout ---")
    green_result = await payout_engine.calculate_automated_payout("U123", ZoneState.GREEN, 10.0, db)
    print("GREEN Result:", green_result)
    assert green_result["payout"] == 0.0
    
    print("\nSuccess: Payout logic verified.")

if __name__ == "__main__":
    asyncio.run(test_payout_logic())
