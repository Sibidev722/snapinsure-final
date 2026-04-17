"""
Weather Ingestion Service
-------------------------
Fetches real-time weather for EVERY zone using its actual geo-coordinates.
Each zone (Z1–Z9 across Chennai) may experience different rainfall intensity,
so we query per-zone lat/lon instead of a single city-wide call.

Uses WeatherService (OWM primary, Open-Meteo fallback, 5-min cache).
Feeds ZoneStateEngine with per-zone weather scores.
"""

import asyncio
import time
from typing import Dict

from core.logger import logger
from services.city_graph_service import ZONE_DEFINITIONS
from services.weather_service import weather_service
from services.zone_state_engine import zone_state_engine

FETCH_INTERVAL_SECONDS = 300   # 5 minutes (respects OWM free tier)
_last_fetch_ts: float = 0.0


async def fetch_all_zones_weather() -> Dict[str, Dict]:
    """
    Fetch real weather data for each zone using its lat/lon coordinates.
    Returns a dict of zone_id → weather payload.
    Feeds zone_state_engine with the results.
    """
    results: Dict[str, Dict] = {}

    # We stagger requests slightly to avoid bursting OWM (free tier: 60 req/min)
    for z in ZONE_DEFINITIONS:
        zone_id = z["id"]
        try:
            weather = await weather_service.get_weather_by_coords(
                lat=z["lat"],
                lon=z["lon"],
                label=f"{z['name']} ({zone_id})",
            )

            # Push into zone state engine
            zone_state_engine.update_weather_score(
                zone_id=zone_id,
                intensity=weather["intensity"],
                rain_mm=weather["rainfall_mm"],
                condition=weather["condition"],
                source=weather.get("source", "unknown"),
            )

            results[zone_id] = weather
            logger.info(
                f"[WEATHER-INGEST] {zone_id} ({z['name']}): "
                f"{weather['intensity'].upper()} | {weather['rainfall_mm']}mm | {weather['condition']}"
            )

        except Exception as e:
            logger.error(f"[WEATHER-INGEST] Failed for zone {zone_id}: {e}")

        # Small stagger between zone fetches (OWM cache means this is mostly free)
        await asyncio.sleep(0.2)

    return results


async def run_weather_ingestion_cycle() -> Dict[str, Dict]:
    """
    Entry point called by zone_state_worker on schedule.
    Respects internal TTL to avoid redundant OWM calls.
    """
    global _last_fetch_ts
    now = time.time()

    if now - _last_fetch_ts < FETCH_INTERVAL_SECONDS:
        remaining = int(FETCH_INTERVAL_SECONDS - (now - _last_fetch_ts))
        logger.debug(f"[WEATHER-INGEST] Cache still valid — skipping fetch ({remaining}s remaining)")
        return {}

    _last_fetch_ts = now
    logger.info("[WEATHER-INGEST] Starting per-zone weather fetch cycle...")
    return await fetch_all_zones_weather()
