from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_roles
from app.models.schemas import AssignTenantRequest, UserCreateRequest, UserResponse
from app.services.audit import log_event
from app.services.users import (
    assign_user_to_tenant,
    create_user_account,
    list_user_accounts,
    list_user_tenant_access,
)

router = APIRouter(prefix="/users", tags=["users"])


def _to_user_response(row) -> UserResponse:
    tenant_ids = list_user_tenant_access(row.user_id)
    return UserResponse(
        user_id=row.user_id,
        username=row.username,
        role=row.role,
        default_tenant_id=row.default_tenant_id,
        tenant_ids=tenant_ids,
        created_at=row.created_at,
    )


@router.post("/", response_model=UserResponse)
def create_user(payload: UserCreateRequest, user: dict = Depends(require_roles(["admin"]))):
    try:
        user_id = create_user_account(
            username=payload.username,
            password=payload.password,
            role=payload.role,
            default_tenant_id=payload.default_tenant_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="User creation failed") from exc

    created = next((row for row in list_user_accounts() if row.user_id == user_id), None)
    if not created:
        raise HTTPException(status_code=500, detail="User created but not found")

    log_event(
        tenant_id=payload.default_tenant_id or user.get("default_tenant_id") or "default",
        user=user["username"],
        action="user_create",
        input_text=created.username,
        output_text=created.role,
        metadata="{}",
    )
    return _to_user_response(created)


@router.get("/", response_model=list[UserResponse])
def list_users(_current_user: dict = Depends(require_roles(["admin"]))):
    rows = list_user_accounts()
    return [_to_user_response(row) for row in rows]


@router.post("/{user_id}/tenants")
def assign_tenant(
    user_id: str,
    payload: AssignTenantRequest,
    user: dict = Depends(require_roles(["admin"])),
):
    try:
        assign_user_to_tenant(user_id, payload.tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Assignment failed") from exc

    log_event(
        tenant_id=payload.tenant_id,
        user=user["username"],
        action="user_tenant_assign",
        input_text=user_id,
        output_text=payload.tenant_id,
        metadata="{}",
    )
    return {"status": "ok"}
