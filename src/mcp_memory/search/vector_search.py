from __future__ import annotations

import json
from typing import List, Tuple

from aiosqlite import Row
from ..storage.sqlite_manager import SQLiteManager


async def vector_topk(
    db: SQLiteManager,
    query_vec: List[float],
    *,
    user_id: str = "default",
    k: int = 50,
) -> List[Tuple[str, float]]:
    """
    Returns [(memory_id, cosine_sim)].
    Assumes stored embeddings are L2-normalized.
    sqlite-vec returns L2 distance; convert to cosine: cos ≈ 1 - d^2/2
    """
    assert db.conn is not None
    sql = """
    SELECT m.id AS id, v.distance AS dist
    FROM (
      SELECT rowid, distance
      FROM memory_embeddings
      WHERE embedding MATCH ?
      ORDER BY distance
      LIMIT ?
    ) AS v
    JOIN memories m ON m.rowid = v.rowid
    WHERE m.user_id = ? AND m.deleted_at IS NULL
    """
    cur = await db.conn.execute(sql, (json.dumps(query_vec), k, user_id))
    rows: List[Row] = await cur.fetchall()
    out: List[Tuple[str, float]] = []
    for r in rows:
        d = float(r["dist"])
        cos = 1.0 - (d * d) / 2.0
        out.append((r["id"], cos))
    return out
