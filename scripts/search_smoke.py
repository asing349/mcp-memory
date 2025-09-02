import asyncio
import json

from mcp_memory.intelligence.embeddings import EmbeddingService
from mcp_memory.storage.sqlite_manager import SQLiteManager
from mcp_memory.search.vector_search import vector_topk
from mcp_memory.search.text_search import text_topk
from mcp_memory.search.hybrid_search import rrf_fuse, composite_score

DB = "~/.mcp/memory.db"

async def main():
    db = SQLiteManager(DB)
    await db.initialize()

    embed = EmbeddingService()
    q = "repo url"
    qvec = embed.embed_one(q)

    v = await vector_topk(db, qvec, k=10)
    t = await text_topk(db, q, k=10)

    vec_ids = [mid for mid, _ in v]
    txt_ids = [mid for mid, _ in t]

    fused = rrf_fuse(vec_ids, txt_ids, k=60)

    # meta and cosine map for composite scoring
    cos_map = {mid: score for mid, score in v}
    meta = await db.fetch_meta_for_ids(list(fused.keys()))
    comp = composite_score(fused.keys(), cos_map=cos_map, meta=meta, half_life_days=14)

    ranked = sorted(comp.items(), key=lambda x: x[1], reverse=True)
    print("Query:", q)
    for mid, s in ranked[:5]:
        print(mid, round(s, 4))

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
