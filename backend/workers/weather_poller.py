"""
Weather Poller (Updated)
------------------------
Polls weather every 5 minutes and:
1. Feeds WeatherService cache (as before)
2. Runs weather_ingestion_service to update per-zone scores in ZoneStateEngine
3. Triggers zone_state_engine.recompute_all() so changes propagate immediately
"""

import asyncio
from datetime import datetime
from core.database import get_db
from core.event_bus import event_bus
from core.logger import logger
from services.weather_service import weather_service
from services.weather_impact_engine import weather_impact_engine
from services.weather_ingestion_service import fetch_all_zones_weather
from services.zone_state_engine import zone_state_engine

POLL_INTERVAL_SECONDS = 300  # 5 minutes
ACTIVE_CITIES = ["Chennai"]


class WeatherPoller:
    """
    Autonomous background worker that polls the weather API every 5 minutes.
    After fetching, updates:
      1. Zone-level weather scores in ZoneStateEngine
      2. Business impact DB record (demand_multiplier, risk_level)
      3. WebSocket broadcast
    """

    def __init__(self):
        self.is_running = False

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        logger.info("[WEATHER-POLLER] Autonomous weather intelligence started.")
        asyncio.create_task(self._run_loop())

    async def stop(self):
        self.is_running = False

    async def _run_loop(self):
        while self.is_running:
            try:
                db = get_db()
                for city in ACTIVE_CITIES:
                    logger.debug(f"[WEATHER-POLLER] Scanning real-time weather for {city}...")

                    # 1. Fetch city-level weather (for business impact / DB archive)
                    weather_data = await weather_service.get_weather(city)
                    result = weather_impact_engine.compute(weather_data)

                    # 2. Store/archive in DB
                    if db is not None:
                        city_name = city.strip().title()
                        existing = await db["weather_state"].find_one({"city": city_name})
                        if existing:
                            await db["weather_state_archive"].insert_one(existing)
                            await db["weather_state"].delete_one({"_id": existing["_id"]})

                        await db["weather_state"].insert_one({
                            "city":  city_name,
                            "rain":  result["input_summary"]["rain"],
                            "impact": {
                                "demand_multiplier": result["demand_multiplier"],
                                "risk_level":        result["risk_level"],
                            },
                            "timestamp": datetime.utcnow().isoformat(),
                        })

                    # 3. Run per-zone weather ingestion → ZoneStateEngine
                    zone_results = await fetch_all_zones_weather()
                    if zone_results:
                        # Recompute zone states with fresh weather data
                        await zone_state_engine.recompute_all(source="weather_poller")
                        logger.info(
                            f"[WEATHER-POLLER] {city}: {result['risk_level'].upper()} risk "
                            f"→ {len(zone_results)} zones updated in ZoneStateEngine"
                        )

                    # 4. Broadcast city-level weather update
                    await event_bus.emit("weather_update", {
                        "type": "weather_update",
                        "data": {
                            "city":    city.title(),
                            "weather": weather_data,
                            "impact":  result,
                        },
                    })

            except Exception as e:
                logger.error(f"[WEATHER-POLLER] Fault during polling cycle: {e}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)


weather_poller = WeatherPoller()
