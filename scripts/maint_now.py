import asyncio
from mcp_memory.storage.sqlite_manager import SQLiteManager
from mcp_memory.config import settings

async def main():
    db = SQLiteManager(settings.db_path)
    await db.initialize()
    ttl = await db.fetch_ttl_expired_ids(limit=10000)
    if ttl:
        n = await db.soft_delete_ids(ttl)
        print("ttl_deleted", n)
    dupe = await db.find_simhash_dupe_ids(limit_groups=1000)
    if dupe:
        n = await db.soft_delete_ids(dupe)
        print("dedup_deleted", n)
    purged = await db.purge_soft_deleted(settings.purge_soft_deleted_after_days)
    print("purged", purged)
    await db.vacuum_analyze()
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
