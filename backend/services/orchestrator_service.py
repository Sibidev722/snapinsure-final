from core.event_bus import event_bus
from core.logger import logger
from services.city_graph_service import city_graph
from typing import Dict, List, Any

class OrchestratorEngine:
    """
    Central Decision Engine that glues together:
    - Worker GPS Ticks
    - Payout Evaluation Triggering
    - UI State Building
    """
    def __init__(self):
        self.active = True
        self._worker_prev_zone_states: Dict[str, str] = {}

    async def evaluate_worker_tick(self, payload: Dict):
        """
        Called on WORKER_ACTIVITY (which comes from simulation_service's loop per worker).
        Checks if the worker is in a RED or YELLOW zone and triggers Payout Engine if needed.
        """
        worker = payload.get("worker")
        pos = payload.get("pos")
        shift = payload.get("shift")

        if not worker or not pos:
            return

        zone_id = pos.get("zone_id")
        if not zone_id:
            return

        zone = city_graph.get_zone(zone_id)
        if not zone:
            return

        zone_state = zone.get("state", "GREEN")

        # Track state transitions to ensure we only trigger on edge changes
        state_key = f"{worker.get('worker_id')}_{zone_id}"
        prev_state = self._worker_prev_zone_states.get(state_key, "GREEN")
        self._worker_prev_zone_states[state_key] = zone_state

        if zone_state in ["RED", "YELLOW"] and prev_state != zone_state:
            # Setup callback to update pool safely
            def update_pool(zid: str, amount: float):
                z = city_graph.get_zone(zid)
                if z:
                    z["pool_balance"] = round(z.get("pool_balance", 0) - amount, 2)
                    city_graph.G.nodes[zid]["pool_balance"] = z["pool_balance"]

            logger.info(f"[TRACING] 3. Zone State Evaluated -> {zone_state} detected for zone {zone_id}")
            logger.info(f"[TRACING] 4. Decision Engine -> Emitting PAYOUT_TRIGGER for worker {worker.get('worker_id')}")

            payload = {
                "worker": worker,
                "zone": zone,
                "zone_state": zone_state,
                "shift": shift,
                "city_graph_pool_updater": update_pool
            }
            await event_bus.emit("PAYOUT_TRIGGER", payload)

orchestrator = OrchestratorEngine()

# Subscribe Orchestrator to worker ticks that occur every frame
event_bus.subscribe("WORKER_ACTIVITY", orchestrator.evaluate_worker_tick)
