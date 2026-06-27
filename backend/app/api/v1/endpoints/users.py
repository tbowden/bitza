from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, get_user_service
from app.core.exceptions import PermissionDeniedError
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserListRead, UserRead, UserSelfUpdate, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Current user's own profile
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserRead, summary="Get your own profile")
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update your own profile (display_name or password)",
)
async def update_me(
    body: UserSelfUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    Password changes require ``current_password`` for verification,
    and the new password must pass the strength policy (zxcvbn score >= 3,
    12–128 characters).
    """
    return await user_service.self_update(data=body, requesting_user=current_user)


# ---------------------------------------------------------------------------
# User listing (admin / superuser only)
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[UserListRead], summary="List users (admin/superuser only)")
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> list[User]:
    return user_service.list_users(
        requesting_user=current_user,
        skip=skip,
        limit=limit,
        role=role,
        is_active=is_active,
    )


# ---------------------------------------------------------------------------
# Create user (admin / superuser only — no self-registration)
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (admin/superuser only)",
)
async def create_user(
    body: UserCreate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    No self-registration — only admins or the superuser may create accounts.
    Password must pass the strength policy (zxcvbn score >= 3, 12–128 chars).
    """
    if current_user.role not in (UserRole.admin, UserRole.superuser):
        raise PermissionDeniedError("Only admins or the superuser may create users")
    return await user_service.create_user(data=body, created_by_role=current_user.role)


# ---------------------------------------------------------------------------
# Get / update / delete a specific user
# ---------------------------------------------------------------------------

@router.get("/{user_id}", response_model=UserRead, summary="Get a user by ID")
def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> User:
    return user_service.get_user(user_id=user_id, requesting_user=current_user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update a user's details (admin/superuser only)",
)
def update_user(
    user_id: str,
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> User:
    if current_user.role not in (UserRole.admin, UserRole.superuser):
        raise PermissionDeniedError("Only admins or the superuser may update users")
    return user_service.update_user(
        user_id=user_id, data=body, requesting_user=current_user
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user (superuser only)",
)
def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> None:
    if current_user.role != UserRole.superuser:
        raise PermissionDeniedError("Only the superuser may delete accounts")
    user_service.delete_user(user_id=user_id, requesting_user=current_user)
