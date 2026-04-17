import asyncio
import logging
from datetime import datetime
from core.database import get_db
from services.income_os_decision_engine import income_os_decision_engine

logger = logging.getLogger(__name__)

class IncomeOSWorker:
    def __init__(self, interval_seconds: int = 5):
        self.interval = interval_seconds
        self.is_running = False
        self._task = None

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[IncomeOSWorker] Started (Interval: {self.interval}s)")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[IncomeOSWorker] Stopped")

    async def _run_loop(self):
        while self.is_running:
            try:
                await self._process_decisions()
            except Exception as e:
                logger.error(f"[IncomeOSWorker] Error in loop: {e}")
            
            await asyncio.sleep(self.interval)

    async def _process_decisions(self):
        db = get_db()
        if db is None:
            return

        # 1. Fetch all workers currently in the simulation
        workers_cursor = db.workers.find({})
        workers = await workers_cursor.to_list(length=1000)

        if not workers:
            return

        decisions_to_store = []
        
        # 2. Generate and batch decisions
        for worker in workers:
            worker_id = worker.get("id")
            zone_id = worker.get("zone_id")
            
            if not worker_id or not zone_id:
                continue
                
            decision_doc = await income_os_decision_engine.generate_decision(worker_id, zone_id)
            decisions_to_store.append(decision_doc)

        # 3. Persist to MongoDB (Upsert latest for each worker)
        if decisions_to_store:
            for doc in decisions_to_store:
                await db.income_os_decisions.update_one(
                    {"worker_id": doc["worker_id"]},
                    {"$set": doc},
                    upsert=True
                )
            # logger.debug(f"[IncomeOSWorker] Updated {len(decisions_to_store)} worker decisions")

income_os_worker = IncomeOSWorker()
