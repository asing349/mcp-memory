from __future__ import annotations
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from .utils import normalize_text
from ..storage.redis_cache import RedisCache

class EmbeddingService:
    """Local sentence-transformers embedder with optional Redis caching."""
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cache: Optional[RedisCache] = None) -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.cache = cache
        _ = self.model.encode(["warmup"], normalize_embeddings=True)

    async def embed_one(self, text: str) -> List[float]:
        n = normalize_text(text)
        if self.cache:
            v = await self.cache.get_embedding(f"{self.model_name}:{n}")
            if v is not None:
                return v
        vec = self.model.encode([n], normalize_embeddings=True)[0].tolist()
        if self.cache:
            await self.cache.set_embedding(f"{self.model_name}:{n}", vec)
        return vec

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        outs: list[list[float]] = []
        misses: list[tuple[int, str]] = []
        if self.cache:
            for i, t in enumerate(texts):
                n = normalize_text(t)
                v = await self.cache.get_embedding(f"{self.model_name}:{n}")
                if v is None:
                    misses.append((i, n))
                    outs.append([])  # placeholder
                else:
                    outs.append(v)
        else:
            misses = [(i, normalize_text(t)) for i, t in enumerate(texts)]
            outs = [[] for _ in texts]
        if misses:
            normed = [n for _, n in misses]
            mat = self.model.encode(normed, normalize_embeddings=True)
            for (i, n), row in zip(misses, mat):
                vec = row.tolist()
                outs[i] = vec
                if self.cache:
                    await self.cache.set_embedding(f"{self.model_name}:{n}", vec)
        return outs
