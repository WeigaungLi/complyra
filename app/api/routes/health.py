"""Health check endpoints for container orchestration (Kubernetes/ECS).

Container orchestrators like Kubernetes need a way to know if the application
is running and if it is ready to serve traffic. This module provides two
separate health check endpoints:

  - GET /health/live  — "liveness" check: is the process alive?
  - GET /health/ready — "readiness" check: are all dependencies reachable?

The distinction matters:
  - If the liveness check fails, the orchestrator restarts the container.
  - If the readiness check fails, the orchestrator stops sending traffic to
    this instance but does NOT restart it (the dependencies might recover).
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.metrics import HEALTH_CHECK_STATUS
from app.db.session import SessionLocal
from app.services.llm import ollama_health
from app.services.queue import get_redis_connection
from app.services.retrieval import get_qdrant_client

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live_check():
    """Liveness probe: live = the process is running.

    This is the simplest possible check. If the server can respond to this
    request at all, it means the Python process is alive and the web
    framework is working. No external dependencies are checked here.
    """
    return {"status": "ok"}


@router.get("/ready")
def ready_check():
    """Readiness probe: ready = all dependencies (DB, Qdrant, Redis, LLM) are reachable.

    This endpoint checks every external service the application depends on.
    If any of them is unreachable, the overall status is "degraded" and the
    orchestrator should stop routing new requests to this instance.

    Each check also measures latency in milliseconds, which is useful for
    diagnosing performance issues.
    """
    checks: dict = {}

    # --- Database health check ---
    # Runs a simple "SELECT 1" query to verify the SQL database (PostgreSQL)
    # is reachable and accepting connections.
    try:
        t0 = time.perf_counter()
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = {
            "status": True,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    except Exception as exc:
        checks["database"] = {"status": False, "error": str(exc)[:100]}

    # --- Qdrant (vector database) health check ---
    # Qdrant stores document embeddings for semantic search. We verify it's
    # reachable by listing its collections.
    try:
        t0 = time.perf_counter()
        qdrant = get_qdrant_client()
        collections = qdrant.get_collections()
        checks["qdrant"] = {
            "status": True,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "collections": len(collections.collections),
        }
    except Exception as exc:
        checks["qdrant"] = {"status": False, "error": str(exc)[:100]}

    # --- Redis health check ---
    # Redis is used as the message queue for background ingestion jobs.
    # A simple PING command verifies connectivity.
    try:
        t0 = time.perf_counter()
        redis_conn = get_redis_connection()
        redis_conn.ping()
        checks["redis"] = {
            "status": True,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    except Exception as exc:
        checks["redis"] = {"status": False, "error": str(exc)[:100]}

    # --- LLM (Large Language Model) provider health check ---
    # The LLM is the AI model that generates answers. We check if the
    # configured provider (e.g., Ollama) is responding.
    t0 = time.perf_counter()
    llm_ok = ollama_health()
    checks["llm"] = {
        "status": llm_ok,
        "provider": settings.llm_provider,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }

    # Update Prometheus metrics gauges so monitoring dashboards can track
    # the health of each component over time.
    for component, detail in checks.items():
        HEALTH_CHECK_STATUS.labels(component=component).set(1.0 if detail["status"] else 0.0)

    # If ALL components are healthy, status is "ok". If any is down, "degraded".
    all_ok = all(c["status"] for c in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "version": "1.0.0",
        "environment": settings.env,
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "checks": checks,
    }
