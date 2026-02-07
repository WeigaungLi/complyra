from __future__ import annotations

from pathlib import Path

from app.db.audit_db import update_ingest_job
from app.services.ingest import ingest_document_from_path


def process_ingest_job(job_id: str, file_path: str, filename: str, tenant_id: str) -> dict:
    update_ingest_job(job_id=job_id, status="processing")
    try:
        document_id, chunks_indexed = ingest_document_from_path(file_path, filename, tenant_id)
        if not document_id:
            update_ingest_job(job_id=job_id, status="failed", error_message="No text extracted from file")
            return {"status": "failed", "job_id": job_id}

        update_ingest_job(
            job_id=job_id,
            status="completed",
            chunks_indexed=chunks_indexed,
            document_id=document_id,
        )
        return {
            "status": "completed",
            "job_id": job_id,
            "document_id": document_id,
            "chunks_indexed": chunks_indexed,
        }
    except Exception as exc:  # pragma: no cover - job system catches broad exceptions
        update_ingest_job(job_id=job_id, status="failed", error_message=str(exc))
        return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        path = Path(file_path)
        if path.exists():
            path.unlink(missing_ok=True)
