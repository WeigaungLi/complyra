from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_roles
from app.models.schemas import TenantCreateRequest, TenantResponse
from app.services.audit import log_event
from app.services.users import create_tenant_account, get_tenant_account, list_tenant_accounts

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("/", response_model=TenantResponse)
def create_tenant(payload: TenantCreateRequest, user: dict = Depends(require_roles(["admin"]))):
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
    rows = list_tenant_accounts()
    return [TenantResponse(tenant_id=row.tenant_id, name=row.name, created_at=row.created_at) for row in rows]
