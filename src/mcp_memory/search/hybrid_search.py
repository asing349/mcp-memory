from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

from ..storage.sqlite_manager import SQLiteManager


def rrf_fuse(
    vec_ids: Sequence[str],
    txt_ids: Sequence[str],
    *,
    k: int = 60,
) -> Dict[str, float]:
    """
    Reciprocal Rank Fusion over two ranked lists.
    """
    ranks: Dict[str, float] = defaultdict(float)
    for i, mid in enumerate(vec_ids):
        ranks[mid] += 1.0 / (k + (i + 1))
    for i, mid in enumerate(txt_ids):
        ranks[mid] += 1.0 / (k + (i + 1))
    return ranks


def composite_score(
    ids: Iterable[str],
    *,
    cos_map: Dict[str, float],
    meta: Dict[str, Dict],
    half_life_days: int = 14,
) -> Dict[str, float]:
    """
    Final score = 0.6*cos + 0.2*recency + 0.15*log1p(access) + 0.05*importance
    """
    now = time.time()
    out: Dict[str, float] = {}
    for mid in ids:
        cos = float(cos_map.get(mid, 0.0))
        m = meta.get(mid, {"created_at_ts": now, "access_count": 0, "importance": 1.0})
        age_days = max(0.0, (now - float(m["created_at_ts"])) / 86400.0)
        rec = math.exp(-age_days / float(half_life_days))
        acc = math.log1p(float(m["access_count"]))
        imp = float(m["importance"])
        s = 0.6 * cos + 0.2 * rec + 0.15 * acc + 0.05 * imp
        out[mid] = s
    return out


async def apply_category_filter(
    db: SQLiteManager, ids: Sequence[str], category: str | None
) -> List[str]:
    if not category or not ids:
        return list(ids)
    assert db.conn is not None
    qmarks = ",".join("?" for _ in ids)
    sql = f"SELECT id FROM memories WHERE id IN ({qmarks}) AND category = ? AND deleted_at IS NULL"
    cur = await db.conn.execute(sql, (*ids, category))
    rows = [r["id"] for r in await cur.fetchall()]
    # preserve original order
    keep = set(rows)
    return [i for i in ids if i in keep]
