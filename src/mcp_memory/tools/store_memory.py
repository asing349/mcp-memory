from __future__ import annotations
import json, uuid
from typing import Optional
from ..storage.sqlite_manager import SQLiteManager
from ..storage.redis_cache import RedisCache
from ..intelligence.utils import normalize_text, sha256_hex, simhash64
from ..intelligence.keywords import extract_keywords
from ..intelligence.categorize import categorize
from ..intelligence.embeddings import EmbeddingService

async def store_memory_tool(
    *,
    db: SQLiteManager,
    cache: Optional[RedisCache],
    embed: EmbeddingService,
    content: str,
    user_id: str = "default",
    category: Optional[str] = None,
    importance: Optional[float] = None,
    ttl_seconds: Optional[int] = None,
) -> dict:
    n = normalize_text(content)
    ch = sha256_hex(n)
    sh = simhash64(n)
    kws = extract_keywords(n)
    cat = category or categorize(n, kws)
    imp = float(importance) if importance is not None else 1.0
    vec = await embed.embed_one(n)

    mem_id = str(uuid.uuid4())
    rowid = await db.insert_memory_row(
        id=mem_id,
        user_id=user_id,
        content=content,
        keywords_json=json.dumps(kws),
        category=cat,
        importance_score=imp,
        content_hash=ch,
        simhash64=sh,
        ttl_seconds=ttl_seconds,
    )
    await db.insert_vector(rowid=rowid, embedding=vec)
    if cache:
        await cache.touch_last_write()
    return {"id": mem_id, "category": cat, "keywords": kws}
