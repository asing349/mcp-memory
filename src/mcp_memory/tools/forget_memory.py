from __future__ import annotations
from typing import Optional, List
from ..storage.sqlite_manager import SQLiteManager
from ..storage.redis_cache import RedisCache
from ..intelligence.embeddings import EmbeddingService
from .recall_memory import recall_memory_tool

async def forget_memory_tool(
    *,
    db: SQLiteManager,
    cache: Optional[RedisCache],
    embed: EmbeddingService,
    user_id: str = "default",
    memory_id: Optional[str] = None,
    query: Optional[str] = None,
    confirm: bool = False,
    preview_limit: int = 50,
) -> dict:
    if not memory_id and not query:
        return {"success": False, "message": "Provide memory_id or query"}
    ids: List[str]
    if memory_id:
        ids = [memory_id]
    else:
        res = await recall_memory_tool(db=db, cache=cache, embed=embed, query=query or "", user_id=user_id, limit=preview_limit)
        ids = [r["id"] for r in res["answers"]]
        if not confirm:
            return {"to_delete": ids, "confirm": False}

    deleted = await db.soft_delete_ids(ids)
    if cache:
        await cache.touch_last_write()
    return {"deleted": deleted, "ids": ids, "confirm": True}
