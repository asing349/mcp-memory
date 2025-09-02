from __future__ import annotations
import json, time
from typing import Optional, List, Tuple, Dict
from ..storage.sqlite_manager import SQLiteManager
from ..storage.redis_cache import RedisCache
from ..intelligence.embeddings import EmbeddingService
from ..search.vector_search import vector_topk
from ..search.text_search import text_topk
from ..search.hybrid_search import rrf_fuse, composite_score

def _coerce_keywords(row: dict) -> dict:
    v = row.get("keywords")
    if isinstance(v, str):
        try:
            row["keywords"] = json.loads(v)
        except Exception:
            row["keywords"] = []
    return row

async def recall_memory_tool(
    *,
    db: SQLiteManager,
    cache: Optional[RedisCache],
    embed: EmbeddingService,
    query: str,
    user_id: str = "default",
    category_filter: Optional[str] = None,
    limit: int = 10,
    rrf_k: int = 60,
    recency_half_life_days: int = 14,
) -> dict:
    timings: Dict[str, float] = {}
    t0 = time.perf_counter()

    # try query cache
    t = time.perf_counter()
    cached_ids = await (cache.get_query_ids(query, "hybrid") if cache else None)
    timings["cache_lookup_ms"] = (time.perf_counter() - t) * 1000.0
    if cached_ids:
        t = time.perf_counter()
        rows = await db.fetch_many_by_ids_ordered(cached_ids[:limit])
        rows = [_coerce_keywords(r) for r in rows]
        await db.bump_access([r["id"] for r in rows])
        timings["db_hydrate_ms"] = (time.perf_counter() - t) * 1000.0
        timings["total_ms"] = (time.perf_counter() - t0) * 1000.0
        return {"answers": rows, "cached": True, "timings_ms": timings}

    # embed
    t = time.perf_counter()
    qvec = await embed.embed_one(query)
    timings["embed_ms"] = (time.perf_counter() - t) * 1000.0

    # vector
    t = time.perf_counter()
    v: List[Tuple[str, float]] = await vector_topk(db, qvec, user_id=user_id, k=50)
    timings["vector_ms"] = (time.perf_counter() - t) * 1000.0

    # text
    t = time.perf_counter()
    tlist: List[Tuple[str, float]] = await text_topk(db, query, user_id=user_id, k=50)
    timings["text_ms"] = (time.perf_counter() - t) * 1000.0

    # fuse + rescore
    t = time.perf_counter()
    vec_ids = [mid for mid, _ in v]
    txt_ids = [mid for mid, _ in tlist]
    fused = rrf_fuse(vec_ids, txt_ids, k=rrf_k)
    cos_map: Dict[str, float] = {mid: score for mid, score in v}
    meta = await db.fetch_meta_for_ids(list(fused.keys()))
    comp = composite_score(fused.keys(), cos_map=cos_map, meta=meta, half_life_days=recency_half_life_days)
    ranked_ids = [mid for mid, _ in sorted(comp.items(), key=lambda x: x[1], reverse=True)]
    timings["fuse_rescore_ms"] = (time.perf_counter() - t) * 1000.0

    # optional category filter after ranking
    if category_filter:
        t = time.perf_counter()
        rows_full = await db.fetch_many_by_ids_ordered(ranked_ids)
        ranked_ids = [r["id"] for r in rows_full if r.get("category") == category_filter]
        timings["category_filter_ms"] = (time.perf_counter() - t) * 1000.0

    # hydrate
    t = time.perf_counter()
    rows = await db.fetch_many_by_ids_ordered(ranked_ids[:limit])
    rows = [_coerce_keywords(r) for r in rows]
    await db.bump_access([r["id"] for r in rows])
    timings["db_hydrate_ms"] = (time.perf_counter() - t) * 1000.0

    # write cache
    t = time.perf_counter()
    if cache:
        await cache.set_query_ids(query, "hybrid", ranked_ids)
    timings["cache_write_ms"] = (time.perf_counter() - t) * 1000.0

    timings["total_ms"] = (time.perf_counter() - t0) * 1000.0
    return {"answers": rows, "cached": False, "timings_ms": timings}
