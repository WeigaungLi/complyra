from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_accessible_tenant_ids, get_tenant_id, require_roles
from app.core.config import settings
from app.db.audit_db import create_ingest_job, get_ingest_job, list_ingest_jobs, update_ingest_job
from app.models.schemas import IngestJobResponse, IngestSubmitResponse
from app.services.audit import log_event
from app.services.ingest import normalize_ingest_filename, validate_ingest_filename
from app.services.queue import get_ingest_queue
from app.workers.ingest_worker import process_ingest_job

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _job_to_response(job) -> IngestJobResponse:
    return IngestJobResponse(
        job_id=job.job_id,
        tenant_id=job.tenant_id,
        filename=job.filename,
        status=job.status,
        chunks_indexed=job.chunks_indexed,
        document_id=job.document_id,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/file", response_model=IngestSubmitResponse)
async def ingest_file(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_id),
    user: dict = Depends(require_roles(["admin"])),
) -> IngestSubmitResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    validate_ingest_filename(file.filename)
    normalized_filename = normalize_ingest_filename(file.filename)

    max_size_bytes = settings.ingest_max_file_size_mb * 1024 * 1024
    data = await file.read(max_size_bytes + 1)
    if len(data) > max_size_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.ingest_max_file_size_mb} MB limit")

    job_id = str(uuid4())
    upload_dir = Path(settings.ingest_storage_path)
    upload_dir.mkdir(parents=True, exist_ok=True)
    local_path = upload_dir / f"{job_id}_{normalized_filename}"
    local_path.write_bytes(data)

    create_ingest_job(job_id=job_id, tenant_id=tenant_id, created_by=user["user_id"], filename=normalized_filename)

    try:
        if settings.ingest_async_enabled:
            queue = get_ingest_queue()
            queue.enqueue(
                "app.workers.ingest_worker.process_ingest_job",
                job_id,
                str(local_path),
                normalized_filename,
                tenant_id,
                job_timeout="15m",
            )
        else:
            process_ingest_job(job_id, str(local_path), normalized_filename, tenant_id)
    except Exception as exc:
        update_ingest_job(job_id=job_id, status="failed", error_message=str(exc))
        raise HTTPException(status_code=503, detail="Failed to enqueue ingest job") from exc

    log_event(
        tenant_id=tenant_id,
        user=user["username"],
        action="ingest_submitted",
        input_text=normalized_filename,
        output_text=job_id,
        metadata='{"queue": "ingest"}',
    )

    return IngestSubmitResponse(job_id=job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=IngestJobResponse)
def get_job(
    job_id: str,
    tenant_ids: list[str] = Depends(get_accessible_tenant_ids),
    _current_user: dict = Depends(require_roles(["admin", "auditor"])),
):
    job = get_ingest_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.tenant_id not in tenant_ids:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    return _job_to_response(job)


@router.get("/jobs", response_model=list[IngestJobResponse])
def list_jobs(
    limit: int = 50,
    tenant_ids: list[str] = Depends(get_accessible_tenant_ids),
    _current_user: dict = Depends(require_roles(["admin", "auditor"])),
):
    jobs = list_ingest_jobs(tenant_ids=tenant_ids, limit=limit)
    return [_job_to_response(job) for job in jobs]
