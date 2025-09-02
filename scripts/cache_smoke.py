import asyncio
from mcp_memory.storage.redis_cache import RedisCache

async def main():
    rc = RedisCache("redis://127.0.0.1:6379/0", user_id="default")
    await rc.initialize()
    print("enabled:", rc.enabled)

    await rc.set_embedding("Hello World", [0.1, 0.2, 0.3])
    v = await rc.get_embedding("Hello World")
    print("embed:", v)

    await rc.touch_last_write()
    before = await rc.last_write_ts()
    print("lw before:", before)

    await rc.set_query_ids("shoe size", "hybrid", ["a","b","c"])
    q = await rc.get_query_ids("shoe size", "hybrid")
    print("q ids:", q)

    await rc.close()

if __name__ == "__main__":
    asyncio.run(main())
