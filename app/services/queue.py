"""Redis job queue management for async document ingestion.

Instead of processing file uploads immediately inside the HTTP request
(which would block the web server and risk timeouts for large files),
we put each upload into a Redis-backed job queue. A separate background
worker process picks up jobs from this queue and processes them at its
own pace.

This pattern is called a "task queue" or "job queue":
1. The web server receives a file upload and creates a job in the queue.
2. The server immediately responds to the user with a job ID.
3. A background worker (see ingest_worker.py) picks up the job, extracts
   text, creates embeddings, and stores them in the vector database.
4. The user can poll the job status to know when processing is complete.

We use RQ (Redis Queue), a simple Python library that uses Redis as the
message broker between the web server and the worker process.
"""

from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.core.config import settings


@lru_cache(maxsize=1)
def get_redis_connection() -> Redis:
    """Return a cached Redis connection.

    The @lru_cache decorator ensures we create only one Redis connection
    and reuse it throughout the application's lifetime, avoiding the cost
    of reconnecting on every queue operation.
    """
    return Redis.from_url(settings.redis_url)


@lru_cache(maxsize=1)
def get_ingest_queue() -> Queue:
    """Return the RQ queue used for async document ingestion.

    This queue acts as a to-do list for the background worker. When a
    user uploads a file, the web server adds a job to this queue. The
    worker process continuously watches the queue and processes jobs
    one by one (or in parallel, depending on worker configuration).
    """
    return Queue(settings.ingest_queue_name, connection=get_redis_connection())
