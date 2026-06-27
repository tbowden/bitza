from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


class UserRepository:
    """
    Data-access layer for the ``users`` table.

    Rules:
    - No business logic.
    - Returns ORM model instances.
    - Uses flush() rather than commit() — the service layer owns transactions.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self._db.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email.lower())
        return self._db.scalar(stmt)

    def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username.lower())
        return self._db.scalar(stmt)

    def get_by_identifier(self, identifier: str) -> Optional[User]:
        """Look up by email OR username (case-insensitive)."""
        normalised = identifier.lower()
        stmt = select(User).where(
            (User.email == normalised) | (User.username == normalised)
        )
        return self._db.scalar(stmt)

    def get_superuser(self) -> Optional[User]:
        """Return the single superuser row, or None if none exists yet."""
        stmt = select(User).where(User.role == UserRole.superuser)
        return self._db.scalar(stmt)

    def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
    ) -> list[User]:
        stmt = select(User)
        if role is not None:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
        return list(self._db.scalars(stmt).all())

    def count(self) -> int:
        stmt = select(func.count()).select_from(User)
        return self._db.scalar(stmt) or 0

    # ------------------------------------------------------------------
    # Writes — flush only; commit is the service's responsibility.
    # ------------------------------------------------------------------

    def create(self, user: User) -> User:
        self._db.add(user)
        self._db.flush()
        self._db.refresh(user)
        return user

    def update(self, user: User) -> User:
        """Flush pending attribute changes and refresh from DB."""
        self._db.flush()
        self._db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self._db.delete(user)
        self._db.flush()
