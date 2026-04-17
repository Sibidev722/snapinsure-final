"""
Zone State Worker — Master Scheduler
--------------------------------------
The single orchestrator that pulls all real-world data sources on schedule
and feeds the ZoneStateEngine to drive zone color decisions.

Schedule:
  • Weather   — every 5 min  (OWM + Open-Meteo, 9 zones, per lat/lon)
  • Traffic   — every 3 min  (OSRM free routing API, delay % per zone)
  • NLP/News  — every 5 min  (NewsAPI + GDELT, spaCy pipeline)
  • Demand    — every 60 sec (MongoDB earnings aggregation + news keywords)

After each ingestion cycle:
  → zone_state_engine.recompute_all() is called
  → Changed zones emit ZONE_STATE_CHANGED
  → UI_SYNC fires for all WebSocket clients
"""

import asyncio
from datetime import datetime

from core.logger import logger
from core.event_bus import event_bus
from services.zone_state_engine import zone_state_engine
from services.weather_ingestion_service import run_weather_ingestion_cycle
from services.traffic_ingestion_service import run_traffic_ingestion_cycle
from services.demand_ingestion_service import run_demand_ingestion_cycle

# NLP pipeline (used inline to process fetched articles)
from services.news_fetcher_service import news_fetcher_service
from services.spacy_nlp_pipeline import extract_news_event
from services.event_mapper_service import event_mapper

WEATHER_INTERVAL  = 300   # 5 min
TRAFFIC_INTERVAL  = 180   # 3 min
NLP_INTERVAL      = 300   # 5 min
DEMAND_INTERVAL   = 60    # 1 min

ACTIVE_CITY = "Chennai"


class ZoneStateWorker:
    """
    Master scheduler that drives all zone state updates from real APIs.
    Started once at application startup.
    """

    def __init__(self):
        self.is_running = False
        self._cycle_count = 0

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        logger.info("[ZSW] Zone State Worker starting — real-world reactive mode active")

        # Run immediate first-pass so zones have real data within seconds of startup
        asyncio.create_task(self._startup_prime())

        # Launch independent scheduling loops
        asyncio.create_task(self._weather_loop())
        asyncio.create_task(self._traffic_loop())
        asyncio.create_task(self._nlp_loop())
        asyncio.create_task(self._demand_loop())

    async def stop(self):
        self.is_running = False

    # ── Startup priming (run immediately, don't wait for first interval) ──────

    async def _startup_prime(self):
        """
        On first boot: prime all signal caches so zones have real state
        within the first 10 seconds rather than waiting 3-5 minutes.
        """
        logger.info("[ZSW] Priming real-world signals on startup...")
        await asyncio.sleep(3)   # Give DB and other services time to init

        try:
            await run_weather_ingestion_cycle()
        except Exception as e:
            logger.warning(f"[ZSW] Weather prime failed: {e}")

        try:
            await run_demand_ingestion_cycle()
        except Exception as e:
            logger.warning(f"[ZSW] Demand prime failed: {e}")

        # First recompute with whatever we have
        try:
            await zone_state_engine.recompute_all(source="startup_prime")
            logger.info("[ZSW] Initial zone states computed from real data ✓")
        except Exception as e:
            logger.error(f"[ZSW] Startup recompute failed: {e}")

        # Traffic is slower (OSRM needs multiple requests) — run in background
        asyncio.create_task(self._prime_traffic())

    async def _prime_traffic(self):
        """Prime traffic scores in background (takes a few seconds for 9 zone requests)."""
        await asyncio.sleep(5)
        try:
            await run_traffic_ingestion_cycle()
            await zone_state_engine.recompute_all(source="traffic_prime")
            logger.info("[ZSW] Traffic scores primed from OSRM ✓")
        except Exception as e:
            logger.warning(f"[ZSW] Traffic prime failed (non-critical): {e}")

    # ── Weather loop ──────────────────────────────────────────────────────────

    async def _weather_loop(self):
        logger.info(f"[ZSW] Weather loop started (every {WEATHER_INTERVAL}s via OWM/Open-Meteo)")
        while self.is_running:
            await asyncio.sleep(WEATHER_INTERVAL)
            try:
                results = await run_weather_ingestion_cycle()
                if results:
                    await zone_state_engine.recompute_all(source="weather_scheduler")
                    logger.info(f"[ZSW] Weather cycle complete — {len(results)} zones updated")
            except Exception as e:
                logger.error(f"[ZSW] Weather loop error: {e}")

    # ── Traffic loop ──────────────────────────────────────────────────────────

    async def _traffic_loop(self):
        logger.info(f"[ZSW] Traffic loop started (every {TRAFFIC_INTERVAL}s via OSRM)")
        while self.is_running:
            await asyncio.sleep(TRAFFIC_INTERVAL)
            try:
                results = await run_traffic_ingestion_cycle()
                if results:
                    await zone_state_engine.recompute_all(source="traffic_scheduler")
                    logger.info(f"[ZSW] Traffic cycle complete — {len(results)} zones checked")
            except Exception as e:
                logger.error(f"[ZSW] Traffic loop error: {e}")

    # ── NLP disruption loop ───────────────────────────────────────────────────

    async def _nlp_loop(self):
        logger.info(f"[ZSW] NLP loop started (every {NLP_INTERVAL}s via NewsAPI+GDELT+spaCy)")
        while self.is_running:
            await asyncio.sleep(NLP_INTERVAL)
            try:
                await self._run_nlp_cycle()
            except Exception as e:
                logger.error(f"[ZSW] NLP loop error: {e}")

    async def _run_nlp_cycle(self):
        """
        Full NLP pipeline:
          1. Fetch articles from NewsAPI + GDELT
          2. Run spaCy extraction on each
          3. Map events to zones via EventMapper
          4. Feed ZoneStateEngine disruption scores
          5. Recompute all zone states
        """
        fetch_result = await news_fetcher_service.fetch_all_sources(ACTIVE_CITY)
        articles = fetch_result.get("articles", [])

        if not articles:
            logger.debug("[ZSW] NLP cycle: no new articles")
            return

        logger.info(f"[ZSW] NLP cycle: processing {len(articles)} articles through spaCy...")

        disruptions_found = 0
        for article in articles:
            text_blob = f"{article.get('title', '')} {article.get('description', '')}"
            nlp_result = extract_news_event(text_blob)

            # Skip low-confidence results
            if nlp_result["confidence"] < 0.60:
                continue

            # Map event to zone
            mapped = await event_mapper.map_and_store_event(nlp_result)
            if not mapped.get("is_new"):
                continue

            doc = mapped["doc"]
            zone_id    = doc["zone_id"]
            event_type = doc["type"]
            severity   = doc["severity"]
            confidence = doc["confidence"]

            # Feed ZoneStateEngine directly
            zone_state_engine.update_disruption_score(
                zone_id=zone_id,
                event_type=event_type,
                severity=severity,
                confidence=confidence,
                source_text=text_blob[:120],
            )
            disruptions_found += 1

            logger.info(
                f"[ZSW] NLP disruption: {event_type} in zone {zone_id} "
                f"(conf={confidence:.2f}, severity={severity})"
            )

        if disruptions_found > 0:
            await zone_state_engine.recompute_all(source=f"nlp_scheduler({disruptions_found}_events)")
            logger.info(f"[ZSW] NLP cycle done — {disruptions_found} disruption(s) mapped")
        else:
            logger.debug("[ZSW] NLP cycle: no high-confidence disruptions found")

    # ── Demand loop ───────────────────────────────────────────────────────────

    async def _demand_loop(self):
        logger.info(f"[ZSW] Demand loop started (every {DEMAND_INTERVAL}s via MongoDB)")
        while self.is_running:
            await asyncio.sleep(DEMAND_INTERVAL)
            try:
                results = await run_demand_ingestion_cycle()
                if results:
                    await zone_state_engine.recompute_all(source="demand_scheduler")
            except Exception as e:
                logger.error(f"[ZSW] Demand loop error: {e}")


# Module-level singleton
zone_state_worker = ZoneStateWorker()
