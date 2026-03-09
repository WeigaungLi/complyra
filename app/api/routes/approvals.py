"""Human-in-the-loop approval workflow endpoints.

Some AI-generated answers are too sensitive or risky to deliver automatically.
When a tenant's policy requires human approval, the system creates an
"approval request" containing the question and a draft answer. An admin or
auditor must then approve or reject it before the answer is shown to the user.

This module provides endpoints to:
  - List pending (and historical) approval requests
  - Approve or reject a pending request
  - Check the result of an approval (used by the chat flow to poll for decisions)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_accessible_tenant_ids, get_current_user, get_tenant_id, require_roles
from app.models.schemas import ApprovalDecisionRequest, ApprovalResponse
from app.services.approvals import decide_approval, get_approval_request, list_approval_requests
from app.services.audit import log_event

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _to_response(row) -> ApprovalResponse:
    """Convert a database approval row into an API response object."""
    return ApprovalResponse(
        approval_id=row.approval_id,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        status=row.status,
        question=row.question,
        draft_answer=row.draft_answer,
        final_answer=row.final_answer,
        created_at=row.created_at,
        decided_at=row.decided_at,
        decision_by=row.decision_by,
        decision_note=row.decision_note,
    )


@router.get("/", response_model=list[ApprovalResponse])
def list_approvals(
    status: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    tenant_ids: list[str] = Depends(get_accessible_tenant_ids),
    _current_user: dict = Depends(require_roles(["admin", "auditor"])),
):
    """List approval requests, optionally filtered by status and tenant.

    Admins and auditors can see all approvals for their accessible tenants.
    Use status="pending" to see only items that still need a decision.
    """
    # If a specific tenant_id is requested, verify the user has access to it.
    selected_tenants = tenant_ids
    if tenant_id:
        if tenant_id not in tenant_ids:
            raise HTTPException(status_code=403, detail="Tenant access denied")
        selected_tenants = [tenant_id]
    rows = list_approval_requests(tenant_ids=selected_tenants, status=status, limit=limit)
    return [_to_response(row) for row in rows]


@router.post("/{approval_id}/decision", response_model=ApprovalResponse)
def decide(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    tenant_ids: list[str] = Depends(get_accessible_tenant_ids),
    user: dict = Depends(require_roles(["admin", "auditor"])),
):
    """Approve or reject a pending approval request.

    The approval decision flow:
      1. Look up the approval request and verify it exists.
      2. Check the user has tenant access and the request is still pending.
      3. If approved (payload.approved=True): the draft_answer becomes the
         final_answer and is delivered to the original user.
      4. If rejected (payload.approved=False): the request is marked as
         rejected and the original user is told their query was declined.
      5. The decision is recorded in the audit log for compliance.
    """
    approval = get_approval_request(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.tenant_id not in tenant_ids:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    # Prevent double-decisions: once approved or rejected, it cannot change.
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Approval already decided")

    # Record who made the decision and when.
    updated = decide_approval(
        approval_id=approval_id,
        approved=payload.approved,
        decision_by=user["username"],
        note=payload.note or "",
    )

    # Log the decision in the audit trail for compliance records.
    log_event(
        tenant_id=approval.tenant_id,
        user=user["username"],
        action="approval_decision",
        input_text=approval_id,
        output_text=updated.status if updated else "unknown",
        metadata=f'{{"approved": {str(payload.approved).lower()}}}',
    )

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update approval")
    return _to_response(updated)


@router.get("/{approval_id}/result", response_model=ApprovalResponse)
def approval_result(
    approval_id: str,
    tenant_id: str = Depends(get_tenant_id),
    user: dict = Depends(get_current_user),
):
    """Check the current status/result of an approval request.

    This endpoint is used by the chat interface to poll for a decision.
    Regular users can only see their own approval requests; admins and
    auditors can see any approval within their tenant.
    """
    approval = get_approval_request(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    # Regular users can only view their own requests.
    if approval.user_id != user["user_id"] and user["role"] not in {"admin", "auditor"}:
        raise HTTPException(status_code=403, detail="Access denied")
    return _to_response(approval)
