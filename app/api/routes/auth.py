from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings
from app.core.security import create_access_token
from app.models.schemas import LoginRequest, TokenResponse
from app.services.users import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response) -> TokenResponse:
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(
        subject=user["username"],
        role=user["role"],
        user_id=user["user_id"],
        default_tenant_id=user.get("default_tenant_id"),
    )

    response.set_cookie(
        key=settings.session_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        max_age=settings.access_token_expire_minutes * 60,
    )

    return TokenResponse(
        access_token=access_token,
        role=user["role"],
        user_id=user["user_id"],
        default_tenant_id=user.get("default_tenant_id"),
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.cookie_domain or None,
        samesite=settings.cookie_samesite,
    )
    return {"status": "ok"}
