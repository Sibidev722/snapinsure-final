"""
AI Zone Advisor Router
----------------------
Lightweight rule-based zone advisor for gig workers.
No LLM required — uses live city graph data.

GET /ai/suggest?worker_id=ZOM-1001
"""

from fastapi import APIRouter, Query
from services.city_graph_service import city_graph
from services.simulation_service import _worker_positions  # noqa
from core.logger import logger

router = APIRouter(prefix="/ai", tags=["AI Zone Advisor"])


@router.get("/suggest")
async def suggest_zone(worker_id: str = Query(default="ZOM-1001")):
    """
    Returns the best zone for a gig worker to operate in based on
    live demand, risk score, and zone state.
    """
    zones = city_graph.get_all_zones()
    if not zones:
        return {"error": "City graph not initialised"}

    # Score each zone on multiple criteria
    scored = []
    for z in zones:
        state = z.get("state", "GREEN")
        risk = z.get("risk_score", 0.5)
        demand = z.get("demand_score", 0.5)
        orders = z.get("orders_per_minute", 100)
        baseline = z.get("baseline_orders", 200)
        pool = z.get("pool_balance", 0)
        contributors = z.get("pool_contributors", 0)

        # Zones that are RED or completely offline get penalised heavily
        state_penalty = 0.0 if state == "GREEN" else (0.4 if state == "YELLOW" else 1.0)

        # Composite score (higher = better for worker)
        # demand_score high = good, risk_score low = good
        composite = (demand * 0.5) + ((1 - risk) * 0.35) + (min(orders / max(baseline, 1), 1.0) * 0.15)
        composite -= state_penalty

        estimated_hourly = round(300 * demand * (1 - risk * 0.5), 0)

        scored.append({
            "zone_id": z["id"],
            "name": z.get("name", z["id"]),
            "state": state,
            "risk_score": risk,
            "demand_score": demand,
            "orders_per_minute": orders,
            "pool_balance": pool,
            "pool_contributors": contributors,
            "estimated_hourly_inr": estimated_hourly,
            "composite_score": round(composite, 3),
        })

    # Sort: highest composite = best recommendation
    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    best = scored[0]
    worst = scored[-1]

    # Avoid
    avoid_zones = [z for z in scored if z["state"] == "RED"]

    # Build human-readable reason
    if best["state"] == "GREEN":
        risk_label = "Low" if best["risk_score"] < 0.35 else "Moderate"
        reason = (
            f"Highest demand ({best['orders_per_minute']} orders/min) with {risk_label} risk. "
            f"Pool active with {best['pool_contributors']} contributors."
        )
    else:
        reason = "All zones disrupted — wait near shelter. System fallback active."

    return {
        "recommended": {
            "zone_id": best["zone_id"],
            "name": best["name"],
            "state": best["state"],
            "estimated_hourly_inr": best["estimated_hourly_inr"],
            "demand_score": best["demand_score"],
            "risk_level": "Low" if best["risk_score"] < 0.35 else ("Moderate" if best["risk_score"] < 0.65 else "High"),
            "reason": reason,
            "pool_active": best["pool_contributors"] >= 5,
        },
        "avoid": [
            {
                "zone_id": z["zone_id"],
                "name": z["name"],
                "reason": f"Zone is {z['state']} — Risk {z['risk_score']:.0%}"
            }
            for z in avoid_zones[:3]
        ],
        "all_zones_ranked": scored,
    }


@router.get("/zone-health")
async def zone_health():
    """Returns a quick health summary of all zones for the debug panel."""
    zones = city_graph.get_all_zones()
    return {
        "zones": [
            {
                "id": z["id"],
                "name": z.get("name", z["id"]),
                "state": z.get("state", "GREEN"),
                "risk_score": z.get("risk_score", 0),
                "demand_score": z.get("demand_score", 1),
                "orders_per_minute": z.get("orders_per_minute", 0),
                "collapse_reason": z.get("collapse_reason"),
                "pool_balance": z.get("pool_balance", 0),
                "pool_contributors": z.get("pool_contributors", 0),
            }
            for z in zones
        ],
        "summary": city_graph.get_analytics(),
    }
