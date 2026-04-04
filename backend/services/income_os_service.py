"""
Income OS Service
-----------------
AI-Powered Income Operating System for gig workers.

Modules:
  1. Income Forecast Engine     — predict next-hour & shift earnings
  2. Scenario Comparison Engine — stay vs. move analysis
  3. AI Decision Engine         — human-readable action recommendation
  4. Zone Scoring System        — rank all zones by composite score
  5. Guaranteed Income Mode     — minimum income guarantee with payout trigger
"""

import random
import math
from typing import Dict, List, Optional, Any
from datetime import datetime

from services.city_graph_service import city_graph, ZONE_DEFINITIONS
from core.logger import logger

# ── Constants ─────────────────────────────────────────────────────────────────

AVG_ORDER_VALUE   = 55.0      # INR per delivery
DEMAND_WEIGHT     = 0.65
RISK_WEIGHT       = 0.35
SHIFT_HOURS       = 4.0
MAX_ORDERS_PER_H  = 12        # max realistic deliveries per hour

# Per-worker historical efficiency (simulated, persistent during session)
_worker_efficiency: Dict[str, float] = {}

# Guarantee mode registry
_guarantees: Dict[str, Dict] = {}

# Per-worker rolling income snapshot (used for confidence scoring)
_worker_income_history: Dict[str, List[float]] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_efficiency(worker_id: str) -> float:
    """Return or initialise per-worker efficiency factor (0.6 – 1.0)."""
    if worker_id not in _worker_efficiency:
        _worker_efficiency[worker_id] = round(random.uniform(0.68, 0.97), 3)
    return _worker_efficiency[worker_id]


def _zone_income_per_hour(zone: Dict) -> float:
    """Estimate hourly income for a given zone dict."""
    demand   = zone.get("demand_score", 0.7)
    risk     = zone.get("risk_score",   0.3)
    orders_m = zone.get("orders_per_minute", 100)
    baseline = zone.get("baseline_orders",   200)

    # Normalise orders availability (0-1)
    order_factor = min(orders_m / max(baseline, 1), 1.0)

    # Effective deliveries per hour = MAX × demand × order_factor
    effective_orders_h = MAX_ORDERS_PER_H * demand * order_factor

    # Risk penalty reduces effective throughput
    risk_penalty = 1.0 - (risk * 0.6)

    income = effective_orders_h * AVG_ORDER_VALUE * risk_penalty
    return round(max(0.0, income), 2)


def _zone_composite_score(zone: Dict, state_penalty: bool = True) -> float:
    """Composite zone score (higher = better for worker)."""
    demand   = zone.get("demand_score", 0.5)
    risk     = zone.get("risk_score",   0.5)
    orders   = zone.get("orders_per_minute", 100)
    baseline = zone.get("baseline_orders",   200)
    state    = zone.get("state", "GREEN")

    order_factor = min(orders / max(baseline, 1), 1.0)
    score = (demand * DEMAND_WEIGHT) + ((1 - risk) * RISK_WEIGHT * order_factor)

    if state_penalty:
        if state == "RED":
            score -= 0.60
        elif state == "YELLOW":
            score -= 0.25

    return round(max(0.0, score), 4)


def _nearby_zones(zone_id: str, all_zones: List[Dict], max_zones: int = 3) -> List[Dict]:
    """Return the `max_zones` nearest zones to zone_id (by lat/lon distance)."""
    current = next((z for z in all_zones if z["id"] == zone_id), None)
    if not current:
        return []

    def dist(z):
        dlat = z["lat"] - current["lat"]
        dlon = z["lon"] - current["lon"]
        return math.sqrt(dlat**2 + dlon**2)

    others = [z for z in all_zones if z["id"] != zone_id]
    others.sort(key=dist)
    return others[:max_zones]


def _km_distance(z1: Dict, z2: Dict) -> float:
    """Haversine-approximated distance (km) between two zone dicts."""
    R = 6371.0
    lat1, lon1 = math.radians(z1["lat"]), math.radians(z1["lon"])
    lat2, lon2 = math.radians(z2["lat"]), math.radians(z2["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(R * 2 * math.asin(math.sqrt(a)), 2)


# ── Module 1: Income Forecast Engine ─────────────────────────────────────────

def compute_income_forecast(worker_id: str, zone_id: Optional[str] = None) -> Dict:
    """
    Predict income for next 1 hour and next shift.

    Returns:
      { next_1_hour_income, next_shift_income, confidence_score,
        demand_score, risk_level, zone_id }
    """
    zones = city_graph.get_all_zones()
    if not zones:
        return {"next_1_hour_income": 0, "next_shift_income": 0, "confidence_score": 0}

    zone_map = {z["id"]: z for z in zones}

    # Use provided zone_id or pick best available
    if zone_id and zone_id in zone_map:
        zone = zone_map[zone_id]
    else:
        # fallback: pick zone Z5 (central) or first available
        zone = zone_map.get("Z5", zones[0])
        zone_id = zone["id"]

    efficiency    = _get_efficiency(worker_id)
    hourly_income = _zone_income_per_hour(zone) * efficiency

    # Small stochastic noise so the number "breathes"
    noise = random.uniform(0.93, 1.07)
    hourly_income = round(hourly_income * noise, 0)
    shift_income  = round(hourly_income * SHIFT_HOURS * random.uniform(0.85, 1.05), 0)

    # Confidence: high demand + low risk + no disruption = high confidence
    demand   = zone.get("demand_score", 0.7)
    risk     = zone.get("risk_score",   0.3)
    state    = zone.get("state", "GREEN")

    if state == "GREEN":
        raw_conf = (demand * 0.6) + ((1 - risk) * 0.4)
    elif state == "YELLOW":
        raw_conf = (demand * 0.5) + ((1 - risk) * 0.3) - 0.1
    else:
        raw_conf = max(0.1, (demand * 0.3) + ((1 - risk) * 0.2) - 0.3)

    confidence = round(min(max(raw_conf, 0.05), 0.99), 2)

    # Rolling history for trend arrow
    hist = _worker_income_history.setdefault(worker_id, [])
    hist.append(hourly_income)
    if len(hist) > 10:
        hist.pop(0)

    trend = "UP" if len(hist) >= 2 and hist[-1] > hist[-2] else ("DOWN" if len(hist) >= 2 and hist[-1] < hist[-2] else "FLAT")

    # Risk label
    if risk < 0.30:
        risk_level = "LOW"
    elif risk < 0.60:
        risk_level = "MODERATE"
    else:
        risk_level = "HIGH"

    return {
        "next_1_hour_income":  int(hourly_income),
        "next_shift_income":   int(shift_income),
        "confidence_score":    confidence,
        "demand_score":        round(demand, 2),
        "risk_level":          risk_level,
        "trend":               trend,
        "zone_id":             zone_id,
        "zone_name":           zone.get("name", zone_id),
        "zone_state":          state,
        "efficiency_factor":   efficiency,
    }


# ── Module 2: Scenario Comparison Engine ─────────────────────────────────────

def compute_scenario_comparison(worker_id: str, current_zone_id: Optional[str] = None) -> Dict:
    """
    Compare staying in current zone vs. moving to the best nearby zone.

    Returns:
      { stay: {zone, income}, move: {zone, income, distance_km}, best_option, income_delta }
    """
    zones = city_graph.get_all_zones()
    zone_map = {z["id"]: z for z in zones}

    if not current_zone_id or current_zone_id not in zone_map:
        current_zone_id = "Z5"

    current_zone  = zone_map[current_zone_id]
    efficiency    = _get_efficiency(worker_id)

    stay_income = round(_zone_income_per_hour(current_zone) * efficiency, 0)

    # Evaluate nearby zones
    nearby = _nearby_zones(current_zone_id, zones, max_zones=4)
    best_nearby = None
    best_income = -1

    for z in nearby:
        inc = round(_zone_income_per_hour(z) * efficiency, 0)
        if inc > best_income:
            best_income = inc
            best_nearby = z

    if best_nearby is None:
        best_nearby = current_zone
        best_income = stay_income

    move_income = int(best_income)
    stay_income = int(stay_income)
    income_delta = move_income - stay_income

    # Which is better?
    if income_delta > 30:
        best_option = "MOVE"
    else:
        best_option = "STAY"
        income_delta = max(income_delta, 0)

    distance_km = _km_distance(current_zone, best_nearby) if best_nearby["id"] != current_zone_id else 0.0

    return {
        "stay": {
            "zone_id":      current_zone_id,
            "zone_name":    current_zone.get("name", current_zone_id),
            "zone_state":   current_zone.get("state", "GREEN"),
            "income_per_hour": stay_income,
        },
        "move": {
            "zone_id":      best_nearby["id"],
            "zone_name":    best_nearby.get("name", best_nearby["id"]),
            "zone_state":   best_nearby.get("state", "GREEN"),
            "income_per_hour": move_income,
            "distance_km":  distance_km,
        },
        "best_option":  best_option,
        "income_delta": income_delta,
    }


# ── Module 3: AI Decision Engine ─────────────────────────────────────────────

def generate_ai_suggestion(worker_id: str, current_zone_id: Optional[str] = None) -> Dict:
    """
    Generate a human-readable action recommendation with priority level.

    Returns:
      { message, priority, action_type, income_uplift }
    """
    scenario = compute_scenario_comparison(worker_id, current_zone_id)
    forecast = compute_income_forecast(worker_id, current_zone_id)

    best    = scenario["best_option"]
    delta   = scenario["income_delta"]
    state   = forecast["zone_state"]
    risk    = forecast["risk_level"]
    confidence = forecast["confidence_score"]

    if state == "RED":
        if best == "MOVE":
            msg = (
                f"⚠️ Your zone is BLOCKED. Move {scenario['move']['distance_km']} km to "
                f"{scenario['move']['zone_name']} — earn ₹{delta} more/hr."
            )
            priority = "CRITICAL"
            action   = "EVACUATE"
        else:
            msg      = "⚠️ All nearby zones are disrupted. Stay sheltered and wait for conditions to clear."
            priority = "WARNING"
            action   = "WAIT"

    elif state == "YELLOW":
        if best == "MOVE" and delta > 50:
            msg = (
                f"🟡 Disruption detected. Move {scenario['move']['distance_km']} km to "
                f"{scenario['move']['zone_name']} to increase earnings by ₹{delta}/hr."
            )
            priority = "HIGH"
            action   = "MOVE"
        else:
            msg      = f"🟡 Minor disruption in your zone. Staying is viable — current forecast ₹{forecast['next_1_hour_income']}/hr."
            priority = "MEDIUM"
            action   = "STAY"

    else:  # GREEN
        if best == "MOVE" and delta > 80:
            msg = (
                f"💡 Opportunity: Move {scenario['move']['distance_km']} km to "
                f"{scenario['move']['zone_name']} — potential uplift ₹{delta}/hr."
            )
            priority = "LOW"
            action   = "OPTIONAL_MOVE"
        else:
            msg      = f"✅ Current zone is optimal. Expected ₹{forecast['next_1_hour_income']} this hour."
            priority = "INFO"
            action   = "STAY"

    return {
        "message":          msg,
        "priority":         priority,
        "action_type":      action,
        "income_uplift":    delta,
        "confidence":       confidence,
        "best_zone_id":     scenario["move"]["zone_id"],
        "best_zone_name":   scenario["move"]["zone_name"],
        "distance_km":      scenario["move"]["distance_km"],
    }


# ── Module 4: Zone Scoring System ────────────────────────────────────────────

def get_zone_scores() -> List[Dict]:
    """
    Score and rank all zones.

    Returns a list sorted best → worst, each with:
      { zone_id, name, state, composite_score, income_per_hour,
        demand_score, risk_score, rank }
    """
    zones  = city_graph.get_all_zones()
    scored = []

    for z in zones:
        score       = _zone_composite_score(z)
        hourly_inc  = _zone_income_per_hour(z)

        scored.append({
            "zone_id":         z["id"],
            "name":            z.get("name", z["id"]),
            "state":           z.get("state", "GREEN"),
            "composite_score": score,
            "income_per_hour": int(hourly_inc),
            "demand_score":    round(z.get("demand_score", 0.5), 2),
            "risk_score":      round(z.get("risk_score",   0.5), 2),
            "orders_per_minute": z.get("orders_per_minute", 0),
            "pool_balance":    z.get("pool_balance", 0),
        })

    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    for i, s in enumerate(scored):
        s["rank"] = i + 1
        s["is_best"] = (i == 0)

    return scored


# ── Module 5: Guaranteed Income Mode ─────────────────────────────────────────

def set_guarantee(worker_id: str, min_income: float, shift_hours: float = 4.0) -> Dict:
    """Enable guaranteed income mode for a worker."""
    if min_income <= 0:
        return {"success": False, "message": "min_income must be positive"}

    # Estimate premium: 8–15% of guarantee
    risk_factor = 0.08 + (min_income / 5000) * 0.07
    premium = round(min_income * min(risk_factor, 0.15), 2)

    _guarantees[worker_id] = {
        "worker_id":      worker_id,
        "min_income":     min_income,
        "shift_hours":    shift_hours,
        "premium":        premium,
        "current_earned": 0.0,
        "payout_triggered": False,
        "enabled_at":     datetime.utcnow().isoformat(),
    }

    logger.info(f"[IncomeOS] Guarantee enabled: {worker_id} → ₹{min_income} (premium ₹{premium})")

    return {
        "success":     True,
        "worker_id":   worker_id,
        "min_income":  min_income,
        "premium":     premium,
        "shift_hours": shift_hours,
        "message":     f"Guarantee active. If earnings fall below ₹{min_income}, payout triggers automatically.",
    }


def update_guarantee_earnings(worker_id: str, earned_increment: float) -> None:
    """Accumulate earnings for workers in guarantee mode (called by simulation tick)."""
    if worker_id not in _guarantees:
        return
    g = _guarantees[worker_id]
    if not g["payout_triggered"]:
        g["current_earned"] = round(g["current_earned"] + earned_increment, 2)


def check_guarantee_trigger(worker_id: str, zone_state: str = "GREEN") -> Optional[Dict]:
    """
    Called each tick. Returns payout dict if shortfall is triggered, else None.
    Trigger condition: zone is RED/YELLOW AND earned < 60% of guaranteed income.
    """
    if worker_id not in _guarantees:
        return None
    g = _guarantees[worker_id]
    if g["payout_triggered"]:
        return None

    # Only trigger in disruption
    if zone_state not in ("RED", "YELLOW"):
        return None

    shortfall_pct = g["current_earned"] / max(g["min_income"], 1)

    if shortfall_pct < 0.60:
        shortfall = round(g["min_income"] - g["current_earned"], 2)
        g["payout_triggered"] = True

        logger.info(f"[IncomeOS] Guarantee PAYOUT: {worker_id} → ₹{shortfall}")

        return {
            "worker_id":     worker_id,
            "payout_amount": shortfall,
            "min_income":    g["min_income"],
            "current_earned": g["current_earned"],
            "triggered_at":  datetime.utcnow().isoformat(),
            "reason":        f"Income fell below guarantee — zone {zone_state}",
        }

    return None


def get_guarantee_status(worker_id: str) -> Dict:
    """Return current guarantee mode status for a worker."""
    if worker_id not in _guarantees:
        return {"enabled": False}

    g = _guarantees[worker_id]
    shortfall = max(0, round(g["min_income"] - g["current_earned"], 2))
    pct       = round(min(g["current_earned"] / max(g["min_income"], 1), 1.0) * 100, 1)

    return {
        "enabled":          True,
        "worker_id":        worker_id,
        "min_income":       g["min_income"],
        "premium":          g["premium"],
        "current_earned":   round(g["current_earned"], 2),
        "shortfall":        shortfall,
        "pct_achieved":     pct,
        "payout_triggered": g["payout_triggered"],
        "enabled_at":       g["enabled_at"],
    }


def disable_guarantee(worker_id: str) -> Dict:
    """Disable guarantee mode for a worker."""
    if worker_id in _guarantees:
        del _guarantees[worker_id]
    return {"success": True, "worker_id": worker_id}


# ── Full worker snapshot (for WebSocket broadcasts) ───────────────────────────

def get_worker_income_snapshot(worker_id: str, zone_id: Optional[str] = None) -> Dict:
    """
    Returns a complete Income OS snapshot for a single worker.
    Used to enrich each WebSocket city_update payload.
    """
    forecast   = compute_income_forecast(worker_id, zone_id)
    scenario   = compute_scenario_comparison(worker_id, zone_id)
    suggestion = generate_ai_suggestion(worker_id, zone_id)
    guarantee  = get_guarantee_status(worker_id)

    return {
        "forecast":   forecast,
        "scenario":   scenario,
        "suggestion": suggestion,
        "guarantee":  guarantee,
    }


# ── Singleton convenience ─────────────────────────────────────────────────────

class IncomeOS:
    """Singleton wrapper exposing the Income OS service."""

    def forecast(self, worker_id, zone_id=None):
        return compute_income_forecast(worker_id, zone_id)

    def scenario(self, worker_id, zone_id=None):
        return compute_scenario_comparison(worker_id, zone_id)

    def suggestion(self, worker_id, zone_id=None):
        return generate_ai_suggestion(worker_id, zone_id)

    def zone_scores(self):
        return get_zone_scores()

    def set_guarantee(self, worker_id, min_income, shift_hours=4.0):
        return set_guarantee(worker_id, min_income, shift_hours)

    def guarantee_status(self, worker_id):
        return get_guarantee_status(worker_id)

    def disable_guarantee(self, worker_id):
        return disable_guarantee(worker_id)

    def check_guarantee_trigger(self, worker_id, zone_state="GREEN"):
        return check_guarantee_trigger(worker_id, zone_state)

    def update_earnings(self, worker_id, increment):
        update_guarantee_earnings(worker_id, increment)

    def snapshot(self, worker_id, zone_id=None):
        return get_worker_income_snapshot(worker_id, zone_id)


income_os = IncomeOS()
