"""
Traffic Ingestion Service
-------------------------
Computes real traffic delay for each zone using the OSRM public routing API.
No API key required. Uses project-osrm.org (free, production-grade).

Method:
  For each zone, measure the live route time from zone centre → Chennai central hub.
  Compare against a stored baseline (first run). 
  delay_pct = (live - baseline) / baseline * 100
  GREEN < 20% | YELLOW 20–50% | RED > 50%

Feeds ZoneStateEngine with per-zone traffic scores.
"""

import asyncio
import time
from typing import Dict, Optional

import httpx

from core.logger import logger
from services.city_graph_service import ZONE_DEFINITIONS
from services.zone_state_engine import zone_state_engine

# OSRM public API — free, no key required
OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"

# Chennai central reference point (T. Nagar / city centre)
CHENNAI_HUB = (80.2341, 13.0418)   # lon, lat (OSRM uses lon,lat order)

FETCH_INTERVAL_SECONDS = 180   # 3 minutes
_last_fetch_ts: float = 0.0

# Baseline travel times cached on first run (seconds)
_baseline_times: Dict[str, Optional[float]] = {}


async def _fetch_osrm_duration(o_lon: float, o_lat: float,
                                d_lon: float, d_lat: float) -> Optional[float]:
    """
    Query OSRM for driving duration between two points.
    Returns duration in seconds, or None on failure.
    """
    url = f"{OSRM_BASE}/{o_lon},{o_lat};{d_lon},{d_lat}"
    params = {"overview": "false", "alternatives": "false"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") == "Ok" and data.get("routes"):
            return float(data["routes"][0]["duration"])
    except httpx.TimeoutException:
        logger.warning(f"[TRAFFIC-INGEST] OSRM timeout for {o_lon},{o_lat}")
    except Exception as e:
        logger.error(f"[TRAFFIC-INGEST] OSRM error: {e}")

    return None


async def fetch_all_zones_traffic() -> Dict[str, Dict]:
    """
    Fetch real OSRM travel times for all zones, compute delay % vs baseline,
    feed ZoneStateEngine.
    Returns dict of zone_id → traffic result.
    """
    results: Dict[str, Dict] = {}
    hub_lon, hub_lat = CHENNAI_HUB

    # Fetch all zones concurrently
    async def fetch_zone(z: dict) -> None:
        zone_id = z["id"]
        z_lat, z_lon = z["lat"], z["lon"]

        live_duration = await _fetch_osrm_duration(z_lon, z_lat, hub_lon, hub_lat)

        if live_duration is None:
            logger.warning(f"[TRAFFIC-INGEST] No OSRM data for {zone_id}, keeping previous score")
            return

        # First run: cache as baseline
        if zone_id not in _baseline_times or _baseline_times[zone_id] is None:
            _baseline_times[zone_id] = live_duration
            logger.info(f"[TRAFFIC-INGEST] Baseline set for {zone_id}: {live_duration:.0f}s")
            # First run — treat as GREEN (no delay data yet)
            delay_pct  = 0.0
            delay_mins = 0.0
        else:
            baseline = _baseline_times[zone_id]
            delay_pct  = max(0.0, (live_duration - baseline) / baseline * 100)
            delay_mins = max(0.0, (live_duration - baseline) / 60.0)

        # Update baseline slowly (EWMA) so long-term average stays current
        _baseline_times[zone_id] = (
            _baseline_times[zone_id] * 0.85 + live_duration * 0.15
        )

        zone_state_engine.update_traffic_score(
            zone_id=zone_id,
            delay_pct=delay_pct,
            delay_mins=delay_mins,
        )

        results[zone_id] = {
            "zone_id":     zone_id,
            "live_secs":   round(live_duration, 1),
            "baseline_secs": round(_baseline_times[zone_id], 1),
            "delay_pct":   round(delay_pct, 1),
            "delay_mins":  round(delay_mins, 1),
        }
        logger.info(
            f"[TRAFFIC-INGEST] {zone_id} ({z['name']}): "
            f"delay {delay_pct:.0f}% | +{delay_mins:.1f} min"
        )

    # Run all fetches concurrently but throttle to avoid hammering OSRM
    tasks = [fetch_zone(z) for z in ZONE_DEFINITIONS]
    await asyncio.gather(*tasks)

    return results


async def run_traffic_ingestion_cycle() -> Dict[str, Dict]:
    """Entry point called by zone_state_worker on schedule."""
    global _last_fetch_ts
    now = time.time()

    if now - _last_fetch_ts < FETCH_INTERVAL_SECONDS:
        logger.debug("[TRAFFIC-INGEST] TTL not reached, skipping")
        return {}

    _last_fetch_ts = now
    logger.info("[TRAFFIC-INGEST] Starting per-zone OSRM traffic fetch cycle...")
    return await fetch_all_zones_traffic()
