import asyncio, json, uuid

from mcp_memory.intelligence.embeddings import EmbeddingService
from mcp_memory.intelligence.utils import normalize_text, sha256_hex, simhash64
from mcp_memory.intelligence.keywords import extract_keywords
from mcp_memory.intelligence.categorize import categorize
from mcp_memory.storage.sqlite_manager import SQLiteManager

DB = "~/.mcp/memory.db"

async def main():
    text = "Remember my UCR project repo is https://github.com/ajit/abc"
    # 1) intelligence
    n = normalize_text(text)
    ch = sha256_hex(n)
    sh = simhash64(n)
    kws = extract_keywords(n)
    cat = categorize(n, kws)
    emb = EmbeddingService().embed_one(n)

    print("normalized:", n)
    print("sha256:", ch[:12], "simhash64:", sh)
    print("keywords:", kws)
    print("category:", cat)
    print("embedding-dim:", len(emb))

    # 2) store to DB
    db = SQLiteManager(DB)
    await db.initialize()
    mem_id = str(uuid.uuid4())
    rowid = await db.insert_memory_row(
        id=mem_id,
        user_id="default",
        content=text,
        keywords_json=json.dumps(kws),
        category=cat,
        importance_score=1.0,
        content_hash=ch,
        simhash64=sh,
    )
    await db.insert_vector(rowid=rowid, embedding=emb)
    print("stored:", mem_id, "rowid:", rowid)
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
