from __future__ import annotations

import os
import pathlib
from array import array
from typing import Iterable, Optional, Sequence

import aiosqlite
import sqlite_vec  # pip install sqlite-vec

PRAGMAS: list[str] = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA temp_store=MEMORY;",
]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  content TEXT NOT NULL,
  keywords TEXT,
  category TEXT,
  importance_score REAL DEFAULT 1.0,
  access_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  content_hash TEXT UNIQUE,
  simhash64 TEXT,
  embedding_version INT DEFAULT 1,
  ttl_seconds INT NULL,
  deleted_at TIMESTAMP NULL,
  pii_flag INT DEFAULT 0,
  source TEXT DEFAULT 'user'
);

-- vec0: embedding stored as float32 BLOB. Rowid matches memories.rowid.
CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0(
  embedding FLOAT[384]
);

-- FTS5 external content; rowid is memories.rowid.
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
  content, keywords, category, content='memories', content_rowid='rowid'
);

CREATE INDEX IF NOT EXISTS idx_user_cat ON memories(user_id, category);
CREATE INDEX IF NOT EXISTS idx_user_created ON memories(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_hash ON memories(content_hash);
CREATE INDEX IF NOT EXISTS idx_deleted_at ON memories(deleted_at);

-- FTS sync and vec cleanup on delete.
CREATE TRIGGER IF NOT EXISTS fts_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, content, keywords, category)
  VALUES (new.rowid, new.content, new.keywords, new.category);
END;

CREATE TRIGGER IF NOT EXISTS fts_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, content)
  VALUES ('delete', old.rowid, old.content);
  DELETE FROM memory_embeddings WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS fts_au AFTER UPDATE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, content)
  VALUES ('delete', old.rowid, old.content);
  INSERT INTO memories_fts(rowid, content, keywords, category)
  VALUES (new.rowid, new.content, new.keywords, new.category);
END;
"""

class SQLiteManager:
    """SQLite + FTS5 + sqlite-vec manager."""

    def __init__(self, db_path: str) -> None:
        self.db_path = os.path.expanduser(db_path)
        self.conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        pathlib.Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row

        for p in PRAGMAS:
            await self.conn.execute(p)

        await self.conn.enable_load_extension(True)
        vec_path = sqlite_vec.loadable_path()
        await self.conn.execute("SELECT load_extension(?)", (vec_path,))

        await self.conn.executescript(SCHEMA_SQL)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()
            self.conn = None

    # ---------------- Writes ----------------

    async def insert_memory_row(
        self,
        *,
        id: str,
        user_id: str,
        content: str,
        keywords_json: str,
        category: str,
        importance_score: float,
        content_hash: str,
        simhash64: str | None = None,
        embedding_version: int = 1,
        ttl_seconds: int | None = None,
        pii_flag: int = 0,
        source: str = "user",
    ) -> int:
        assert self.conn is not None
        cur = await self.conn.execute(
            """
            INSERT INTO memories
              (id, user_id, content, keywords, category, importance_score,
               content_hash, simhash64, embedding_version, ttl_seconds, pii_flag, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                user_id,
                content,
                keywords_json,
                category,
                importance_score,
                content_hash,
                simhash64,
                embedding_version,
                ttl_seconds,
                pii_flag,
                source,
            ),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def insert_vector(self, *, rowid: int, embedding: Sequence[float]) -> None:
        assert self.conn is not None
        buf = array("f", embedding).tobytes()
        await self.conn.execute(
            "INSERT INTO memory_embeddings(rowid, embedding) VALUES (?, ?)",
            (rowid, buf),
        )
        await self.conn.commit()

    async def soft_delete_ids(self, ids: Iterable[str]) -> int:
        assert self.conn is not None
        ids = list(ids)
        if not ids:
            return 0
        q = ",".join("?" for _ in ids)
        cur = await self.conn.execute(
            f"UPDATE memories SET deleted_at = CURRENT_TIMESTAMP WHERE id IN ({q})",
            tuple(ids),
        )
        await self.conn.commit()
        return cur.rowcount

    # ---------------- Reads / Hydration ----------------

    async def fetch_one_by_id(self, id: str) -> Optional[dict]:
        assert self.conn is not None
        cur = await self.conn.execute(
            "SELECT * FROM memories WHERE id = ? AND deleted_at IS NULL", (id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def fetch_rowid_by_id(self, id: str) -> Optional[int]:
        assert self.conn is not None
        cur = await self.conn.execute(
            "SELECT rowid FROM memories WHERE id = ? AND deleted_at IS NULL", (id,)
        )
        r = await cur.fetchone()
        return int(r["rowid"]) if r else None

    async def fetch_many_by_ids_ordered(self, ids: Sequence[str]) -> list[dict]:
        assert self.conn is not None
        if not ids:
            return []
        q = ",".join("?" for _ in ids)
        cur = await self.conn.execute(
            f"SELECT * FROM memories WHERE id IN ({q}) AND deleted_at IS NULL", tuple(ids)
        )
        rows = [dict(r) for r in await cur.fetchall()]
        pos = {mid: i for i, mid in enumerate(ids)}
        rows.sort(key=lambda r: pos.get(r["id"], 1_000_000))
        return rows

    async def fetch_meta_for_ids(self, ids: Sequence[str]) -> dict[str, dict]:
        assert self.conn is not None
        if not ids:
            return {}
        q = ",".join("?" for _ in ids)
        cur = await self.conn.execute(
            f"""
            SELECT id, strftime('%s', created_at) AS created_at_ts, access_count, importance_score
            FROM memories WHERE id IN ({q}) AND deleted_at IS NULL
            """,
            tuple(ids),
        )
        out: dict[str, dict] = {}
        for r in await cur.fetchall():
            out[r["id"]] = {
                "created_at_ts": int(r["created_at_ts"]),
                "access_count": int(r["access_count"]),
                "importance": float(r["importance_score"]),
            }
        return out

    async def bump_access(self, ids: Iterable[str]) -> None:
        assert self.conn is not None
        ids = list(ids)
        if not ids:
            return
        q = ",".join("?" for _ in ids)
        await self.conn.execute(
            f"""
            UPDATE memories
            SET access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP
            WHERE id IN ({q}) AND deleted_at IS NULL
            """,
            tuple(ids),
        )
        await self.conn.commit()

    async def update_content_and_embedding(
        self,
        *,
        id: str,
        new_content: str,
        new_keywords_json: str,
        new_category: str,
        new_content_hash: str,
        new_simhash64: str | None,
        new_embedding: Sequence[float],
        new_embedding_version: int = 1,
    ) -> None:
        assert self.conn is not None
        async with self.conn.execute("BEGIN"):
            await self.conn.execute(
                """
                UPDATE memories
                SET content = ?, keywords = ?, category = ?,
                    content_hash = ?, simhash64 = ?, embedding_version = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (
                    new_content,
                    new_keywords_json,
                    new_category,
                    new_content_hash,
                    new_simhash64,
                    new_embedding_version,
                    id,
                ),
            )
            rowid = await self.fetch_rowid_by_id(id)
            if rowid is None:
                raise ValueError("id not found or deleted")
            buf = array("f", new_embedding).tobytes()
            await self.conn.execute("DELETE FROM memory_embeddings WHERE rowid = ?", (rowid,))
            await self.conn.execute(
                "INSERT INTO memory_embeddings(rowid, embedding) VALUES (?, ?)",
                (rowid, buf),
            )
        await self.conn.commit()

    # ---------------- Maintenance ----------------

    async def vacuum_analyze(self) -> None:
        assert self.conn is not None
        await self.conn.execute("VACUUM")
        await self.conn.execute("ANALYZE")
        await self.conn.commit()

    async def fts_rebuild(self) -> None:
        assert self.conn is not None
        await self.conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild');")
        await self.conn.commit()

    async def fetch_ttl_expired_ids(self, limit: int = 500) -> list[str]:
        """IDs where ttl_seconds expired and not yet soft-deleted."""
        assert self.conn is not None
        cur = await self.conn.execute(
            """
            SELECT id
            FROM memories
            WHERE deleted_at IS NULL
              AND ttl_seconds IS NOT NULL
              AND (strftime('%s','now') - strftime('%s', created_at)) > ttl_seconds
            LIMIT ?
            """,
            (limit,),
        )
        return [r["id"] for r in await cur.fetchall()]

    async def find_simhash_dupe_ids(self, limit_groups: int = 100) -> list[str]:
        """
        Return IDs to delete for exact simhash duplicates, keeping the oldest row per simhash64.
        """
        assert self.conn is not None
        sql = """
        WITH dups AS (
          SELECT simhash64
          FROM memories
          WHERE simhash64 IS NOT NULL AND deleted_at IS NULL
          GROUP BY simhash64
          HAVING COUNT(*) > 1
          LIMIT ?
        ),
        keepers AS (
          SELECT m.simhash64, MIN(m.created_at) AS min_created
          FROM memories m
          JOIN dups d ON d.simhash64 = m.simhash64
          WHERE m.deleted_at IS NULL
          GROUP BY m.simhash64
        )
        SELECT m.id
        FROM memories m
        JOIN keepers k ON k.simhash64 = m.simhash64
        WHERE m.deleted_at IS NULL AND m.created_at > k.min_created
        """
        cur = await self.conn.execute(sql, (limit_groups,))
        return [r["id"] for r in await cur.fetchall()]

    async def purge_soft_deleted(self, older_than_days: int) -> int:
        """Hard-delete rows soft-deleted before threshold. Triggers clean vec + FTS."""
        assert self.conn is not None
        cur = await self.conn.execute(
            """
            DELETE FROM memories
            WHERE deleted_at IS NOT NULL
              AND (strftime('%s','now') - strftime('%s', deleted_at)) > (? * 86400)
            """,
            (older_than_days,),
        )
        await self.conn.commit()
        return cur.rowcount
