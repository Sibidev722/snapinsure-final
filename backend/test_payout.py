import asyncio
import sys
from services.simulation_service import manual_trigger, get_current_state, set_worker_shift, MOCK_WORKERS, _worker_positions, city_graph
from services.unified_payout_engine import payout_engine

async def main():
    print("Testing shift assignment...")
    wid = MOCK_WORKERS[0]["worker_id"]
    set_worker_shift(wid, "evening")

    print(f"Triggering 'traffic'...")
    # Force a position into RED natively
    _worker_positions[wid] = {"lat": 13.0, "lon": 80.2, "zone_id": "Z1", "heading": 0, "speed": 10}
    city_graph._zones["Z1"]["state"] = "RED"
    city_graph._zones["Z1"]["delay_factor"] = 4.0
    
    await manual_trigger("traffic")
    
    state = get_current_state()
    payouts = state.get("analytics", {}).get("recent_payouts", [])
    
    if payouts:
        print(f"SUCCESS. Payouts generated: {len(payouts)}")
        for p in payouts:
            print(p)
    else:
        print("FAIL. No payouts generated. Let's see history directly:")
        print(payout_engine.payout_history)

if __name__ == "__main__":
    asyncio.run(main())
