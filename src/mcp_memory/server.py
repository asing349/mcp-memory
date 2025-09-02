from __future__ import annotations
import os, pathlib, time
from fastapi import FastAPI, Body, Response
from structlog import get_logger
from .config import settings
from .storage.sqlite_manager import SQLiteManager
from .storage.redis_cache import RedisCache
from .intelligence.embeddings import EmbeddingService
from .tools.store_memory import store_memory_tool
from .tools.recall_memory import recall_memory_tool
from .tools.forget_memory import forget_memory_tool
from .tools.memory_health import memory_health_tool
from .obs.metrics import METRICS
from .background.worker import BackgroundWorker

log = get_logger()
app = FastAPI(title="mcp-memory", version="0.1.0")

_db: SQLiteManager | None = None
_cache: RedisCache | None = None
_embed: EmbeddingService | None = None
_bg: BackgroundWorker | None = None

@app.on_event("startup")
async def startup() -> None:
    global _db, _cache, _embed, _bg
    db_path = os.path.expanduser(settings.db_path)
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _db = SQLiteManager(db_path)
    await _db.initialize()
    _cache = RedisCache(settings.redis_url, user_id=settings.user_id)
    await _cache.initialize()
    _embed = EmbeddingService(model_name=settings.embedding_model, cache=_cache)
    if settings.enable_background:
        _bg = BackgroundWorker(_db)
        await _bg.start()
    log.info("startup", db=db_path, redis=settings.redis_url, model=settings.embedding_model, bg=settings.enable_background)

@app.on_event("shutdown")
async def shutdown() -> None:
    global _db, _cache, _bg
    if _bg: await _bg.stop()
    if _cache: await _cache.close()
    if _db: await _db.close()
    log.info("shutdown")

@app.get("/health")
async def health():
    return {"ok": True, "db_path": os.path.expanduser(settings.db_path), "redis_url": settings.redis_url}

@app.get("/metrics")
async def metrics():
    text = await METRICS.export_prom()
    return Response(content=text, media_type="text/plain; version=0.0.4")

@app.post("/tools/store_memory")
async def store_memory_ep(payload: dict = Body(...)):
    assert _db and _embed is not None
    t0 = time.perf_counter()
    res = await store_memory_tool(
        db=_db, cache=_cache, embed=_embed,
        content=str(payload.get("content", "")),
        user_id=settings.user_id,
        category=payload.get("category"),
        importance=payload.get("importance"),
        ttl_seconds=payload.get("ttl_seconds"),
    )
    await METRICS.inc("requests_store_total")
    await METRICS.observe_ms("latency_store", (time.perf_counter() - t0) * 1000.0)
    return {"success": True, "data": res}

@app.post("/tools/recall_memory")
async def recall_memory_ep(payload: dict = Body(...)):
    assert _db and _embed is not None
    t0 = time.perf_counter()
    res = await recall_memory_tool(
        db=_db, cache=_cache, embed=_embed,
        query=str(payload.get("query", "")),
        user_id=settings.user_id,
        category_filter=payload.get("category_filter"),
        limit=int(payload.get("limit", 10)),
        rrf_k=int(settings.rrf_k),
        recency_half_life_days=int(settings.recency_half_life_days),
    )
    await METRICS.inc("requests_recall_total")
    await METRICS.observe_ms("latency_recall_total", (time.perf_counter() - t0) * 1000.0)
    for k, v in res.get("timings_ms", {}).items():
        await METRICS.observe_ms(f"stage_{k}", float(v))
    return {"success": True, "data": res}

@app.post("/tools/forget_memory")
async def forget_memory_ep(payload: dict = Body(...)):
    assert _db and _embed is not None
    t0 = time.perf_counter()
    res = await forget_memory_tool(
        db=_db, cache=_cache, embed=_embed,
        user_id=settings.user_id,
        memory_id=payload.get("memory_id"),
        query=payload.get("query"),
        confirm=bool(payload.get("confirm", False)),
    )
    await METRICS.inc("requests_forget_total")
    await METRICS.observe_ms("latency_forget", (time.perf_counter() - t0) * 1000.0)
    return {"success": True, "data": res}

@app.get("/tools/memory_health")
async def memory_health_ep():
    assert _db is not None
    res = await memory_health_tool(db=_db, cache=_cache, db_path=settings.db_path)
    await METRICS.inc("requests_health_total")
    return {"success": True, "data": res}
