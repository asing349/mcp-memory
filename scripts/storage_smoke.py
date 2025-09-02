import asyncio
import json
import uuid

from mcp_memory.storage.sqlite_manager import SQLiteManager

DB = "~/.mcp/memory.db"

async def main():
    db = SQLiteManager(DB)
    await db.initialize()

    # insert
    mid = str(uuid.uuid4())
    rowid = await db.insert_memory_row(
        id=mid,
        user_id="default",
        content="remember: office wifi password is redacted",
        keywords_json=json.dumps(["office","wifi","password"]),
        category="work",
        importance_score=0.8,
        content_hash=mid.replace("-", "")[:32],
        simhash64=None,
    )
    print("inserted", mid, "rowid", rowid)

    # fetch one
    one = await db.fetch_one_by_id(mid)
    print("fetch_one:", one["category"], one["content"][:24])

    # bump access
    await db.bump_access([mid])
    one2 = await db.fetch_one_by_id(mid)
    print("access_count:", one2["access_count"])

    # fetch many ordered
    rows = await db.fetch_many_by_ids_ordered([mid])
    print("ordered_count:", len(rows))

    # soft delete
    deleted = await db.soft_delete_ids([mid])
    print("deleted:", deleted)

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
