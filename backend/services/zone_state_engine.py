"""
Zone State Engine
-----------------
The SINGLE source of truth for all zone state decisions.

Every zone's color (GREEN / YELLOW / RED) is computed ONLY from
real-world signals. No random logic. No simulation triggers.

Signal sources:
  1. weather_score   — OpenWeatherMap / Open-Meteo (per-zone coords)
  2. traffic_score   — OSRM free routing API (delay %)
  3. disruption_score — NLP engine on NewsAPI + GDELT articles
  4. demand_score    — MongoDB orders vs baseline

Priority override logic:
  IF disruption_score == RED  → RED  (strike/protest always overrides)
  ELSE IF weather == RED OR traffic == RED → RED
  ELSE IF weather == YELLOW OR traffic == YELLOW OR demand == RED → YELLOW
  ELSE → GREEN
"""

import asyncio
import time
from typing import Dict, Optional
from datetime import datetime

from core.logger import logger
from core.event_bus import event_bus
from services.city_graph_service import city_graph, ZONE_DEFINITIONS

# ── Signal score thresholds ───────────────────────────────────────────────────

WEATHER_THRESHOLDS = {
    "heavy":    ("RED",    0.90),
    "moderate": ("YELLOW", 0.55),
    "light":    ("YELLOW", 0.35),
    "none":     ("GREEN",  0.08),
}

TRAFFIC_THRESHOLDS = {
    # delay_percentage → (state, score)
    "red":    (50,  "RED",    0.90),
    "yellow": (20,  "YELLOW", 0.55),
    "green":  (0,   "GREEN",  0.10),
}

DEMAND_THRESHOLDS = {
    # ratio current/baseline → (state, score)
    "red":    0.50,   # > 50% drop
    "yellow": 0.20,   # 20-50% drop
}

DISRUPTION_HIGH_TYPES  = {"strike", "riot", "shutdown", "blockade", "bandh", "curfew", "violence"}
DISRUPTION_MED_TYPES   = {"protest", "demonstration", "march", "union action"}


class ZoneStateEngine:
    """
    Singleton engine that holds the latest per-zone signal scores
    and recomputes zone states whenever any signal updates.
    """

    def __init__(self):
        # Latest signal scores per zone_id
        self._weather_scores:    Dict[str, Dict] = {}   # zone_id → {state, score, label, ts}
        self._traffic_scores:    Dict[str, Dict] = {}
        self._disruption_scores: Dict[str, Dict] = {}
        self._demand_scores:     Dict[str, Dict] = {}

        # Previous states for change-detection
        self._prev_states: Dict[str, str] = {}

        # Bootstrap all zones as UNKNOWN so first real data triggers a proper broadcast
        for z in ZONE_DEFINITIONS:
            zid = z["id"]
            self._prev_states[zid] = "UNKNOWN"
            empty = {"state": "GREEN", "score": 0.0, "label": "Initialising...", "ts": 0.0}
            self._weather_scores[zid]    = dict(empty)
            self._traffic_scores[zid]    = dict(empty)
            self._disruption_scores[zid] = dict(empty)
            self._demand_scores[zid]     = dict(empty)

    # ── Signal ingestion methods ──────────────────────────────────────────────

    def update_weather_score(self, zone_id: str, intensity: str, rain_mm: float,
                              condition: str, source: str = "unknown"):
        state, score = WEATHER_THRESHOLDS.get(intensity, ("YELLOW", 0.5))
        label = f"{condition} ({rain_mm:.1f}mm/hr)"
        self._weather_scores[zone_id] = {
            "state": state, "score": score, "label": label,
            "intensity": intensity, "rain_mm": rain_mm, "source": source,
            "ts": time.time()
        }
        logger.debug(f"[ZSE] Weather score {zone_id}: {state} ({intensity}, {rain_mm}mm) via {source}")

    def update_traffic_score(self, zone_id: str, delay_pct: float, delay_mins: float):
        if delay_pct >= 50:
            state, score = "RED", 0.90
        elif delay_pct >= 20:
            state, score = "YELLOW", 0.55
        else:
            state, score = "GREEN", 0.10
        label = f"Traffic delay {delay_pct:.0f}% ({delay_mins:.0f} min extra)"
        self._traffic_scores[zone_id] = {
            "state": state, "score": score, "label": label,
            "delay_pct": delay_pct, "delay_mins": delay_mins,
            "ts": time.time()
        }
        logger.debug(f"[ZSE] Traffic score {zone_id}: {state} ({delay_pct:.0f}% delay)")

    def update_disruption_score(self, zone_id: str, event_type: str,
                                 severity: str, confidence: float, source_text: str = ""):
        if event_type in DISRUPTION_HIGH_TYPES:
            state, score = "RED", min(0.95, 0.70 + confidence * 0.25)
        elif event_type in DISRUPTION_MED_TYPES:
            state, score = "YELLOW", min(0.70, 0.45 + confidence * 0.20)
        else:
            state, score = "GREEN", 0.05
        label = f"{event_type.title()} detected (conf: {confidence:.0%})"
        self._disruption_scores[zone_id] = {
            "state": state, "score": score, "label": label,
            "event_type": event_type, "severity": severity,
            "confidence": confidence, "source_text": source_text[:100],
            "ts": time.time()
        }
        logger.info(f"[ZSE] Disruption score {zone_id}: {state} ({event_type}, conf={confidence:.2f})")

    def clear_disruption(self, zone_id: str):
        """Call when a disruption event expires or is resolved."""
        self._disruption_scores[zone_id] = {
            "state": "GREEN", "score": 0.0,
            "label": "No disruptions", "ts": time.time()
        }

    def update_demand_score(self, zone_id: str, current_rate: float, baseline_rate: float):
        if baseline_rate <= 0:
            ratio = 1.0
        else:
            ratio = current_rate / baseline_rate

        drop_pct = max(0.0, (1.0 - ratio) * 100)

        if ratio < (1 - DEMAND_THRESHOLDS["red"]):      # > 50% drop
            state, score = "RED", 0.85
        elif ratio < (1 - DEMAND_THRESHOLDS["yellow"]):  # 20-50% drop
            state, score = "YELLOW", 0.50
        else:
            state, score = "GREEN", 0.10

        label = f"Demand {'-' if drop_pct > 0 else '+'}{drop_pct:.0f}% vs baseline"
        self._demand_scores[zone_id] = {
            "state": state, "score": score, "label": label,
            "current_rate": current_rate, "baseline_rate": baseline_rate,
            "drop_pct": drop_pct, "ts": time.time()
        }
        logger.debug(f"[ZSE] Demand score {zone_id}: {state} ({drop_pct:.0f}% drop)")

    # ── Core decision engine ──────────────────────────────────────────────────

    def compute_zone_state(self, zone_id: str) -> Dict:
        """
        Compute the final zone state from all signals.
        Returns the decision with full signal breakdown.
        """
        w = self._weather_scores.get(zone_id, {})
        t = self._traffic_scores.get(zone_id, {})
        d = self._disruption_scores.get(zone_id, {})
        dem = self._demand_scores.get(zone_id, {})

        w_state  = w.get("state", "GREEN")
        t_state  = t.get("state", "GREEN")
        d_state  = d.get("state", "GREEN")
        dem_state = dem.get("state", "GREEN")

        # ── Priority Logic ────────────────────────────────────────────────────
        if d_state == "RED":
            final_state  = "RED"
            final_score  = d.get("score", 0.85)
            driving_reason = f"Disruption: {d.get('label', 'Strike/Protest detected')}"
        elif w_state == "RED" or t_state == "RED":
            final_state = "RED"
            final_score = max(w.get("score", 0), t.get("score", 0))
            if w_state == "RED":
                driving_reason = f"Weather: {w.get('label', 'Heavy rain')}"
            else:
                driving_reason = f"Traffic: {t.get('label', 'Severe congestion')}"
        elif w_state == "YELLOW" or t_state == "YELLOW" or d_state == "YELLOW" or dem_state == "RED":
            final_state  = "YELLOW"
            final_score  = max(w.get("score", 0), t.get("score", 0),
                               d.get("score", 0), dem.get("score", 0))
            if dem_state == "RED":
                driving_reason = f"Demand: {dem.get('label', 'Severe order drop')}"
            elif w_state == "YELLOW":
                driving_reason = f"Weather: {w.get('label', 'Rain')}"
            elif t_state == "YELLOW":
                driving_reason = f"Traffic: {t.get('label', 'Delay')}"
            else:
                driving_reason = f"Disruption: {d.get('label', 'Protest')}"
        else:
            final_state  = "GREEN"
            final_score  = max(w.get("score", 0.05), 0.05)
            driving_reason = "All systems nominal"

        return {
            "zone_id": zone_id,
            "state": final_state,
            "risk_score": round(final_score, 3),
            "reason": driving_reason,
            "signals": {
                "weather":    w,
                "traffic":    t,
                "disruption": d,
                "demand":     dem,
            },
            "computed_at": datetime.utcnow().isoformat(),
        }

    async def recompute_all(self, source: str = "scheduler") -> Dict[str, str]:
        """
        Recompute states for ALL zones, apply to city_graph, emit events for changes.
        Returns dict of zone_id → new_state.
        """
        results = {}
        changed_zones = []

        for z in ZONE_DEFINITIONS:
            zid = z["id"]
            decision = self.compute_zone_state(zid)
            new_state = decision["state"]
            results[zid] = new_state

            # Apply to the city graph (source of truth for the rest of the system)
            city_graph.update_zone_from_engine(
                zone_id=zid,
                state=new_state,
                risk_score=decision["risk_score"],
                reason=decision["reason"],
                signals=decision["signals"],
            )

            # Detect state changes
            prev = self._prev_states.get(zid, "UNKNOWN")
            if prev != new_state:
                changed_zones.append({
                    "zone_id": zid,
                    "zone_name": z["name"],
                    "prev_state": prev,
                    "new_state": new_state,
                    "decision": decision,
                })
                self._prev_states[zid] = new_state

        # Emit change events
        for change in changed_zones:
            logger.info(
                f"[ZSE] ZONE_STATE_CHANGED: {change['zone_id']} ({change['zone_name']}) "
                f"{change['prev_state']} → {change['new_state']} | {change['decision']['reason']}"
            )
            await event_bus.emit("ZONE_STATE_CHANGED", {
                "type": "zone_signal_update",
                "zone_id": change["zone_id"],
                "zone_name": change["zone_name"],
                "prev_state": change["prev_state"],
                "new_state": change["new_state"],
                "signals": change["decision"]["signals"],
                "reason": change["decision"]["reason"],
            })

        # Always emit UI_SYNC so WebSocket clients get the latest map
        await event_bus.emit("UI_SYNC")

        if changed_zones:
            logger.info(f"[ZSE] Recomputed {len(ZONE_DEFINITIONS)} zones via [{source}] → "
                        f"{len(changed_zones)} state change(s)")
        else:
            logger.debug(f"[ZSE] Recomputed {len(ZONE_DEFINITIONS)} zones via [{source}] → no changes")

        return results

    def get_all_signals(self) -> Dict:
        """Return current signal snapshot for all zones (used by REST API)."""
        result = {}
        for z in ZONE_DEFINITIONS:
            zid = z["id"]
            result[zid] = {
                "zone_id": zid,
                "zone_name": z["name"],
                "weather":    self._weather_scores.get(zid, {}),
                "traffic":    self._traffic_scores.get(zid, {}),
                "disruption": self._disruption_scores.get(zid, {}),
                "demand":     self._demand_scores.get(zid, {}),
                "computed":   self.compute_zone_state(zid),
            }
        return result


# Module-level singleton
zone_state_engine = ZoneStateEngine()
