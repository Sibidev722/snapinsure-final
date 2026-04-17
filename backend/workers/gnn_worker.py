import asyncio
import logging
from datetime import datetime, timezone
from core.database import get_db
from services.city_graph_service import city_graph, ROAD_EDGES
from services.gnn_decision_engine import gnn_engine
from services.xai_explainer import generate_explanation

logger = logging.getLogger(__name__)

# ── Feature manifest (order matters — must match NUM_FEATURES in engine) ──────
#   Index 0: weather        — city-wide weather disruption intensity [0, 1]
#   Index 1: strikes        — binary social disruption flag per zone  [0, 1]
#   Index 2: earnings       — min-max normalised earning density      [0, 1]
#   Index 3: time_of_day    — hour of day normalised to [0, 1]        [0, 1]
#   Index 4: day_of_week    — weekday normalised to [0, 1]            [0, 1]
FEATURE_NAMES = ["weather", "strikes", "earnings", "time_of_day", "day_of_week"]


def _normalise_hour(hour: int) -> float:
    """Map hour ∈ [0, 23] → [0.0, 1.0] linearly.
    0 h → 0.0,  12 h → 0.522,  23 h → 1.0
    """
    return hour / 23.0


def _normalise_weekday(weekday: int) -> float:
    """Map weekday ∈ [0, 6] (Mon=0 … Sun=6) → [0.0, 1.0] linearly.
    Monday → 0.0,  Sunday → 1.0
    """
    return weekday / 6.0


def _minmax_scale(values: dict, *, eps: float = 1e-8) -> dict:
    """
    Min-max normalise a {key: float} mapping across all values.

    Formula:  scaled = (v - min) / (max - min + eps)

    The eps term prevents ZeroDivisionError when all values are equal
    (e.g. first tick where every zone has 0 earnings).  The result is
    always in [0.0, 1.0].
    """
    raw = list(values.values())
    v_min = min(raw)
    v_max = max(raw)
    denom = (v_max - v_min) + eps          # guaranteed > 0
    return {k: (v - v_min) / denom for k, v in values.items()}


class GNNWorker:
    """
    Autonomous GNN Intelligence Worker.

    Builds a 5-feature node matrix every tick:
      [weather, strikes, earnings(min-max), time_of_day, day_of_week]
    Runs graph-attention inference and stores enriched predictions in MongoDB.
    """
    def __init__(self, interval_seconds: int = 10):
        self.interval = interval_seconds
        self.is_running = False
        self._task = None
        # Z1-Z9 to 0-8 mapping for GNN tensor indices
        self.zone_map = {f"Z{i}": i-1 for i in range(1, 10)}
        self.edge_indices = []
        for src, dst in ROAD_EDGES:
            if src in self.zone_map and dst in self.zone_map:
                self.edge_indices.append((self.zone_map[src], self.zone_map[dst]))

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[GNNWorker] Started (Interval: {self.interval}s)")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[GNNWorker] Stopped")

    async def _run_loop(self):
        while self.is_running:
            try:
                await self._compute_predictions()
            except Exception as e:
                logger.error(f"[GNNWorker] Error in loop: {e}")
            
            await asyncio.sleep(self.interval)

    async def _compute_predictions(self):
        db = get_db()
        if db is None:
            return

        # ── Feature 0: Weather ──────────────────────────────────────────────────
        # Source: weather_state collection (updated by weather_poller every 5 min).
        # Value:  demand_multiplier - 1.0  clipped to [0, 1].
        #   multiplier = 1.0 → no impact (delta = 0.0 → LOW)
        #   multiplier = 2.0 → severe impact (delta = 1.0 → HIGH)
        weather_impact: float = 0.0
        weather_doc = await db.weather_state.find_one({"city": "Chennai"})
        if weather_doc and "impact" in weather_doc:
            raw_multiplier = weather_doc["impact"].get("demand_multiplier", 1.0)
            weather_impact = min(max(raw_multiplier - 1.0, 0.0), 1.0)

        # ── Feature 1: Strikes (per-zone binary flag) ───────────────────────────
        # Source: real_events collection, status == "active".
        # Value:  1.0 if ≥1 active social event in zone, else 0.0 (binary).
        strike_counts: dict[str, float] = {z_id: 0.0 for z_id in self.zone_map}
        active_events = await db.real_events.find({"status": "active"}).to_list(length=100)
        for ev in active_events:
            z_id = ev.get("zone_id")
            if z_id in strike_counts:
                strike_counts[z_id] = 1.0  # binary: presence of any active event

        # ── Feature 2: Historical Earning Density (min-max across all nodes) ────
        # Source: workers collection, field = total_protection (cumulative earnings).
        # Aggregation: sum per zone → cross-zone min-max normalisation.
        #
        # Why min-max instead of /max?  Min-max preserves the *relative spread*
        # between zones.  A zone with 0 earnings stays 0.0 only if *all* zones
        # have 0 earnings — in that edge case eps prevents ZeroDivisionError and
        # all zones get 0.0 (uniform), which is correct.
        raw_earnings: dict[str, float] = {z_id: 0.0 for z_id in self.zone_map}
        workers = await db.workers.find({}, {"zone_id": 1, "total_protection": 1}).to_list(length=1000)
        for w in workers:
            z_id = w.get("zone_id")
            if z_id in raw_earnings:
                # Accumulate — a zone with more workers accrues a higher density
                raw_earnings[z_id] += float(w.get("total_protection", 0.0))

        # Apply safe min-max scaling with eps guard → all values in [0.0, 1.0]
        zone_earnings: dict[str, float] = _minmax_scale(raw_earnings)

        # ── Features 3 & 4: Temporal (shared across all nodes in this tick) ─────
        # Source: wall-clock UTC time at the moment of inference.
        # Rationale: shift patterns strongly influence both demand and risk.
        #   Morning rush / lunch / evening rush → higher demand → higher risk.
        #   Weekends (≥5) → different dynamics than weekdays.
        #
        # Normalisation:
        #   time_of_day  = hour / 23          → [0.0, 1.0]  (0 h = 0.0, 23 h = 1.0)
        #   day_of_week  = weekday / 6        → [0.0, 1.0]  (Mon = 0.0, Sun = 1.0)
        now_utc          = datetime.now(tz=timezone.utc)
        time_of_day_norm = _normalise_hour(now_utc.hour)         # float ∈ [0, 1]
        day_of_week_norm = _normalise_weekday(now_utc.weekday())  # float ∈ [0, 1]

        # ── Assemble 5-feature node matrix ──────────────────────────────────────
        # Each dict entry maps feature_name → scalar so the GNN engine and XAI
        # explainer can reference features by name rather than index position.
        gnn_zones = []
        for i in range(1, 10):
            z_id = f"Z{i}"
            gnn_zones.append({
                "id":          z_id,
                # --- signal features (zone-specific) ---
                "weather":     weather_impact,           # same for all zones (city-wide)
                "strikes":     strike_counts[z_id],      # zone-specific binary flag
                "earnings":    zone_earnings[z_id],      # min-max normalised density
                # --- temporal features (tick-specific, same for all zones) ---
                "time_of_day": time_of_day_norm,         # hour/23
                "day_of_week": day_of_week_norm,         # weekday/6
            })

        logger.debug(
            "[GNNWorker] Feature tick | "
            f"weather={weather_impact:.3f} "
            f"time={time_of_day_norm:.3f} ({now_utc.hour}h) "
            f"day={day_of_week_norm:.3f} ({now_utc.strftime('%a')}) "
            f"strikes_active={int(sum(strike_counts.values()))} "
            f"earnings_range=[{min(raw_earnings.values()):.1f}, {max(raw_earnings.values()):.1f}]"
        )

        # ── Perform Inference ────────────────────────────────────────────────────
        predictions = gnn_engine.predict_and_explain(gnn_zones, self.edge_indices)

        # ── Enrich predictions with structured XAI explanations ─────────────────
        # Build a zone_id → gnn_zone dict for O(1) feature lookup
        zone_feature_map = {z["id"]: z for z in gnn_zones}

        # Build a zone_id → list[neighbour_id] from edge index pairs
        zone_neighbours: dict = {f"Z{i}": [] for i in range(1, 10)}
        inv_zone_map = {v: k for k, v in self.zone_map.items()}
        for src_idx, dst_idx in self.edge_indices:
            src_id = inv_zone_map.get(src_idx, f"N{src_idx}")
            dst_id = inv_zone_map.get(dst_idx, f"N{dst_idx}")
            zone_neighbours.setdefault(src_id, []).append(dst_id)

        enriched: list = []
        for pred in predictions:
            zone_id  = pred.get("zone", "")
            conf     = pred.get("confidence", 0.5)
            z_feats  = zone_feature_map.get(zone_id, {})
            nids     = zone_neighbours.get(zone_id, [])

            # Attention weights from pred (may be None in fallback mode)
            raw_attn = pred.get("attention")  # float | None
            if raw_attn is not None and nids:
                # Distribute node-level scalar attention uniformly across neighbours
                attn_input = [{"node_id": n, "weight": raw_attn / max(len(nids), 1)}
                              for n in nids]
            else:
                attn_input = []

            xai = generate_explanation(
                node_features={
                    "weather":     z_feats.get("weather",     0.0),
                    "strikes":     z_feats.get("strikes",     0.0),
                    "earnings":    z_feats.get("earnings",    0.0),
                    "time_of_day": z_feats.get("time_of_day", 0.0),
                    "day_of_week": z_feats.get("day_of_week", 0.0),
                },
                attention_weights=attn_input,
                feature_names=FEATURE_NAMES,
                risk_score=conf,
                zone_id=zone_id,
                neighbor_ids=nids,
                top_k=3,
            )

            enriched.append({
                **pred,
                "xai": {
                    "top_features":  [{"name": f.name, "label": f.label,
                                       "value": f.value, "importance": f.importance,
                                       "direction": f.direction}
                                      for f in xai.top_features],
                    "top_neighbors": [{"node_id": n.node_id, "attention": n.attention,
                                       "rank": n.rank, "label": n.label}
                                      for n in xai.top_neighbors],
                    "explanation":   xai.explanation,
                    "risk_level":    xai.risk_level,
                    "parts":         xai.explanation_parts,
                },
            })

        # ── Persist enriched snapshot to MongoDB ─────────────────────────────────
        if enriched:
            snapshot = {
                "timestamp":            datetime.utcnow().isoformat(),
                "predictions":          enriched,
                "weather_intensity":    weather_impact,
                "active_strikes_count": len(active_events),
            }
            await db.gnn_predictions.update_one(
                {"type": "latest_snapshot"},
                {"$set": snapshot},
                upsert=True
            )

gnn_worker = GNNWorker()
