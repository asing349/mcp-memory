import asyncio
import json
import uuid

from mcp_memory.storage.sqlite_manager import SQLiteManager

DB = "~/.mcp/memory.db"


async def main():
    db = SQLiteManager(DB)
    await db.initialize()

    mem_id = str(uuid.uuid4())
    rowid = await db.insert_memory_row(
        id=mem_id,
        user_id="default",
        content="my shoe size is 10 US",
        keywords_json=json.dumps(["shoe", "size", "10", "us"]),
        category="personal",
        importance_score=1.0,
        content_hash="dummyhash123",
        simhash64=None,
    )

    fake_vec = [0.0] * 384
    await db.insert_vector(rowid=rowid, embedding=fake_vec)

    print("Inserted memory id:", mem_id, "rowid:", rowid)
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
