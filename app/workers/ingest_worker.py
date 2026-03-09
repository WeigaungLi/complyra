"""Background worker that processes document ingestion jobs from the Redis queue.

This module is executed by the RQ worker process (not the web server). When a
user uploads a document, the web server enqueues a job; this worker picks it
up and runs the full ingestion pipeline:
1. Read the uploaded file from the temporary storage path.
2. Extract text (with OCR for scanned PDFs, or Gemini Vision for images).
3. Split the text into chunks and embed them into vectors.
4. Store the vectors in Qdrant and create a database record.
5. Clean up the temporary file to save disk space.

If anything fails at any step, the job is marked as "failed" in the database
so the user (or an admin) can see what went wrong.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.core.config import settings
from app.db.audit_db import get_ingest_job, update_ingest_job
from app.services.ingest import ingest_document_from_path

logger = logging.getLogger(__name__)


def _count_pages(file_path: str, extension: str) -> int:
    """Count the number of pages in a PDF file.

    This information is stored in the document record so the UI can display
    the page count. For non-PDF files, we return 0 since the concept of
    "pages" does not apply to plain text or images.
    """
    if extension != "pdf":
        return 0
    try:
        import fitz

        doc = fitz.open(file_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def _move_to_preview_storage(file_path: str, document_id: str, filename: str) -> str | None:
    """Copy the uploaded file to permanent preview storage. Returns the new path.

    The original file sits in a temporary upload directory and will be deleted
    after processing. If we want users to be able to preview/download the
    original document later, we need to keep a copy in a permanent location.
    The file is renamed to {document_id}.{extension} to avoid name collisions.
    """
    try:
        preview_dir = Path(settings.document_preview_storage_path)
        preview_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix
        dest = preview_dir / f"{document_id}{ext}"
        shutil.copy2(file_path, str(dest))
        return str(dest)
    except Exception:
        logger.warning("Failed to copy file to preview storage: %s", file_path, exc_info=True)
        return None


def process_ingest_job(job_id: str, file_path: str, filename: str, tenant_id: str) -> dict:
    """Process a single document ingestion job from the Redis queue.

    This is the main function that the RQ worker calls. It orchestrates
    the full pipeline:
    1. Mark the job as "processing" so the user sees progress.
    2. Call ingest_document_from_path to extract text, chunk it, embed it,
       and store vectors in Qdrant.
    3. Count pages (for PDFs) and copy the file to preview storage.
    4. Create a SQL record for the document so it appears in the UI.
    5. Mark the job as "completed" with the resulting document_id.

    If anything fails, the job is marked as "failed" with the error message
    so the user knows what went wrong and can retry or report the issue.

    The temporary upload file is always deleted in the 'finally' block,
    regardless of success or failure, to avoid filling up disk space with
    abandoned uploads.
    """
    # Mark the job as "processing" immediately so the user's status poll
    # shows that work has begun.
    update_ingest_job(job_id=job_id, status="processing")
    try:
        document_id, chunks_indexed = ingest_document_from_path(file_path, filename, tenant_id)
        if not document_id:
            update_ingest_job(
                job_id=job_id, status="failed", error_message="No text extracted from file"
            )
            return {"status": "failed", "job_id": job_id}

        # Determine page count and move file for preview
        extension = Path(filename).suffix.lstrip(".").lower()
        page_count = _count_pages(file_path, extension)
        file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
        preview_path = _move_to_preview_storage(file_path, document_id, filename)

        # Create SQL Document record
        job = get_ingest_job(job_id)
        created_by = job.created_by if job else "unknown"

        from app.services.documents import create_document

        create_document(
            document_id=document_id,
            tenant_id=tenant_id,
            filename=filename,
            file_size=file_size,
            page_count=page_count,
            chunk_count=chunks_indexed,
            created_by=created_by,
            storage_path=preview_path,
        )

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
        # If anything fails (text extraction, embedding, database write, etc.),
        # mark the job as "failed" so the user knows. The error message is stored
        # in the database for debugging purposes.
        update_ingest_job(job_id=job_id, status="failed", error_message=str(exc))
        return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        # Delete the temporary upload file after processing to save disk space.
        # This runs whether the job succeeded or failed — the file is no longer
        # needed because either (a) it was already copied to preview storage,
        # or (b) the job failed and keeping the file would just waste space.
        path = Path(file_path)
        if path.exists():
            path.unlink(missing_ok=True)
