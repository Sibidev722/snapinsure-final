from core.event_bus import event_bus
from core.logger import logger
from typing import Dict, Any

class PoWFraudEngine:
    def __init__(self):
        # worker_id -> tracking metrics
        self.tracking: Dict[str, Dict[str, Any]] = {}

    def init_workers(self, mock_workers):
        for worker in mock_workers:
            wid = worker["worker_id"]
            self.tracking[wid] = {
                "active_time": 0,
                "idle_time": 0,
                "route_attempts": 0,
                "completed_trips": 0,
                "fraud_score": 100,
                "is_valid": True
            }
        # Pre-configure fraudster for demo
        if "ZOM-1003" in self.tracking:
            self.tracking["ZOM-1003"]["idle_time"] = 400
            self.tracking["ZOM-1003"]["fraud_score"] = 10
            self.tracking["ZOM-1003"]["is_valid"] = False

    async def handle_worker_activity(self, payload: Dict):
        """
        Process incoming raw GPS ticks.
        payload = {"worker_id": str, "speed": float, "tick_interval": int, "route_attempt": bool, "competed_trip": bool}
        """
        worker_id = payload.get("worker_id")
        if not worker_id or worker_id not in self.tracking:
            return

        tick_time = payload.get("tick_interval", 4)
        speed = payload.get("speed", 0)
        pow_m = self.tracking[worker_id]
        
        old_valid = pow_m["is_valid"]

        if worker_id == "ZOM-1003":
            # Hardcoded demo fraud profile: always idle, score decays
            pow_m["idle_time"] += tick_time
            pow_m["is_valid"] = False
            pow_m["fraud_score"] = max(0, pow_m["fraud_score"] - 2)
        else:
            if speed > 5:
                pow_m["active_time"] += tick_time
            else:
                pow_m["idle_time"] += tick_time

            if payload.get("route_attempt"):
                pow_m["route_attempts"] += 1
            if payload.get("completed_trip"):
                pow_m["completed_trips"] += 1

            # Recalculate generic score
            total_time = max(1, pow_m["active_time"] + pow_m["idle_time"])
            activity_ratio = pow_m["active_time"] / total_time
            
            # Artificial bump so normal mock workers typically stay above 50 over long durations
            # Real behavior would rely on hard telemetry
            score = (activity_ratio * 70) + min(30, pow_m["completed_trips"] * 10) + 15
            pow_m["fraud_score"] = int(max(0, min(100, score)))

            # Only disable if heavily idle, Re-enable fairly easily for continuous demoing
            if pow_m["active_time"] > 10 and pow_m["fraud_score"] >= 45:
                pow_m["is_valid"] = True
            elif activity_ratio < 0.15 and pow_m["idle_time"] > 120 and pow_m["fraud_score"] < 40:
                pow_m["is_valid"] = False

        if old_valid != pow_m["is_valid"]:
            # Status changed, emit alert
            await event_bus.emit("FRAUD_ALERT", {
                "worker_id": worker_id, 
                "is_valid": pow_m["is_valid"],
                "fraud_score": pow_m["fraud_score"]
            })

pow_fraud_engine = PoWFraudEngine()

# Subscribe to activity updates
event_bus.subscribe("WORKER_ACTIVITY", pow_fraud_engine.handle_worker_activity)
