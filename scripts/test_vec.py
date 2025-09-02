# scripts/test_vec.py
import asyncio
import os
import sys
import aiosqlite
import sqlite_vec

def get_vec_path() -> str:
    """Return the absolute path to the sqlite-vec extension."""
    loadable_path = os.path.dirname(sqlite_vec.__file__)
    if sys.platform == "darwin":
        return os.path.join(loadable_path, "vec0.dylib")
    elif sys.platform == "win32":
        return os.path.join(loadable_path, "vec0.dll")
    else:
        return os.path.join(loadable_path, "vec0.so")

async def main():
    db_path = os.path.expanduser("~/.mcp/memory.db")
    conn = await aiosqlite.connect(db_path)
    await conn.enable_load_extension(True)
    vec_path = get_vec_path()
    print(f"Loading extension from {vec_path}")
    await conn.load_extension(vec_path)
    print("Extension loaded")
    
    # Sanity check
    try:
        await conn.execute("SELECT vec0_version()")
        print("vec0_version() works")
    except Exception as e:
        print(f"vec0_version() failed: {e}")

    try:
        await conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _vec_sanity USING vec0(embedding FLOAT[4])")
        await conn.execute("DROP TABLE _vec_sanity")
        print("CREATE VIRTUAL TABLE works")
    except Exception as e:
        print(f"CREATE VIRTUAL TABLE failed: {e}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
