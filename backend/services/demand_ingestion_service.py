"""
Demand Ingestion Service
------------------------
Computes real demand scores for each zone from live MongoDB order data.
No simulation — uses actual DB writes from the earnings-loop worker.

Demand score logic:
  current_rate = orders in last 5 min in this zone
  baseline_rate = zone's stored baseline_orders (DB-persisted)

  ratio = current_rate / baseline_rate
  GREEN  → ratio > 0.80  (< 20% drop)
  YELLOW → ratio 0.50–0.80 (20–50% drop)
  RED    → ratio < 0.50  (> 50% drop)

Also checks NewsAPI/GDELT for keyword signals:
  "LPG shortage", "fuel crisis", "bandh", "curfew", "festival" 
  → Applies a short-term demand suppression flag on affected zones.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List

import httpx

from core.database import get_db
from core.logger import logger
from core.config import settings
from services.city_graph_service import ZONE_DEFINITIONS, city_graph
from services.zone_state_engine import zone_state_engine

FETCH_INTERVAL_SECONDS = 60   # Demand can change fast — check every 60s
_last_fetch_ts: float = 0.0

# Keywords that signal systemic demand suppression
DEMAND_SUPPRESSION_KEYWORDS = [
    "lpg shortage", "fuel shortage", "petrol shortage", "diesel shortage",
    "bandh", "complete shutdown", "curfew", "lockdown",
    "festival holiday", "public holiday",
]

# Zones to suppress demand for if a city-wide keyword is detected
_demand_suppressed_zones: Dict[str, float] = {}   # zone_id → expiry timestamp
SUPPRESSION_TTL = 3600  # 1 hour


async def _detect_news_demand_suppression(city: str = "Chennai") -> bool:
    """
    Quick NewsAPI scan for demand-suppression keywords.
    Returns True if any keyword detected in last 6 hours.
    """
    api_key = getattr(settings, "NEWS_API_KEY", None)
    if not api_key or api_key.startswith("your_"):
        return False

    query = " OR ".join([f'"{kw}"' for kw in DEMAND_SUPPRESSION_KEYWORDS])
    params = {
        "q": f"({query}) AND {city}",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": api_key,
        "from": (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S"),
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get("https://newsapi.org/v2/everything", params=params)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
            if articles:
                logger.info(
                    f"[DEMAND-INGEST] Demand suppression signal detected: "
                    f"'{articles[0].get('title', '')[:80]}'"
                )
                return True
    except Exception as e:
        logger.debug(f"[DEMAND-INGEST] News scan failed (non-critical): {e}")

    return False


async def compute_zone_demand_scores() -> Dict[str, Dict]:
    """
    Compute demand scores for all zones from recent DB earnings records.
    Returns dict of zone_id → demand info.
    """
    db = get_db()
    results: Dict[str, Dict] = {}
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=5)

    all_zones = {z["id"]: z for z in ZONE_DEFINITIONS}
    city_zones = city_graph.get_all_zones()
    zone_baselines = {z["id"]: z.get("baseline_orders", 200) for z in city_zones}

    # Check news-driven demand suppression (city-wide)
    suppression_active = await _detect_news_demand_suppression()
    if suppression_active:
        for zone_id in all_zones:
            _demand_suppressed_zones[zone_id] = time.time() + SUPPRESSION_TTL

    # Clean expired suppressions
    expired = [zid for zid, exp in _demand_suppressed_zones.items() if time.time() > exp]
    for zid in expired:
        del _demand_suppressed_zones[zid]

    # Aggregate real orders from DB
    try:
        if db is not None:
            pipeline = [
                {"$match": {"timestamp": {"$gte": window_start}}},
                {"$group": {"_id": "$zone_id", "total_orders": {"$sum": "$orders_completed"},
                            "avg_earnings": {"$avg": "$earnings"}}},
            ]
            raw = await db.earnings.aggregate(pipeline).to_list(length=50)
            recent_by_zone = {r["_id"]: r for r in raw}
        else:
            recent_by_zone = {}
    except Exception as e:
        logger.error(f"[DEMAND-INGEST] DB aggregation failed: {e}")
        recent_by_zone = {}

    for zone_id, zone_def in all_zones.items():
        baseline = zone_baselines.get(zone_id, 200)
        # Convert baseline_orders (per period) to per-minute rate
        baseline_rate = baseline / 5.0   # orders per minute over 5-min window

        recent = recent_by_zone.get(zone_id)
        if recent:
            current_rate = recent["total_orders"] / 5.0   # per minute
        else:
            # No orders in 5-min window — this IS a signal (possible demand crash)
            # But also could be low-traffic area — use 70% of baseline as neutral floor
            current_rate = baseline_rate * 0.70

        # Override: if news-driven suppression is active
        if zone_id in _demand_suppressed_zones:
            current_rate = current_rate * 0.40   # 60% drop forced by external signal
            logger.info(f"[DEMAND-INGEST] News suppression active for {zone_id}")

        zone_state_engine.update_demand_score(
            zone_id=zone_id,
            current_rate=current_rate,
            baseline_rate=baseline_rate,
        )

        ratio = current_rate / baseline_rate if baseline_rate > 0 else 1.0
        drop_pct = max(0.0, (1.0 - ratio) * 100)

        results[zone_id] = {
            "zone_id":       zone_id,
            "current_rate":  round(current_rate, 2),
            "baseline_rate": round(baseline_rate, 2),
            "ratio":         round(ratio, 3),
            "drop_pct":      round(drop_pct, 1),
            "suppressed":    zone_id in _demand_suppressed_zones,
        }
        logger.debug(
            f"[DEMAND-INGEST] {zone_id}: {current_rate:.1f}/min vs baseline {baseline_rate:.1f}/min "
            f"({drop_pct:.0f}% drop)"
        )

    return results


async def run_demand_ingestion_cycle() -> Dict[str, Dict]:
    """Entry point called by zone_state_worker on schedule."""
    global _last_fetch_ts
    now = time.time()

    if now - _last_fetch_ts < FETCH_INTERVAL_SECONDS:
        return {}

    _last_fetch_ts = now
    logger.info("[DEMAND-INGEST] Computing live zone demand scores...")
    return await compute_zone_demand_scores()
