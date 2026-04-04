"""
WebSocket + Simulation Control Router
--------------------------------------
Endpoints:
  WS  /ws/city          — Real-time city feed (WebSocket)
  POST /sim/trigger     — Manual disruption trigger (rain/traffic/strike/clear)
  GET  /sim/state       — Current city state (HTTP fallback)
  GET  /sim/analytics   — Aggregated analytics
  GET  /sim/payouts     — Recent payout history
  GET  /sim/route       — Route status between two zones
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.simulation_service import (
    manual_trigger,
    get_current_state,
    get_payout_history,
    build_current_state
)
from services.city_graph_service import city_graph
from core.logger import logger
from core.event_bus import event_bus

router = APIRouter()

# Global WebSocket connection registry
_clients = set()

def register_client(ws) -> None:
    _clients.add(ws)
    logger.info(f"[WS] Client connected. Total: {len(_clients)}")

def unregister_client(ws) -> None:
    _clients.discard(ws)
    logger.info(f"[WS] Client disconnected. Total: {len(_clients)}")

async def _broadcast(payload: dict):
    if not _clients:
        return
    dead = set()
    for ws in list(_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _clients.discard(ws)

# Event Bus Listeners
async def handle_ui_sync(payload=None):
    """When UI_SYNC is triggered, push state."""
    state = build_current_state()
    await _broadcast(state)

async def handle_ui_notification(payload: dict):
    """When a specific notification is emitted, broadcast it immediately to all clients."""
    # Wrap in a type that the frontend can distinguish
    await _broadcast({
        "type": "NOTIFICATION",
        "payload": payload
    })

event_bus.subscribe("UI_SYNC", handle_ui_sync)
event_bus.subscribe("UI_NOTIFICATION", handle_ui_notification)



# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/city")
async def city_websocket(websocket: WebSocket):
    """
    Real-time city feed.
    Broadcasts zone states, worker positions, payouts, and events every 4s.
    """
    await websocket.accept()
    register_client(websocket)

    # Send current state immediately on connect
    try:
        state = get_current_state()
        await websocket.send_json(state)
    except Exception:
        pass

    try:
        while True:
            # Keep connection alive; simulation loop does the broadcasting
            await asyncio.sleep(1)
            # Handle any incoming messages (ping/pong, control messages)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                logger.debug(f"[WS] Received: {data}")
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[WS] Error: {e}")
    finally:
        unregister_client(websocket)


# ── HTTP Simulation Control ───────────────────────────────────────────────────

class TriggerRequest(BaseModel):
    event_type: str  # "rain" | "traffic" | "strike" | "clear"


@router.post("/sim/trigger", summary="Manual Disruption Trigger")
async def trigger_simulation(request: TriggerRequest):
    """
    Manually trigger a disruption event from the frontend control panel.
    Valid event types: rain, traffic, strike, clear
    """
    valid = {"rain", "traffic", "strike", "demand", "clear"}
    if request.event_type not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_type '{request.event_type}'. Must be one of: {valid}"
        )

    result = await manual_trigger(request.event_type)
    return {
        "success": True,
        "triggered": request.event_type,
        "zones_summary": city_graph.get_analytics(),
        "message": f"'{request.event_type}' disruption applied and broadcast to all clients.",
    }


@router.get("/sim/state", summary="Current City State (HTTP)")
async def get_state():
    """HTTP fallback for when WebSocket is not available."""
    return get_current_state()


@router.get("/sim/analytics", summary="City Analytics")
async def get_analytics():
    """Returns aggregate analytics: total payouts, disruptions, zone counts."""
    state = get_current_state()
    return state.get("analytics", {})


@router.get("/sim/payouts", summary="Recent Payout History")
async def recent_payouts():
    """Returns the last 20 auto-triggered payouts across all workers."""
    return {"payouts": get_payout_history()}


@router.get("/sim/route/{source}/{target}", summary="Route Status")
async def route_status(source: str, target: str):
    """
    Calculates route status between two zone IDs using live Dijkstra.
    Returns: GREEN (optimal) | YELLOW (detour) | RED (blocked)
    """
    result = city_graph.get_route_status(source.upper(), target.upper())
    return {"source": source, "target": target, **result}


@router.get("/sim/zones", summary="All Zone States")
async def all_zones():
    """Returns current state of all 9 city zones."""
    return {"zones": city_graph.get_all_zones()}
