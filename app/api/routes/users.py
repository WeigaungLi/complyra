"""User management endpoints — create users, list users, assign tenants.

Users in this system have:
  - A role (admin, auditor, or user) that controls what they can do
  - A default tenant that determines which organization's data they see
  - Additional tenant assignments for users who need access to multiple orgs

The user-tenant assignment pattern:
  Each user has a "default_tenant_id" (their primary organization) but can
  also be assigned to additional tenants. This allows, for example, an
  auditor to review data across multiple organizations without needing
  separate accounts. The assign_tenant endpoint adds these extra mappings.
"""

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
    """Convert a database user row into an API response, including tenant list."""
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
    """Create a new user account.

    Only admins can create users. The password is hashed before storage
    (never stored in plain text). The new user is automatically assigned
    to their default tenant.
    """
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
    """List all user accounts in the system. Only admins can see this list."""
    rows = list_user_accounts()
    return [_to_user_response(row) for row in rows]


@router.post("/{user_id}/tenants")
def assign_tenant(
    user_id: str,
    payload: AssignTenantRequest,
    user: dict = Depends(require_roles(["admin"])),
):
    """Grant a user access to an additional tenant.

    This creates a user-tenant mapping so the user can access data in the
    specified tenant, in addition to their default tenant. This is useful
    when a user (e.g., an auditor) needs to work across multiple organizations.
    """
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
