from __future__ import annotations
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_MEMORY_", case_sensitive=False)

    # Storage
    db_path: str = Field(default="~/.mcp/memory.db")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Embeddings & search
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    rrf_k: int = 60
    recency_half_life_days: int = 14

    # Categorization
    categories: List[str] = ["work", "personal", "technical", "contacts", "finance", "other"]

    # Background jobs
    enable_background: bool = False
    ttl_sweep_interval_sec: int = 300          # 5 min
    dedup_interval_sec: int = 1800             # 30 min
    vacuum_interval_sec: int = 86400           # 24 h
    purge_soft_deleted_after_days: int = 30    # hard-delete after 30 days

    # User identity
    user_id: str = "default"

settings = Settings()
