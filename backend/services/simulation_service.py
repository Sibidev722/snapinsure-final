"""
Simulation Service (Refactored for Event-Driven Architecture)
-------------------------------------------------------------
Background asyncio task that acts simply as the simulation CLOCK.
1. Ticks the city graph.
2. Moves worker GPS positions.
3. Randomly injects disruptions.
4. Emits TICK and ACTIVITY events to the Event Bus.
"""

import asyncio
import random
import math
from datetime import datetime
from typing import Set, List, Dict, Any

from services.city_graph_service import city_graph, ZONE_DEFINITIONS
from core.mock_workers import MOCK_WORKERS
from core.logger import logger
from core.event_bus import event_bus
from services.pow_fraud_engine import pow_fraud_engine
from services.unified_payout_engine import payout_engine
from services.income_os_service import income_os

TICK_INTERVAL   = 4      
AUTO_EVENT_INTERVAL = 30 

# Per-worker GPS state
_worker_positions: Dict[str, Dict] = {}

# Shift Insurance
_worker_shifts: Dict[str, Dict] = {}

SHIFTS_CONFIG = {
    "morning": {"name": "Morning (6–10 AM)", "expected_income": 800.0},
    "lunch": {"name": "Lunch (10 AM–2 PM)", "expected_income": 600.0},
    "evening": {"name": "Evening (4–8 PM)", "expected_income": 900.0},
    "night": {"name": "Night (8 PM–12 AM)", "expected_income": 1200.0},
}

_analytics: Dict[str, Any] = {
    "total_events": 0,
    "active_disruptions": 0,
}
_last_auto_event: float = 0.0
_recent_events: List[Dict] = []


def set_worker_shift(worker_id: str, shift_id: str) -> Dict:
    if shift_id not in SHIFTS_CONFIG:
        return {"success": False, "message": "Invalid shift ID"}
    _worker_shifts[worker_id] = {
        "shift_id": shift_id,
        "name": SHIFTS_CONFIG[shift_id]["name"],
        "expected_income": SHIFTS_CONFIG[shift_id]["expected_income"],
        "current_earnings": 0.0,
        "compensated": False
    }
    return {"success": True, "shift": _worker_shifts[worker_id]}


def _init_worker_positions():
    pow_fraud_engine.init_workers(MOCK_WORKERS)
    payout_engine.init_history()
    
    zones = city_graph.get_all_zones()
    for i, worker in enumerate(MOCK_WORKERS):
        zone = zones[i % len(zones)]
        _worker_positions[worker["worker_id"]] = {
            "lat": zone["lat"] + random.uniform(-0.012, 0.012),
            "lon": zone["lon"] + random.uniform(-0.014, 0.014),
            "zone_id": zone["id"],
            "heading": random.uniform(0, 360),
            "speed": random.uniform(15, 35),  
        }


async def _move_workers():
    """Nudge GPS and emit events directly to the Event Bus for Engines."""
    zones = {z["id"]: z for z in city_graph.get_all_zones()}

    for worker in MOCK_WORKERS:
        wid = worker["worker_id"]
        pos = _worker_positions.get(wid)
        if not pos:
            continue

        heading_rad = math.radians(pos["heading"])
        speed_deg   = pos["speed"] / 111_000 * TICK_INTERVAL  

        pos["lat"] += speed_deg * math.cos(heading_rad)
        pos["lon"] += speed_deg * math.sin(heading_rad)

        pos["heading"] = (pos["heading"] + random.uniform(-25, 25)) % 360
        pos["speed"]   = max(5, min(45, pos["speed"] + random.uniform(-3, 3)))

        pos["lat"] = max(12.85, min(13.20, pos["lat"]))
        pos["lon"] = max(80.05, min(80.35, pos["lon"]))

        nearest = min(zones.values(), key=lambda z: (z["lat"] - pos["lat"])**2 + (z["lon"] - pos["lon"])**2)
        pos["zone_id"] = nearest["id"]

        # Prepare activity metrics
        route_attempt = pos["speed"] > 5 and random.random() < 0.15
        completed_trip = pos["speed"] > 5 and random.random() < 0.12

        # Emit to Fraud Engine directly via Bus
        payload = {
            "worker_id": wid,
            "worker": worker,
            "pos": pos,
            "shift": _worker_shifts.get(wid),
            "tick_interval": TICK_INTERVAL,
            "speed": pos["speed"] if wid != "ZOM-1003" else 0, # Hack for demo
            "route_attempt": route_attempt,
            "completed_trip": completed_trip
        }
        await event_bus.emit("WORKER_ACTIVITY", payload)


def _simulate_earnings():
    zones = {z["id"]: z for z in city_graph.get_all_zones()}
    for worker_id, shift in _worker_shifts.items():
        if shift.get("compensated"):
            continue
            
        pos = _worker_positions.get(worker_id, {})
        zone_id = pos.get("zone_id", "Z5")
        zone_state = zones.get(zone_id, {}).get("state", "GREEN")
        
        if zone_state == "GREEN":
            increment = 20.0
            shift["current_earnings"] += increment
        elif zone_state == "YELLOW":
            increment = 8.0
            shift["current_earnings"] += increment
        else:
            increment = 0.0
            
        shift["current_earnings"] += random.uniform(-2, 2)
        shift["current_earnings"] = max(0.0, min(shift["expected_income"], shift["current_earnings"]))

        # Update Income OS guarantee tracker
        income_os.update_earnings(worker_id, increment)

        # Check guarantee trigger
        trigger = income_os.check_guarantee_trigger(worker_id, zone_state)
        if trigger:
            logger.info(f"[IncomeOS] Guarantee payout triggered for {worker_id}: ₹{trigger['payout_amount']}")
            _recent_events.insert(0, {
                "type": "PAYOUT",
                "msg": f"💰 Income Guarantee triggered — ₹{trigger['payout_amount']:.0f} credited to {worker_id}",
                "amount": trigger["payout_amount"],
                "reason": "Income Guarantee Payout",
                "timestamp": trigger["triggered_at"],
            })


def _maybe_auto_event() -> List[Dict]:
    """Simulation auto-events REMOVED — zones are now driven by real-world APIs.
    Kept as stub so existing callsites don't break during migration."""
    return []


async def simulation_loop():
    logger.info("[CLOCK] Ticker Loop Started — zone states driven by real-world APIs.")
    _init_worker_positions()

    while True:
        try:
            # Tick city graph only for pool_balance and demand fluctuation tracking
            # Zone STATE is set exclusively by zone_state_engine (real API data)
            city_graph.tick()
            await _move_workers()
            _simulate_earnings()

            # No random auto-events — real signals drive everything
            # Emit UI_SYNC so WebSocket clients get worker position updates
            await event_bus.emit("UI_SYNC")

        except Exception as e:
            logger.error(f"[CLOCK] Simulation error: {e}")

        await asyncio.sleep(TICK_INTERVAL)


# ── HTTP FALLBACK BUILDER & MANUAL TRIGGER ───────────────────────────────

def build_current_state() -> Dict:
    zones = city_graph.get_all_zones()
    zone_map = {z["id"]: z for z in zones}
    workers_out = []
    
    for worker in MOCK_WORKERS:
        wid = worker["worker_id"]
        pos = _worker_positions.get(wid, {})
        zone_id = pos.get("zone_id", "Z5")

        # Compute Income OS snapshot for this worker
        try:
            income_snapshot = income_os.snapshot(wid, zone_id)
        except Exception:
            income_snapshot = {}

        workers_out.append({
            "id": wid,
            "name": worker["name"],
            "company": worker["company"],
            "lat": round(pos.get("lat", 13.07), 6),
            "lon": round(pos.get("lon", 80.23), 6),
            "zone_id": zone_id,
            "zone_state": zone_map.get(zone_id, {}).get("state", "GREEN"),
            "total_protection": worker.get("total_protection", 0.0),
            "last_payout": worker.get("last_payout", 0.0),
            "shift": _worker_shifts.get(wid),
            "pow": pow_fraud_engine.tracking.get(wid),
            "income_os": income_snapshot,
        })

    # Combine recent payouts and general events
    all_events = payout_engine.payout_history[:15] + _recent_events[:15]
    all_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    total_payout_today = sum(p.get("amount", 0) for p in payout_engine.payout_history)

    analytics = {
        **_analytics,
        **city_graph.get_analytics(),
        "total_payout_today": total_payout_today,
        "recent_payouts": payout_engine.payout_history[:10],
        "workers_in_red": sum(1 for w in workers_out if w["zone_state"] == "RED"),
        "workers_in_yellow": sum(1 for w in workers_out if w["zone_state"] == "YELLOW"),
        "workers_in_green": sum(1 for w in workers_out if w["zone_state"] == "GREEN"),
    }

    return {
        "type": "city_update",
        "timestamp": datetime.utcnow().isoformat(),
        "zones": zones,
        "workers": workers_out,
        "events": all_events[:20],  # Give top 20 events interleaved
        "analytics": analytics,
    }


async def manual_trigger(event_type: str) -> Dict:
    """Triggered by frontend manual control."""
    logger.info(f"[TRACING] 1. Simulation Button Clicked: {event_type}")
    logger.info(f"[TRACING] 2. Backend Received Event: {event_type}")
    events = []
    
    if event_type == "rain":
        city_graph.apply_rain(intensity=0.92)
        events.append({"type": "WEATHER", "msg": "🌧️ HEAVY RAIN triggered"})
        _analytics["active_disruptions"] += 1
    elif event_type == "traffic":
        city_graph.apply_traffic(delay_minutes=45)
        events.append({"type": "TRAFFIC", "msg": "🚧 TRAFFIC JAM triggered"})
        _analytics["active_disruptions"] += 1
    elif event_type == "strike":
        city_graph.apply_strike()
        events.append({"type": "STRIKE", "msg": "📢 STRIKE triggered"})
        _analytics["active_disruptions"] += 1
    elif event_type == "demand":
        city_graph.apply_demand_collapse()
        events.append({"type": "SYSTEM", "msg": "📉 DEMAND COLLAPSE triggered"})
        _analytics["active_disruptions"] += 1
    elif event_type == "clear":
        events.append({"type": "SYSTEM", "msg": "Simulation manually cleared."})
        city_graph.clear_disruption()
        # Ensure we flush previous zone states so triggers can happen again when red drops later
        from services.orchestrator_service import orchestrator
        orchestrator._worker_prev_zone_states.clear()

    # Reset any active locks in the Payout engine to allow immediate consecutive test triggers
    payout_engine.clear_locks()

    for e in events:
        e["timestamp"] = datetime.utcnow().isoformat()
        _recent_events.insert(0, e)

    # Force one full worker pass so Orchestrator fires payouts immediately
    await _move_workers()
    _simulate_earnings()
    
    # Also emit UI_SYNC so the updated zone map reaches the frontend immediately
    await event_bus.emit("UI_SYNC")

    return build_current_state()

def get_current_state() -> Dict:
    return build_current_state()

def get_payout_history() -> List[Dict]:
    return payout_engine.payout_history[:20]

# Add listener for Fraud Strike Events
async def collect_strike_event(payload):
    _recent_events.insert(0, payload)

event_bus.subscribe("UI_STRIKE_EVENT", collect_strike_event)
