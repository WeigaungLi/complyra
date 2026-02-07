from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_accessible_tenant_ids, get_current_user, get_tenant_id, require_roles
from app.models.schemas import ApprovalDecisionRequest, ApprovalResponse
from app.services.approvals import decide_approval, get_approval_request, list_approval_requests
from app.services.audit import log_event

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _to_response(row) -> ApprovalResponse:
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
    approval = get_approval_request(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.tenant_id not in tenant_ids:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Approval already decided")

    updated = decide_approval(
        approval_id=approval_id,
        approved=payload.approved,
        decision_by=user["username"],
        note=payload.note or "",
    )

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
    approval = get_approval_request(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    if approval.user_id != user["user_id"] and user["role"] not in {"admin", "auditor"}:
        raise HTTPException(status_code=403, detail="Access denied")
    return _to_response(approval)
