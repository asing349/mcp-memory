from __future__ import annotations
import os
from ..storage.sqlite_manager import SQLiteManager
from ..storage.redis_cache import RedisCache

async def memory_health_tool(*, db: SQLiteManager, cache: RedisCache | None, db_path: str) -> dict:
    assert db.conn is not None
    cur = await db.conn.execute("SELECT COUNT(*) AS c FROM memories WHERE deleted_at IS NULL")
    c = (await cur.fetchone())["c"]
    cur = await db.conn.execute("SELECT COUNT(*) AS c FROM memory_embeddings")
    ev = (await cur.fetchone())["c"]
    size_mb = round(os.path.getsize(os.path.expanduser(db_path)) / (1024 * 1024), 2) if os.path.exists(os.path.expanduser(db_path)) else 0.0
    lw = await cache.last_write_ts() if cache else "disabled"
    return {"count": int(c), "embeddings": int(ev), "db_mb": size_mb, "last_write": lw}
