import asyncio
import sys
import os

# Add the backend directory to the path so we can import services
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.risk_service import risk_engine

async def test_unified_risk():
    print("Testing Unified Risk Engine for Chennai...")
    try:
        # We can't easily mock the external APIs here without a lot of setup,
        # but we can check if the method exists and runs (it will use fallbacks if keys are missing)
        result = await risk_engine.get_unified_risk_for_city("Chennai")
        print("Result:", result)
        
        # Validate structure
        assert "zone" in result
        assert "risk_score" in result
        assert "factors" in result
        assert "confidence" in result
        assert "timestamp" in result
        assert "last_updated" in result
        assert isinstance(result["factors"], list)
        assert "%" in result["confidence"]
        
        print("Success: Unified Risk Engine returned valid structure.")
    except Exception as e:
        print("Error during test:", e)

if __name__ == "__main__":
    asyncio.run(test_unified_risk())
