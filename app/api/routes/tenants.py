"""Tenant management and policy configuration endpoints.

A "tenant" represents an isolated organization or workspace in the system.
Each tenant has its own documents, users, and policies. This multi-tenant
design means one deployment of the application can serve many separate
organizations, each with their own data and settings.

This module provides endpoints to:
  - Create and list tenants (admin only)
  - Get and update a tenant's approval policy
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_roles
from app.models.schemas import (
    TenantCreateRequest,
    TenantPolicyResponse,
    TenantPolicyUpdateRequest,
    TenantResponse,
)
from app.services.approval_policy import get_tenant_approval_mode, set_tenant_approval_mode
from app.services.audit import log_event
from app.services.users import create_tenant_account, get_tenant_account, list_tenant_accounts

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("/", response_model=TenantResponse)
def create_tenant(payload: TenantCreateRequest, user: dict = Depends(require_roles(["admin"]))):
    """Create a new tenant (organization).

    If no tenant_id is provided in the request, one is auto-generated from
    the tenant name by lowercasing and replacing spaces with hyphens.
    Only admins can create tenants.
    """
    tenant_id = payload.tenant_id or payload.name.lower().replace(" ", "-")
    try:
        row = create_tenant_account(tenant_id, payload.name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Tenant creation failed") from exc

    if not row:
        row = get_tenant_account(tenant_id)
    if not row:
        raise HTTPException(status_code=500, detail="Tenant created but not found")

    log_event(
        tenant_id=user.get("default_tenant_id") or tenant_id,
        user=user["username"],
        action="tenant_create",
        input_text=tenant_id,
        output_text=row.name,
        metadata="{}",
    )

    return TenantResponse(tenant_id=row.tenant_id, name=row.name, created_at=row.created_at)


@router.get("/", response_model=list[TenantResponse])
def list_tenants(_current_user: dict = Depends(require_roles(["admin"]))):
    """List all tenants in the system. Only admins can see this list."""
    rows = list_tenant_accounts()
    return [
        TenantResponse(tenant_id=row.tenant_id, name=row.name, created_at=row.created_at)
        for row in rows
    ]


@router.get("/{tenant_id}/policy", response_model=TenantPolicyResponse)
def get_policy(
    tenant_id: str,
    _current_user: dict = Depends(require_roles(["admin"])),
) -> TenantPolicyResponse:
    """Get the current approval policy for a tenant.

    The "approval mode" controls how AI-generated answers are handled:
      - "auto": answers are delivered immediately with no human review
      - "always": every answer requires human approval before delivery
      - "sensitive": only answers about sensitive documents need approval

    If no policy has been explicitly set, the system default is returned.
    """
    from app.db.audit_db import get_tenant_policy

    policy = get_tenant_policy(tenant_id)
    if policy:
        return TenantPolicyResponse(
            tenant_id=policy.tenant_id,
            approval_mode=policy.approval_mode,
            updated_at=policy.updated_at,
            updated_by=policy.updated_by,
        )
    # No explicit policy found — return the system-wide default.
    return TenantPolicyResponse(
        tenant_id=tenant_id,
        approval_mode=get_tenant_approval_mode(tenant_id),
    )


@router.put("/{tenant_id}/policy", response_model=TenantPolicyResponse)
def update_policy(
    tenant_id: str,
    payload: TenantPolicyUpdateRequest,
    current_user: dict = Depends(require_roles(["admin"])),
) -> TenantPolicyResponse:
    """Update the approval policy for a tenant.

    Changes the approval mode (auto / always / sensitive) for the given
    tenant. This immediately affects how new AI-generated answers are
    handled. The change is recorded in the audit log.
    """
    policy = set_tenant_approval_mode(tenant_id, payload.approval_mode, current_user["username"])
    log_event(
        tenant_id=tenant_id,
        user=current_user["username"],
        action="policy_updated",
        input_text=f"approval_mode={payload.approval_mode}",
        output_text="",
        metadata="{}",
    )
    return TenantPolicyResponse(
        tenant_id=policy.tenant_id,
        approval_mode=policy.approval_mode,
        updated_at=policy.updated_at,
        updated_by=policy.updated_by,
    )
