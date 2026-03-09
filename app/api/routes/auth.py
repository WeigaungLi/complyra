"""Authentication endpoints — login to get a JWT token, logout to clear it.

This module provides two simple endpoints:
  - POST /auth/login  — verify username + password, return a JWT token
  - POST /auth/logout — delete the session cookie so the user is logged out
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings
from app.core.security import create_access_token
from app.models.schemas import LoginRequest, TokenResponse
from app.services.users import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response) -> TokenResponse:
    """Log in with a username and password.

    Steps:
      1. Check the username/password against the database.
      2. If the credentials are wrong, return a 401 error.
      3. If correct, create a JWT (JSON Web Token) that encodes the user's
         identity and role.
      4. Store the token in an HTTP-only cookie AND return it in the JSON body.
      5. Return the token along with the user's role and tenant info.
    """

    # Step 1: Verify password — this checks the hashed password stored in the
    # database against the plain-text password the user provided.
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Step 2: Create a JWT token — this is a signed string that contains the
    # user's identity (username, role, user_id). The server can later verify
    # this token without needing to look up a session in the database.
    access_token = create_access_token(
        subject=user["username"],
        role=user["role"],
        user_id=user["user_id"],
        default_tenant_id=user.get("default_tenant_id"),
    )

    # Step 3: Set the token as an HTTP-only cookie.
    # Why both a cookie AND a JSON response?
    #   - The cookie is for browser-based clients (the frontend). Browsers
    #     automatically send cookies with every request, so the frontend
    #     doesn't need to manage tokens manually.
    #   - The JSON response body is for API clients (like Postman, curl, or
    #     mobile apps) that don't use cookies and instead pass the token in
    #     an Authorization header.
    # "httponly=True" means JavaScript cannot read this cookie, which prevents
    # cross-site scripting (XSS) attacks from stealing the token.
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
    """Log out by deleting the session cookie.

    This tells the browser to remove the JWT cookie. After this, the user
    will need to log in again to make authenticated requests.
    Note: This does NOT invalidate the JWT itself — it simply removes it
    from the browser. If someone copied the token, it remains valid until
    it expires. For true server-side invalidation, a token blocklist would
    be needed.
    """
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.cookie_domain or None,
        samesite=settings.cookie_samesite,
    )
    return {"status": "ok"}
