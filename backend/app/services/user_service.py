import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    InvalidCredentialsError,
    PermissionDeniedError,
    SuperuserExistsError,
    UserNotFoundError,
)
from app.core.security import hash_password, validate_password, verify_password
from app.models.user import User, UserRole
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserSelfUpdate, UserUpdate


class UserService:
    """
    All user-management business logic lives here.

    Permission matrix:
    ┌─────────────────────────────────┬───────────┬───────┬──────┐
    │ Action                          │ superuser │ admin │ user │
    ├─────────────────────────────────┼───────────┼───────┼──────┤
    │ Create superuser                │ CLI only  │  ✗    │  ✗   │
    │ Create admin                    │    ✓      │  ✗    │  ✗   │
    │ Create normal user              │    ✓      │  ✓    │  ✗   │
    │ List / view any user            │    ✓      │  ✓    │  ✗   │
    │ View own profile                │    ✓      │  ✓    │  ✓   │
    │ Update own profile (self)       │    ✓      │  ✓    │  ✓   │
    │ Update any user details         │    ✓      │ users │  ✗   │
    │ Suspend a user                  │    ✓      │ users │  ✗   │
    │ Change user role                │    ✓      │  ✗    │  ✗   │
    │ Delete a user                   │    ✓      │  ✗    │  ✗   │
    │ Be suspended                    │    ✗      │  ✓    │  ✓   │
    └─────────────────────────────────┴───────────┴───────┴──────┘

    Methods that set or change passwords are async because they call the
    async validate_password() helper (zxcvbn + optional HIBP breach check).
    All other methods remain synchronous.
    """

    def __init__(
        self,
        db: Session,
        user_repo: UserRepository,
        token_repo: TokenRepository,
    ) -> None:
        self._db = db
        self._user_repo = user_repo
        self._token_repo = token_repo

    # ------------------------------------------------------------------
    # Superuser bootstrap (CLI only)
    # ------------------------------------------------------------------

    async def create_superuser(
        self,
        email: str,
        username: str,
        display_name: str,
        password: str,
    ) -> User:
        """
        Create the single application superuser.
        Only callable from the CLI — not exposed as an API endpoint.
        """
        if self._user_repo.get_superuser():
            raise SuperuserExistsError()
        self._assert_unique(email=email, username=username)
        await validate_password(password)

        user = User(
            id=str(uuid.uuid4()),
            email=email.lower(),
            username=username.lower(),
            display_name=display_name,
            hashed_password=hash_password(password),
            role=UserRole.superuser,
            is_active=True,
        )
        created = self._user_repo.create(user)
        self._db.commit()
        return created

    # ------------------------------------------------------------------
    # Create user (admin/superuser)
    # ------------------------------------------------------------------

    async def create_user(self, data: UserCreate, created_by_role: UserRole) -> User:
        """
        Create a new user account. No self-registration.

        Superuser  → may create admin or user roles.
        Admin      → may only create user role.
        """
        if data.role == UserRole.superuser:
            raise PermissionDeniedError("Superuser cannot be created via the API")
        if created_by_role == UserRole.admin and data.role != UserRole.user:
            raise PermissionDeniedError("Admins may only create accounts with the 'user' role")

        self._assert_unique(email=data.email, username=data.username)
        await validate_password(data.password)

        user = User(
            id=str(uuid.uuid4()),
            email=data.email.lower(),
            username=data.username.lower(),
            display_name=data.display_name,
            hashed_password=hash_password(data.password),
            role=data.role,
            is_active=True,
        )
        created = self._user_repo.create(user)
        self._db.commit()
        return created

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_user(self, user_id: str, requesting_user: User) -> User:
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        if requesting_user.role == UserRole.user and requesting_user.id != user_id:
            raise PermissionDeniedError("You may only view your own profile")
        return user

    def list_users(
        self,
        requesting_user: User,
        skip: int = 0,
        limit: int = 100,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
    ) -> list[User]:
        if requesting_user.role == UserRole.user:
            raise PermissionDeniedError()
        return self._user_repo.list_users(
            skip=skip, limit=limit, role=role, is_active=is_active
        )

    # ------------------------------------------------------------------
    # Update (admin/superuser path)
    # ------------------------------------------------------------------

    def update_user(
        self, user_id: str, data: UserUpdate, requesting_user: User
    ) -> User:
        target = self._user_repo.get_by_id(user_id)
        if not target:
            raise UserNotFoundError()

        self._check_update_permissions(data=data, target=target, actor=requesting_user)

        if data.display_name is not None:
            target.display_name = data.display_name
        if data.email is not None:
            new_email = data.email.lower()
            existing = self._user_repo.get_by_email(new_email)
            if existing and existing.id != user_id:
                raise ConflictError("Email address is already in use")
            target.email = new_email
        if data.username is not None:
            new_username = data.username.lower()
            existing = self._user_repo.get_by_username(new_username)
            if existing and existing.id != user_id:
                raise ConflictError("Username is already in use")
            target.username = new_username
        if data.is_active is not None:
            target.is_active = data.is_active
        if data.role is not None:
            target.role = data.role

        updated = self._user_repo.update(target)
        self._db.commit()
        return updated

    # ------------------------------------------------------------------
    # Self-update (any authenticated user)
    # ------------------------------------------------------------------

    async def self_update(
        self, data: UserSelfUpdate, requesting_user: User
    ) -> User:
        user = self._user_repo.get_by_id(requesting_user.id)
        if not user:
            raise UserNotFoundError()

        if data.display_name is not None:
            user.display_name = data.display_name

        if data.new_password:
            if not data.current_password:
                raise InvalidCredentialsError("current_password is required")
            if not verify_password(data.current_password, user.hashed_password):
                raise InvalidCredentialsError("Current password is incorrect")
            await validate_password(data.new_password)
            user.hashed_password = hash_password(data.new_password)

        updated = self._user_repo.update(user)
        self._db.commit()
        return updated

    # ------------------------------------------------------------------
    # Delete (superuser only)
    # ------------------------------------------------------------------

    def delete_user(self, user_id: str, requesting_user: User) -> None:
        if requesting_user.role != UserRole.superuser:
            raise PermissionDeniedError("Only the superuser may delete accounts")
        target = self._user_repo.get_by_id(user_id)
        if not target:
            raise UserNotFoundError()
        if target.id == requesting_user.id:
            raise PermissionDeniedError("The superuser cannot delete their own account")
        self._user_repo.delete(target)
        self._db.commit()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _assert_unique(self, email: str, username: str) -> None:
        if self._user_repo.get_by_email(email):
            raise ConflictError("Email address is already registered")
        if self._user_repo.get_by_username(username):
            raise ConflictError("Username is already taken")

    def _check_update_permissions(
        self, data: UserUpdate, target: User, actor: User
    ) -> None:
        if actor.role == UserRole.user:
            raise PermissionDeniedError()
        if actor.role == UserRole.admin:
            if target.role in (UserRole.admin, UserRole.superuser):
                raise PermissionDeniedError(
                    "Admins may not modify admin or superuser accounts"
                )
            if data.role is not None:
                raise PermissionDeniedError("Admins may not change user roles")
        if actor.role == UserRole.superuser:
            if data.is_active is False and target.id == actor.id:
                raise PermissionDeniedError("The superuser account cannot be suspended")
            if data.role == UserRole.superuser:
                raise PermissionDeniedError(
                    "Superuser role cannot be assigned via the API"
                )
