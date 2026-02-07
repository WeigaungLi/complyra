from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.retrieval import get_qdrant_client
from app.services.llm import ollama_health

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live_check():
    return {"status": "ok"}


@router.get("/ready")
def ready_check():
    checks = {
        "database": False,
        "qdrant": False,
        "ollama": False,
    }

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    try:
        qdrant = get_qdrant_client()
        qdrant.get_collections()
        checks["qdrant"] = True
    except Exception:
        checks["qdrant"] = False

    checks["ollama"] = ollama_health()

    overall = "ok" if all(checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
