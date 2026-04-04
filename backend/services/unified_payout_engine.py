"""
Unified Payout Engine - Demo-Grade Bulletproof Version
-------------------------------------------------------
Guarantees:
- EVERY RED zone triggers a payout (no silent failures)
- All asyncio.create_task calls are guarded
- Demand drop, shift insurance, and route disruption all handled
- Immediate UI_NOTIFICATION fired after every payout
"""

import time
import asyncio
import random
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from core.event_bus import event_bus
from core.logger import logger

# ── Insurance Engine Rule Constants ──────────────────────────────────────────
HOURLY_INCOME    = 300.0    # INR estimated per hour
AVG_ORDER_VALUE  = 80.0     # INR per missed order
DEDUCTIBLE       = 0.0      # Disabled for demo
COVERAGE_LIMIT   = 800.0    # Max per trigger
MIN_POOL_CONTRIBUTORS = 5    # For collective pool activation
BASE_DEMO_PAYOUT = 120.0    # Guaranteed payout when in RED zone (demo fallback)


def _safe_create_task(coro):
    """Safely schedule a coroutine as a task without crashing if no loop."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        pass  # No running event loop - skip background tasks (startup edge case)


class UnifiedPayoutEngine:
    def __init__(self):
        self.payout_history: List[Dict] = []
        self._worker_last_payout: Dict[str, float] = {}
        self._payout_active_flags: Dict[str, bool] = {}
        self.PAYOUT_COOLDOWN = 10.0   # Enforce 10s cooldown

    def init_history(self):
        self.payout_history = []
        self.clear_locks()

    def clear_locks(self):
        """Called by simulation service when a new event drops."""
        self._worker_last_payout.clear()
        self._payout_active_flags.clear()

    async def evaluate_payout_trigger(self, payload: Dict):
        """
        Core parametric payout logic.
        Called by Orchestrator Engine on PAYOUT_TRIGGER.
        
        Priority of payout reasons:
          1. Shift Guarantee (income shortfall)
          2. Demand Collapse (orders plunged)
          3. Route Disruption (delay_factor)
          4. Base Demo Payout (fallback for any RED zone)
        """
        try:
            now = time.time()
            worker = payload.get("worker", {})
            zone   = payload.get("zone", {})
            shift  = payload.get("shift")
            zone_state = payload.get("zone_state", "GREEN")
            wid = worker.get("worker_id", "UNKNOWN")

            logger.info(f"[PAYOUT] Evaluating for worker {wid} | Zone: {zone.get('id')} | State: {zone_state}")

            # ── Step 4 & 5: Lock and Cooldown System ──────────────────────────
            is_locked = self._payout_active_flags.get(wid, False)
            if is_locked:
                return

            last = self._worker_last_payout.get(wid, 0)
            if now - last < self.PAYOUT_COOLDOWN:
                return

            # Lock immediately while calculating
            self._payout_active_flags[wid] = True

            # ── 1. FRAUD CHECK (Bypassed for demo) ───────────────────────────
            is_valid = True   # Always valid in demo mode

            if not is_valid:
                return

            # ── 2. LOSS CALCULATION ──────────────────────────────────────────
            payout_amount = 0.0
            reason_type = ""
            reason_explanation = ""
            calculation_desc = ""
            shift_compensation_due = False

            # Branch A: Shift Guarantee (highest priority)
            if shift and not shift.get("compensated") and zone_state == "RED":
                expected = round(float(shift.get("expected_income", 0)), 2)
                current  = round(float(shift.get("current_earnings", 0)), 2)
                if current < expected:
                    loss = round(expected - current, 2)
                    payout_amount = loss
                    reason_type = "Shift Guarantee"
                    reason_explanation = f"Income shortfall protected for your {shift.get('name', 'shift')}"
                    calculation_desc = f"(Expected ₹{expected} − Earned ₹{current})"
                    shift_compensation_due = True
                    logger.info(f"[PAYOUT] Branch A: Shift Guarantee → ₹{payout_amount}")

            # Branch B: Demand Collapse
            if not shift_compensation_due and zone_state == "RED" and zone.get("collapse_reason") == "DEMAND":
                baseline = zone.get("baseline_orders", 250)
                actual   = zone.get("orders_per_minute", 100)
                if baseline > 0 and actual < baseline * 0.8:
                    order_loss    = int(baseline - actual)
                    drop_pct      = int((order_loss / baseline) * 100)
                    missed_approx = max(2, int(order_loss * 0.05))
                    loss = round(missed_approx * AVG_ORDER_VALUE, 2)
                    if loss > payout_amount:
                        payout_amount = loss
                        reason_type = "Demand Collapse"
                        reason_explanation = f"Orders plunged by {drop_pct}% in your zone"
                        calculation_desc = f"({missed_approx} missed deliveries × ₹{AVG_ORDER_VALUE})"
                        logger.info(f"[PAYOUT] Branch B: Demand Collapse → ₹{payout_amount}")

            # Branch C: Route/Traffic Disruption
            if not shift_compensation_due and payout_amount == 0 and zone_state in ["RED", "YELLOW"]:
                delay = float(zone.get("delay_factor", 1.0))
                if delay > 1.1:
                    time_lost_hrs = round((delay - 1.0) * 0.5, 2)
                    loss = round(time_lost_hrs * HOURLY_INCOME, 2)
                    if loss > payout_amount:
                        payout_amount = loss
                        reason_type = "Route Disruption"
                        urgency = "Severe" if zone_state == "RED" else "Moderate"
                        reason_explanation = f"{urgency} route delay ({int((delay-1)*100)}% slower than normal)"
                        calculation_desc = f"({time_lost_hrs:.2f} hrs × ₹{HOURLY_INCOME}/hr)"
                        logger.info(f"[PAYOUT] Branch C: Route Disruption → ₹{payout_amount}")

            # Branch D: Demo Guaranteed Fallback (RED zone always pays)
            if payout_amount == 0 and zone_state == "RED":
                payout_amount = round(random.uniform(80.0, BASE_DEMO_PAYOUT + 80.0), 2)
                reason_type = "Zone Disruption"
                reason_explanation = f"Severe disruption in {zone.get('name', 'your zone')} — guaranteed protection"
                calculation_desc = f"(Demo Safe Mode: ₹{payout_amount} base payout)"
                logger.info(f"[PAYOUT] Branch D: Demo Fallback → ₹{payout_amount}")

            # ── 3. INSURANCE RULES ───────────────────────────────────────────
            payout_amount = round(payout_amount, 2)

            if payout_amount <= DEDUCTIBLE:
                logger.info(f"[PAYOUT] Skipped: amount ₹{payout_amount} below deductible ({DEDUCTIBLE})")
                return

            payout_amount = min(payout_amount, COVERAGE_LIMIT)

            # ── 4. COMMIT SHIFT ──────────────────────────────────────────────
            if shift_compensation_due and shift:
                shift["compensated"] = True

            # ── 5. COLLECTIVE RISK POOL ──────────────────────────────────────
            contributors  = zone.get("pool_contributors", 0)
            current_pool  = zone.get("pool_balance", 0)
            pooled_amount = 0.0
            system_fallback = payout_amount
            pool_active = contributors >= MIN_POOL_CONTRIBUTORS

            if pool_active and current_pool > 0:
                if current_pool >= payout_amount:
                    pooled_amount   = payout_amount
                    system_fallback = 0.0
                else:
                    pooled_amount   = current_pool
                    system_fallback = round(payout_amount - current_pool, 2)

                pool_updater = payload.get("city_graph_pool_updater")
                if pool_updater and pooled_amount > 0:
                    pool_updater(zone["id"], pooled_amount)

            # ── 6. BUILD PAYOUT RECORD ───────────────────────────────────────
            if pool_active and pooled_amount == payout_amount:
                source_label = "Active Risk Pool"
            elif system_fallback == payout_amount:
                source_label = "System Reserve"
            else:
                source_label = "Risk Pool + System Reserve"

            ui_msg = (
                f"₹{payout_amount} credited — {reason_explanation} | "
                f"{calculation_desc} | Source: {source_label}"
            )

            payout_record = {
                "id":                 str(uuid.uuid4()),
                "type":               "PAYOUT",
                "msg":                ui_msg,
                "amount":             payout_amount,
                "worker_id":          wid,
                "name":               worker.get("name", "Unknown"),
                "company":            worker.get("company", "Unknown"),
                "pool_contribution":  pooled_amount,
                "system_fallback":    system_fallback,
                "zone":               zone_state,
                "zone_id":            zone.get("id", ""),
                "reason":             reason_type,
                "calculation_details": calculation_desc,
                "pool_used":          pooled_amount > 0,
                "timestamp":          datetime.utcnow().isoformat(),
            }

            # ── 7. COMMIT TO WORKER STATE ────────────────────────────────────
            self._worker_last_payout[wid] = now
            # Leave the active flag as TRUE until it expires or gets cleared
            # (In a real system you'd use a background timer, here we just use cooldown)
            
            worker["total_protection"] = round(float(worker.get("total_protection", 0)) + payout_amount, 2)
            worker["last_payout"] = payout_amount

            # ── 8. UPDATE HISTORY ────────────────────────────────────────────
            self.payout_history.insert(0, payout_record)
            if len(self.payout_history) > 50:
                self.payout_history.pop()

            logger.info(f"[PAYOUT] ✅ SUCCESS → {wid}: ₹{payout_amount} ({reason_type})")

            # ── 9. EMIT EVENTS ───────────────────────────────────────────────
            await event_bus.emit("PAYOUT_SUCCESS", payout_record)
            await event_bus.emit("UI_NOTIFICATION", {
                "type":                "PAYOUT",
                "id":                  payout_record["id"],
                "worker_id":           wid,
                "name":                worker.get("name", "Worker"),
                "company":             worker.get("company", ""),
                "amount":              payout_amount,
                "reason":              reason_type,
                "reason_explanation":  reason_explanation,
                "calculation_details": calculation_desc,
                "source":              source_label,
                "zone":                zone_state,
                "zone_id":             zone.get("id", ""),
                "pool_used":           pooled_amount > 0,
                "pool_contribution":   pooled_amount,
                "system_fallback":     system_fallback,
                "msg":                 ui_msg,
                "timestamp":           payout_record["timestamp"],
            })

        except Exception as e:
            # Release lock safely on error
            if "wid" in locals():
                self._payout_active_flags[wid] = False

            logger.error(f"[PAYOUT] EXCEPTION in evaluate_payout_trigger: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Once event finishes, we disable the active lock but keep the time lock strictly intact!
            if "wid" in locals():
                self._payout_active_flags[wid] = False


# Singleton
payout_engine = UnifiedPayoutEngine()

# Subscribe to Orchestrator Payout Trigger
event_bus.subscribe("PAYOUT_TRIGGER", payout_engine.evaluate_payout_trigger)
