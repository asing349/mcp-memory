from __future__ import annotations

import hashlib
import json
import time
from typing import List, Optional, Sequence

from redis.asyncio import Redis, from_url

from ..intelligence.utils import normalize_text


class RedisCache:
    """
    Async Redis cache for embeddings and query results.
    Safe to disable by setting URL to 'disabled'.
    """

    def __init__(self, redis_url: str, *, user_id: str = "default") -> None:
        self.redis_url = redis_url
        self.user_id = user_id
        self.client: Optional[Redis] = None
        self.enabled: bool = False

    # ---------- lifecycle ----------

    async def initialize(self) -> None:
        if self.redis_url.lower() == "disabled":
            self.enabled = False
            return
        self.client = from_url(self.redis_url, encoding="utf-8", decode_responses=True)
        try:
            pong = await self.client.ping()
            self.enabled = bool(pong)
        except Exception:
            self.enabled = False
            self.client = None

    async def close(self) -> None:
        if self.client:
            try:
                await self.client.aclose()
            finally:
                self.client = None
        self.enabled = False

    # ---------- keys ----------

    @staticmethod
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _embed_key(self, text: str) -> str:
        n = normalize_text(text)
        return f"embed:{self._sha256(n)}"

    def _lw_key(self) -> str:
        return f"u:{self.user_id}:lw"  # last write timestamp (seconds)

    def _query_key(self, query: str, search_type: str, schema_v: int) -> str:
        # include last-write to invalidate old caches after any write/delete
        lw = "0"
        return f"u:{self.user_id}:q:v{schema_v}:{self._sha256(query)}:{search_type}:{lw}"

    async def _query_key_with_lw(self, query: str, search_type: str, schema_v: int) -> str:
        lw = await self.last_write_ts()
        return f"u:{self.user_id}:q:v{schema_v}:{self._sha256(query)}:{search_type}:{lw}"

    # ---------- embedding cache ----------

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        if not (self.enabled and self.client):
            return None
        v = await self.client.get(self._embed_key(text))
        return json.loads(v) if v else None

    async def set_embedding(self, text: str, vec: Sequence[float], ttl: int = 86400) -> None:
        if not (self.enabled and self.client):
            return
        await self.client.setex(self._embed_key(text), ttl, json.dumps(list(vec)))

    # ---------- query result cache ----------

    async def get_query_ids(self, query: str, search_type: str, schema_v: int = 1) -> Optional[List[str]]:
        if not (self.enabled and self.client):
            return None
        k = await self._query_key_with_lw(query, search_type, schema_v)
        v = await self.client.get(k)
        return json.loads(v) if v else None

    async def set_query_ids(
        self,
        query: str,
        search_type: str,
        ids: Sequence[str],
        ttl: int = 3600,
        schema_v: int = 1,
    ) -> None:
        if not (self.enabled and self.client):
            return
        k = await self._query_key_with_lw(query, search_type, schema_v)
        await self.client.setex(k, ttl, json.dumps(list(ids)))

    # ---------- invalidation ----------

    async def touch_last_write(self) -> None:
        if not (self.enabled and self.client):
            return
        now = int(time.time())
        await self.client.set(self._lw_key(), str(now))

    async def last_write_ts(self) -> str:
        if not (self.enabled and self.client):
            return "0"
        v = await self.client.get(self._lw_key())
        return v or "0"
