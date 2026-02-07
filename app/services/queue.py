from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.core.config import settings


@lru_cache(maxsize=1)
def get_redis_connection() -> Redis:
    return Redis.from_url(settings.redis_url)


@lru_cache(maxsize=1)
def get_ingest_queue() -> Queue:
    return Queue(settings.ingest_queue_name, connection=get_redis_connection())
