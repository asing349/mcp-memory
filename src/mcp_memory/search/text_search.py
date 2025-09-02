from __future__ import annotations
import re
from typing import List, Tuple
from aiosqlite import Row
from ..storage.sqlite_manager import SQLiteManager

_WORD = re.compile(r'"[^"]+"|\S+')

def build_fts_query(q: str) -> str:
    """Phrases stay quoted. Other tokens AND'ed."""
    parts = _WORD.findall(q)
    clauses = []
    for p in parts:
        if p.startswith('"') and p.endswith('"'):
            clauses.append(p)
        else:
            clauses.append(f'"{p}"')
    return " AND ".join(clauses) if clauses else '""'

async def text_topk(
    db: SQLiteManager,
    query: str,
    *,
    user_id: str = "default",
    k: int = 50,
) -> List[Tuple[str, float]]:
    """
    Returns [(memory_id, score)], where score = 1/(1+bm25).
    """
    assert db.conn is not None
    match = build_fts_query(query)
    sql = """
    SELECT m.id AS id, bm25(memories_fts) AS bm
    FROM memories_fts f
    JOIN memories m ON m.rowid = f.rowid
    WHERE m.user_id = ? AND m.deleted_at IS NULL
      AND f.memories_fts MATCH ?
    ORDER BY bm ASC
    LIMIT ?
    """
    cur = await db.conn.execute(sql, (user_id, match, k))
    rows: List[Row] = await cur.fetchall()
    out: List[Tuple[str, float]] = []
    for r in rows:
        bm = float(r["bm"])
        score = 1.0 / (1.0 + bm)
        out.append((r["id"], score))
    return out
