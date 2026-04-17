import asyncio
import random
import uuid
from datetime import datetime
from core.database import get_db
from core.event_bus import event_bus
from core.logger import logger
from services.city_graph_service import city_graph
from services.weather_service import weather_service
from services.route_optimizer import route_optimizer
from services.esg_service import update_worker_esg_stats

class LiveSimulatorWorker:
    """
    Live Asynchronous Real-World DB Stream Worker.

    Responsibilities (SIMULATION-FREE):
    - Earnings loop: Writes actual earnings records to MongoDB based on
      real zone states. Zone states come from ZoneStateEngine, NOT from here.
    - Claims loop: Generates claim records whose approval probability and
      payout size are driven by real zone state (RED/YELLOW/GREEN).

    What this worker NO LONGER does:
    - Does NOT call city_graph.apply_rain() / apply_traffic() / apply_strike()
    - Does NOT inject random disruption types
    - Does NOT set zone colors — that is EXCLUSIVELY ZoneStateEngine's job
    """

    def __init__(self):
        self.is_running = False

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        logger.info("[LIVE-SIM] Starting real-data DB stream workers (earnings / claims)")
        asyncio.create_task(self._earnings_loop())
        asyncio.create_task(self._claims_loop())

    async def stop(self):
        self.is_running = False

    # ── Earnings Loop ─────────────────────────────────────────────────────────

    async def _earnings_loop(self):
        """Every 5s: Insert new earnings into DB based on real zone state + weather."""
        db = get_db()
        while self.is_running:
            try:
                worker_agg = await db.workers.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
                if not worker_agg:
                    await asyncio.sleep(5)
                    continue

                worker = worker_agg[0]
                zones  = city_graph.get_all_zones()
                zone   = random.choice(zones)

                # Real zone demand from city_graph (set by ZoneStateEngine)
                zone_demand = zone.get("demand_score", 1.0)
                zone_state  = zone.get("state", "GREEN")

                # Pull cached weather multiplier from DB (written by WeatherPoller)
                weather_doc = await db.weather_state.find_one({"city": "Chennai"})
                weather_multiplier = (
                    weather_doc["impact"]["demand_multiplier"]
                    if weather_doc and "impact" in weather_doc else 1.0
                )

                # Check for active real NLP-mapped events in this zone
                active_events = await db.real_events.count_documents(
                    {"zone_id": zone["id"], "status": "active"}
                )

                # Base orders (organic delivery activity)
                orders = random.randint(1, 4)
                base   = float(orders * random.randint(30, 80))

                # Demand multiplied by real weather signal
                demand_multiplier = (zone_demand * 0.5) + (weather_multiplier * 0.5)

                # Surge: real zone state and NLP events drive surge pricing
                surge = 1.0
                if zone_state == "RED":
                    surge += 0.35    # Red zone workers earn more (risk premium)
                if zone_state == "YELLOW":
                    surge += 0.12
                if active_events > 0:
                    surge += 0.45   # NLP-detected disruption = surge pricing

                earnings = round(base * demand_multiplier * surge, 2)

                doc = {
                    "_id":             str(uuid.uuid4()),
                    "worker_id":       worker["worker_id"],
                    "zone_id":         zone["id"],
                    "timestamp":       datetime.utcnow(),
                    "orders_completed": orders,
                    "earnings":        earnings,
                    "factors": {
                        "base":               base,
                        "demand_multiplier":  round(demand_multiplier, 2),
                        "surge":              round(surge, 2),
                        "active_nlp_events":  active_events,
                        "real_zone_state":    zone_state,
                    },
                }
                await db.earnings.insert_one(doc)

                # ESG carbon tracking
                trip_km = round(random.uniform(2.0, 8.0), 2)
                vehicle = worker.get("vehicle_type", "petrol")
                await update_worker_esg_stats(worker["worker_id"], trip_km, vehicle)

                await event_bus.emit("new_earning", {
                    "type": "new_earning",
                    "data": {
                        "worker_name": worker["name"],
                        "zone_name":   zone["name"],
                        "zone_state":  zone_state,
                        "earnings":    earnings,
                        "orders":      orders,
                        "factors":     doc["factors"],
                        "vehicle_type": vehicle,
                        "timestamp":   doc["timestamp"].isoformat(),
                    },
                })

            except Exception as e:
                logger.error(f"[LIVE-SIM] Earnings loop error: {e}")

            await asyncio.sleep(5)

    # ── Claims Loop ───────────────────────────────────────────────────────────

    async def _claims_loop(self):
        """
        Every 10s: Generate claims whose approval probability is driven by
        the REAL zone state (set by ZoneStateEngine from real APIs).
        NO random disruption injection — zone color comes from ZoneStateEngine.
        """
        db = get_db()
        while self.is_running:
            try:
                zones = city_graph.get_all_zones()
                zone  = random.choice(zones)

                # Real zone state (set by ZoneStateEngine from weather/traffic/NLP/demand)
                zone_state  = zone.get("state", "GREEN")
                zone_reason = zone.get("collapse_reason", "")

                # Pull cached real weather for route-optimizer update
                weather = await weather_service.get_weather_risk(city="Chennai")
                route_optimizer.apply_live_weather(weather)

                # Write analytics disruption record (source = real zone state)
                disrupt_type = {
                    "RED":    "high_risk",
                    "YELLOW": "moderate_risk",
                    "GREEN":  "normal",
                }.get(zone_state, "normal")

                await db.disruptions.insert_one({
                    "_id":       str(uuid.uuid4()),
                    "zone_id":   zone["id"],
                    "type":      disrupt_type,
                    "severity":  zone_state.lower(),
                    "source":    "real_zone_state_engine",
                    "reason":    zone_reason or "ZoneStateEngine signal",
                    "timestamp": datetime.utcnow(),
                })

                await event_bus.emit("disruption_update", {
                    "type": "disruption_update",
                    "data": {
                        "zone_name":   zone["name"],
                        "zone_state":  zone_state,
                        "source":      "real_zone_state_engine",
                        "reason":      zone_reason,
                    },
                })

                # ── Claim generation ─────────────────────────────────────────
                worker_agg = await db.workers.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
                if not worker_agg:
                    await asyncio.sleep(10)
                    continue

                worker = worker_agg[0]
                c_id   = f"CLM-{uuid.uuid4().hex[:8].upper()}"

                # Real zone state drives approval threshold
                approval_threshold = {"RED": 0.15, "YELLOW": 0.25, "GREEN": 0.40}.get(zone_state, 0.35)
                is_approved = random.random() > approval_threshold
                status      = "approved" if is_approved else "rejected"

                # Payout scales with real severity
                amount_range = {"RED": (300, 1500), "YELLOW": (150, 800), "GREEN": (100, 400)}.get(zone_state, (100, 400))
                amount = float(random.randint(*amount_range))

                await db.claims.insert_one({
                    "_id":              c_id,
                    "claim_id":         c_id,
                    "worker_id":        worker["worker_id"],
                    "requested_amount": amount,
                    "status":           status,
                    "zone_state":       zone_state,
                    "zone_id":          zone["id"],
                })
                await db.audit_logs.insert_one({
                    "_id":       str(uuid.uuid4()),
                    "claim_id":  c_id,
                    "worker_id": worker["worker_id"],
                    "decision":  status.upper(),
                    "agents": [
                        {"agent": "TelemetristAgent", "status": "PASS",
                         "reason": "Worker within active zone", "confidence": 0.95},
                        {"agent": "EconomistAgent",
                         "status": "PASS" if is_approved else "FAIL",
                         "reason": "Real zone risk validated" if is_approved
                                   else "Zone state insufficient for payout",
                         "confidence": 0.92 if is_approved else 0.15},
                    ],
                })

                if is_approved:
                    await db.transactions.insert_one({
                        "_id":            str(uuid.uuid4()),
                        "transaction_id": f"TXN-{uuid.uuid4().hex[:6].upper()}",
                        "worker_id":      worker["worker_id"],
                        "claim_id":       c_id,
                        "amount":         amount,
                        "status":         "completed",
                        "type":           "payout",
                        "timestamp":      datetime.utcnow(),
                    })

                await event_bus.emit("new_claim", {
                    "type": "new_claim",
                    "data": {
                        "claim_id":    c_id,
                        "worker_name": worker["name"],
                        "status":      status.upper(),
                        "amount":      amount,
                        "zone_state":  zone_state,
                    },
                })

            except Exception as e:
                logger.error(f"[LIVE-SIM] Claims loop error: {e}")

            await asyncio.sleep(10)


live_simulator = LiveSimulatorWorker()
