"""User business logic service"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import AdminUserCreate, AdminUserUpdate


class UserService:
    """User business logic service"""

    # ---------- GET SINGLE ----------

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """
        Get user by ID.
        
        Raises:
            HTTPException: If user not found
        """
        stmt = select(User).where(User.id == user_id)
        user = db.execute(stmt).scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )
        return user

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User | None:
        """Get user by email (returns None if not found)"""
        stmt = select(User).where(User.email == email)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_user_by_display_name(db: Session, display_name: str) -> User | None:
        """Get user by display_name (returns None if not found)"""
        stmt = select(User).where(User.display_name == display_name)
        return db.execute(stmt).scalar_one_or_none()

    # ---------- LIST ----------

    @staticmethod
    def list_users(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> tuple[list[User], int]:
        """
        List users with pagination.
        
        Returns:
            Tuple of (users list, total count)
        """
        base_stmt = select(User)

        if active_only:
            base_stmt = base_stmt.where(User.is_active.is_(True))

        # Total count
        count_stmt = select(func.count()).select_from(
            base_stmt.subquery()
        )
        total = db.execute(count_stmt).scalar_one()

        # Paged results
        stmt = base_stmt.offset(skip).limit(limit)
        users = db.execute(stmt).scalars().all()

        return users, total

    # ---------- CREATE ----------

    @staticmethod
    def admin_create_user(db: Session, user_in: AdminUserCreate) -> User:
        """
        Create new user.
        
        Raises:
            HTTPException: If validation fails or user exists
        """
        # Check if email already exists
        if UserService.get_user_by_email(db, user_in.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Check if display_name already exists
        if UserService.get_user_by_display_name(db, user_in.display_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

        hashed_password = hash_password(user_in.password)

        # Create user
        new_user = User(
            display_name=user_in.display_name,
            email=user_in.email,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=False,
        )

        try:
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User creation failed due to database constraint",
            )

        return new_user

    # ---------- UPDATE ----------

    @staticmethod
    def admin_pdate_user(db: Session, user_id: int, user_in: AdminUserUpdate) -> User:
        """
        Update user.
        
        Business rules:
        - Email must remain unique if changed
        - Only update fields that are provided
        
        Raises:
            HTTPException: If user not found or validation fails
        """
        user = UserService.get_user_by_id(db, user_id)

        # Check email uniqueness if changing
        if user_in.email and user_in.email != user.email:
            existing = UserService.get_user_by_email(db, user_in.email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )

        # Update only provided fields
        update_data = user_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Update failed due to database constraint",
            )

        return user

    # ---------- DELETE ----------

    @staticmethod
    def delete_user(db: Session, user_id: int) -> None:
        """
        Delete user.
        
        Business rules:
        - Can optionally check if user should be deactivated instead
        
        Raises:
            HTTPException: If user not found
        """
        user = UserService.get_user_by_id(db, user_id)
        db.delete(user)
        db.commit()

    # ---------- SOFT DELETE ----------

    @staticmethod
    def deactivate_user(db: Session, user_id: int) -> User:
        """
        Deactivate user (soft delete).
        
        Raises:
            HTTPException: If user not found
        """
        user = UserService.get_user_by_id(db, user_id)
        user.is_active = False
        db.commit()
        db.refresh(user)
        return user
