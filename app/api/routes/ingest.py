"""Document upload and ingestion job tracking.

This module handles uploading files (PDF, DOCX, etc.) and processing them into
searchable chunks stored in a vector database. The workflow is:
  1. User uploads a file via POST /ingest/file
  2. The file is validated, saved to disk, and a "job" record is created
  3. The actual processing (parsing, chunking, embedding) happens either
     synchronously or via a background worker queue (async)
  4. Users can check job status via GET /ingest/jobs/{job_id}
"""

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
    """Convert a database job row into an API response object."""
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
    """Upload a document file and start an ingestion job.

    This endpoint accepts a file upload, validates it, saves it to disk,
    and then kicks off the ingestion pipeline (parsing, chunking, embedding)
    either synchronously or via a background worker queue.

    Only users with the "admin" role can upload documents.

    Returns a job_id that can be used to track processing status.
    """

    # --- File validation ---
    # Make sure the file has a name and that the name/extension is allowed.
    # This prevents uploading of dangerous file types (e.g., .exe).
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    validate_ingest_filename(file.filename)
    # Normalize the filename (remove special characters, etc.) to avoid
    # filesystem issues and security problems.
    normalized_filename = normalize_ingest_filename(file.filename)

    # --- Size check ---
    # Read one byte more than the limit. If we get that extra byte, the file
    # is too large. This avoids loading an entire huge file into memory.
    max_size_bytes = settings.ingest_max_file_size_mb * 1024 * 1024
    data = await file.read(max_size_bytes + 1)
    if len(data) > max_size_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.ingest_max_file_size_mb} MB limit")

    # --- Save file to disk ---
    # We prefix the filename with the job_id to avoid name collisions.
    job_id = str(uuid4())
    upload_dir = Path(settings.ingest_storage_path)
    upload_dir.mkdir(parents=True, exist_ok=True)
    local_path = upload_dir / f"{job_id}_{normalized_filename}"
    local_path.write_bytes(data)

    # Create a job record in the database so we can track its status.
    create_ingest_job(job_id=job_id, tenant_id=tenant_id, created_by=user["user_id"], filename=normalized_filename)

    # --- Sync vs Async ingestion path ---
    # When async is enabled (production), the job is placed onto a Redis queue
    # and a background worker picks it up. This is important because ingestion
    # can take minutes (parsing PDFs, generating embeddings) and we don't want
    # to block the HTTP request for that long.
    # When async is disabled (development/testing), we process the file right
    # here in the same request — simpler but slower for the caller.
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
        # If enqueueing fails (e.g., Redis is down), mark the job as failed
        # so the user knows something went wrong.
        update_ingest_job(job_id=job_id, status="failed", error_message=str(exc))
        raise HTTPException(status_code=503, detail="Failed to enqueue ingest job") from exc

    # Record this action in the audit log for compliance tracking.
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
    """Get the status of a single ingestion job by its ID.

    Returns details like status (queued/processing/completed/failed),
    how many chunks were indexed, and any error message.
    Only accessible to admins and auditors within the same tenant.
    """
    job = get_ingest_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Ensure the user can only see jobs belonging to their tenant(s).
    if job.tenant_id not in tenant_ids:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    return _job_to_response(job)


@router.get("/jobs", response_model=list[IngestJobResponse])
def list_jobs(
    limit: int = 50,
    tenant_ids: list[str] = Depends(get_accessible_tenant_ids),
    _current_user: dict = Depends(require_roles(["admin", "auditor"])),
):
    """List all ingestion jobs visible to the current user.

    Returns jobs filtered by the user's accessible tenants, ordered by
    most recent first. Use the 'limit' parameter to control how many
    results are returned (default: 50).
    """
    jobs = list_ingest_jobs(tenant_ids=tenant_ids, limit=limit)
    return [_job_to_response(job) for job in jobs]
