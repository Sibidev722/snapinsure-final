"""
Income OS Router
----------------
REST endpoints for the AI-Powered Income Operating System.

Routes:
  GET  /income-os/forecast/{worker_id}   — Income forecast (1h + shift)
  GET  /income-os/scenario/{worker_id}   — Stay vs. move comparison
  GET  /income-os/suggestion/{worker_id} — AI action recommendation
  GET  /income-os/zones/ranked           — All zones ranked by composite score
  POST /income-os/guarantee              — Enable guaranteed income mode
  DELETE /income-os/guarantee/{worker_id} — Disable guarantee mode
  GET  /income-os/guarantee/{worker_id}  — Guarantee status
  GET  /income-os/snapshot/{worker_id}   — Full Income OS snapshot
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.income_os_service import income_os
from services.simulation_service import _worker_positions
from core.logger import logger

router = APIRouter(prefix="/income-os", tags=["Income OS"])


# ── Request schemas ───────────────────────────────────────────────────────────

class GuaranteeRequest(BaseModel):
    worker_id: str
    min_income: float
    shift_hours: float = 4.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_zone(worker_id: str, zone_id: Optional[str] = None) -> Optional[str]:
    """Auto-resolve a worker's current zone from position tracking."""
    if zone_id:
        return zone_id
    pos = _worker_positions.get(worker_id, {})
    return pos.get("zone_id")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/forecast/{worker_id}")
async def get_income_forecast(
    worker_id: str,
    zone_id: Optional[str] = Query(default=None, description="Override zone ID"),
):
    """
    Returns income forecast for the next 1 hour and next shift.

    Driven by: demand score, risk score, historical efficiency.
    Updates every 5 seconds via the simulation clock.
    """
    resolved = _resolve_zone(worker_id, zone_id)
    result   = income_os.forecast(worker_id, resolved)

    logger.debug(f"[IncomeOS] /forecast → {worker_id} zone={resolved}: {result['next_1_hour_income']} INR/h")
    return result


@router.get("/scenario/{worker_id}")
async def get_scenario_comparison(
    worker_id: str,
    zone_id: Optional[str] = Query(default=None),
):
    """
    Stay vs. Move scenario comparison.

    Computes income for current zone (STAY) and best nearby zone (MOVE).
    Returns best_option: 'STAY' | 'MOVE' and income_delta.
    """
    resolved = _resolve_zone(worker_id, zone_id)
    result   = income_os.scenario(worker_id, resolved)
    return result


@router.get("/suggestion/{worker_id}")
async def get_ai_suggestion(
    worker_id: str,
    zone_id: Optional[str] = Query(default=None),
):
    """
    AI Decision Engine — returns a human-readable action recommendation.

    Priority levels: INFO | LOW | MEDIUM | HIGH | CRITICAL
    Action types:    STAY | MOVE | OPTIONAL_MOVE | WAIT | EVACUATE
    """
    resolved = _resolve_zone(worker_id, zone_id)
    result   = income_os.suggestion(worker_id, resolved)
    return result


@router.get("/zones/ranked")
async def get_ranked_zones():
    """
    Zone Scoring — ranks all 9 city zones by composite score.

    composite_score = (demand_weight × demand_score) − (risk_weight × risk_score)

    Returns list sorted best → worst with estimated hourly income.
    """
    return {"zones": income_os.zone_scores()}


@router.post("/guarantee")
async def enable_guarantee(request: GuaranteeRequest):
    """
    Enable Guaranteed Income Mode for a worker.

    System calculates a dynamic premium (8–15% of guaranteed amount)
    and monitors earnings. If income falls below `min_income` during
    a disruption, payout triggers automatically.
    """
    if request.min_income <= 0 or request.min_income > 10000:
        raise HTTPException(
            status_code=400,
            detail="min_income must be between 1 and 10,000 INR"
        )

    result = income_os.set_guarantee(
        request.worker_id,
        request.min_income,
        request.shift_hours
    )
    return result


@router.get("/guarantee/{worker_id}")
async def get_guarantee_status(worker_id: str):
    """Return current guarantee mode status for a worker."""
    return income_os.guarantee_status(worker_id)


@router.delete("/guarantee/{worker_id}")
async def disable_guarantee(worker_id: str):
    """Disable guarantee mode for a worker."""
    return income_os.disable_guarantee(worker_id)


@router.get("/snapshot/{worker_id}")
async def get_full_snapshot(
    worker_id: str,
    zone_id: Optional[str] = Query(default=None),
):
    """
    Full Income OS snapshot — forecast + scenario + suggestion + guarantee.

    This is the same payload injected into each WebSocket city_update.
    """
    resolved = _resolve_zone(worker_id, zone_id)
    return income_os.snapshot(worker_id, resolved)


@router.get("/demo-flow/{worker_id}")
async def run_demo_flow(worker_id: str):
    """
    Demo flow endpoint — returns the complete narrative data needed for
    a step-by-step Income OS product demonstration.
    """
    from services.city_graph_service import city_graph

    zones    = income_os.zone_scores()
    best     = zones[0] if zones else {}
    forecast = income_os.forecast(worker_id)
    scenario = income_os.scenario(worker_id)
    suggest  = income_os.suggestion(worker_id)
    guarantee = income_os.guarantee_status(worker_id)

    analytics = city_graph.get_analytics()

    return {
        "worker_id":     worker_id,
        "city_state":    analytics,
        "income_forecast": {
            "next_1h":   forecast["next_1_hour_income"],
            "next_shift": forecast["next_shift_income"],
            "confidence": forecast["confidence_score"],
            "trend":      forecast["trend"],
        },
        "best_zone": {
            "name":  best.get("name"),
            "score": best.get("composite_score"),
            "income_per_hour": best.get("income_per_hour"),
        },
        "scenario": scenario,
        "ai_suggestion": suggest["message"],
        "ai_action":     suggest["action_type"],
        "ai_priority":   suggest["priority"],
        "guarantee":     guarantee,
        "ranked_zones":  zones,
    }
