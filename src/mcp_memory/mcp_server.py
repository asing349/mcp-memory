from __future__ import annotations
import asyncio
from typing import Optional

from mcp.server.fastmcp import FastMCP

from mcp_memory.config import settings
from mcp_memory.storage.sqlite_manager import SQLiteManager
from mcp_memory.storage.redis_cache import RedisCache
from mcp_memory.intelligence.embeddings import EmbeddingService
from mcp_memory.tools.store_memory import store_memory_tool
from mcp_memory.tools.recall_memory import recall_memory_tool
from mcp_memory.tools.forget_memory import forget_memory_tool
from mcp_memory.tools.memory_health import memory_health_tool

mcp = FastMCP("mcp-memory")

_db: Optional[SQLiteManager] = None
_cache: Optional[RedisCache] = None
_embed: Optional[EmbeddingService] = None
_initialized = False
_lock = asyncio.Lock()

async def ensure_init() -> None:
    global _initialized, _db, _cache, _embed
    if _initialized:
        return
    async with _lock:
        if _initialized:
            return
        _db = SQLiteManager(settings.db_path)
        await _db.initialize()
        _cache = RedisCache(settings.redis_url, user_id=settings.user_id)
        await _cache.initialize()
        _embed = EmbeddingService(model_name=settings.embedding_model, cache=_cache)
        _initialized = True

@mcp.tool()
async def store_memory(content: str, category: str | None = None,
                       importance: float | None = None,
                       ttl_seconds: int | None = None) -> dict:
    await ensure_init()
    assert _db and _embed
    return await store_memory_tool(
        db=_db, cache=_cache, embed=_embed,
        content=content, user_id=settings.user_id,
        category=category, importance=importance, ttl_seconds=ttl_seconds
    )

@mcp.tool()
async def recall_memory(query: str, category_filter: str | None = None,
                        limit: int = 10) -> dict:
    await ensure_init()
    assert _db and _embed
    return await recall_memory_tool(
        db=_db, cache=_cache, embed=_embed,
        query=query, user_id=settings.user_id,
        category_filter=category_filter, limit=limit,
        rrf_k=settings.rrf_k, recency_half_life_days=settings.recency_half_life_days
    )

@mcp.tool()
async def forget_memory(memory_id: str | None = None,
                        query: str | None = None,
                        confirm: bool = False) -> dict:
    await ensure_init()
    assert _db and _embed
    return await forget_memory_tool(
        db=_db, cache=_cache, embed=_embed,
        user_id=settings.user_id, memory_id=memory_id,
        query=query, confirm=confirm
    )

@mcp.tool()
async def memory_health() -> dict:
    await ensure_init()
    assert _db
    return await memory_health_tool(db=_db, cache=_cache, db_path=settings.db_path)

if __name__ == "__main__":
    mcp.run(transport="stdio")
