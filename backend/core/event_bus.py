import asyncio
from typing import Dict, List, Callable, Any
from core.logger import logger

# Event Constants
EVENT_WORKER_ACTIVITY    = "WORKER_ACTIVITY"
EVENT_PAYOUT_TRIGGER     = "PAYOUT_TRIGGER"
EVENT_PAYOUT_SUCCESS     = "PAYOUT_SUCCESS"
EVENT_UI_SYNC            = "UI_SYNC"
EVENT_UI_NOTIFICATION    = "UI_NOTIFICATION"
EVENT_FRAUD_ALERT        = "FRAUD_ALERT"

# Real-world signal pipeline events
EVENT_ZONE_STATE_CHANGED   = "ZONE_STATE_CHANGED"
EVENT_WEATHER_ZONE_UPDATE  = "WEATHER_ZONE_UPDATE"
EVENT_TRAFFIC_ZONE_UPDATE  = "TRAFFIC_ZONE_UPDATE"
EVENT_DISRUPTION_DETECTED  = "DISRUPTION_DETECTED"
EVENT_DEMAND_DROP_ALERT    = "DEMAND_DROP_ALERT"


class EventBus:
    """
    Centralised Async Event Bus for Decoupled Engine Communication
    """
    def __init__(self):
        # Maps event types to lists of async callback functions
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        """Register an async callback for a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(f"[BUS] Subscribed {callback.__name__} to {event_type}")

    async def emit(self, event_type: str, payload: Any = None):
        """Emit an event, triggering all subscribed async callbacks concurrently."""
        if event_type not in self._subscribers:
            return

        callbacks = self._subscribers[event_type]
        # Execute all listeners concurrently
        tasks = []
        for cb in callbacks:
            try:
                res = cb(payload)
                if asyncio.iscoroutine(res):
                    tasks.append(asyncio.create_task(res))
                elif asyncio.isfuture(res) or isinstance(res, asyncio.Task):
                    tasks.append(res)
            except Exception as e:
                logger.error(f"[BUS] Error wrapping callback {cb.__name__} for {event_type}: {e}")
                
        if tasks:
            # We await until all callbacks have at least finished their execution
            # This ensures that sequential emits in simulated loops maintain data consistency
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"[BUS] Exception in callback for {event_type}: {r}", exc_info=r)

# Global singleton event bus
event_bus = EventBus()
