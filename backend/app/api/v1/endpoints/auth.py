from fastapi import APIRouter, Depends

from app.core.dependencies import get_auth_service
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email/username + password",
    responses={
        200: {"description": "Access + refresh token pair"},
        401: {"description": "Invalid credentials"},
        403: {"description": "Account suspended"},
    },
)
def login(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Accepts either an email address or a username as ``identifier``.
    Returns a short-lived access token (15 min) and a long-lived
    refresh token (30 days).  The refresh token is stored in the DB.
    """
    return auth_service.login(identifier=body.identifier, password=body.password)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new token pair",
    responses={
        200: {"description": "New access + refresh token pair (old refresh token revoked)"},
        401: {"description": "Invalid, expired, or revoked refresh token"},
    },
)
def refresh(
    body: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Validates the supplied refresh token, revokes it, and issues a fresh pair
    (token rotation).  Replaying the old refresh token after a successful
    refresh will return 401.
    """
    return auth_service.refresh(body.refresh_token)


@router.post(
    "/logout",
    status_code=204,
    summary="Revoke a refresh token (logout)",
    responses={
        204: {"description": "Token revoked — no content"},
        401: {"description": "Invalid refresh token"},
    },
)
def logout(
    body: LogoutRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """
    Revokes the supplied refresh token.  The short-lived access token will
    continue to work until it expires naturally — clients should discard it.
    Operation is idempotent: logging out an already-revoked token succeeds silently.
    """
    auth_service.logout(body.refresh_token)
