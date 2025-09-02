from __future__ import annotations
import asyncio
from structlog import get_logger
from mcp_memory.storage.sqlite_manager import SQLiteManager
from mcp_memory.config import settings
from mcp_memory.obs.metrics import METRICS

log = get_logger()

class BackgroundWorker:
    def __init__(self, db: SQLiteManager) -> None:
        self.db = db
        self._tasks: list[asyncio.Task] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        self._stopping.clear()
        self._tasks = [
            asyncio.create_task(self._loop_ttl_sweeper(), name="ttl_sweeper"),
            asyncio.create_task(self._loop_dedup(), name="dedup"),
            asyncio.create_task(self._loop_vacuum(), name="vacuum"),
        ]
        log.info("bg_started")

    async def stop(self) -> None:
        self._stopping.set()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        log.info("bg_stopped")

    async def _sleep(self, seconds: int) -> None:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return

    async def _loop_ttl_sweeper(self) -> None:
        interval = int(settings.ttl_sweep_interval_sec)
        while not self._stopping.is_set():
            try:
                ids = await self.db.fetch_ttl_expired_ids(limit=1000)
                if ids:
                    n = await self.db.soft_delete_ids(ids)
                    await METRICS.inc("ttl_deleted_total", n)
                    log.info("ttl_sweep", deleted=n)
            except Exception as e:
                log.warning("ttl_sweep_error", err=str(e))
            await self._sleep(interval)

    async def _loop_dedup(self) -> None:
        interval = int(settings.dedup_interval_sec)
        while not self._stopping.is_set():
            try:
                ids = await self.db.find_simhash_dupe_ids(limit_groups=200)
                if ids:
                    n = await self.db.soft_delete_ids(ids)
                    await METRICS.inc("dedup_deleted_total", n)
                    log.info("dedup", deleted=n)
            except Exception as e:
                log.warning("dedup_error", err=str(e))
            await self._sleep(interval)

    async def _loop_vacuum(self) -> None:
        interval = int(settings.vacuum_interval_sec)
        keep_days = int(settings.purge_soft_deleted_after_days)
        while not self._stopping.is_set():
            try:
                purged = await self.db.purge_soft_deleted(older_than_days=keep_days)
                await self.db.vacuum_analyze()
                await METRICS.inc("purged_total", purged)
                log.info("vacuum", purged=purged)
            except Exception as e:
                log.warning("vacuum_error", err=str(e))
            await self._sleep(interval)
