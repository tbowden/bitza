"""SQLAlchemy User model"""

from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class User(Base):
    """User database model"""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(
            Integer, 
            primary_key = True, 
            index = True)

    email: Mapped[str] = mapped_column(
            String(100), 
            unique = True, 
            nullable = False, 
            index = True)

    display_name: Mapped[str] = mapped_column(
            String(50), 
            unique = True, 
            nullable = False, 
            index = True)

    hashed_password: Mapped[str] = mapped_column(
            String(255), 
            nullable = False)

    is_active: Mapped[bool] = mapped_column(
            Boolean, 
            default=True, 
            nullable=False)

    is_superuser: Mapped[bool] = mapped_column(
            Boolean,
            default=False,
            nullable=False)

    created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), 
            server_default=func.now(), 
            nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), 
            onupdate=func.now(),
            nullable=True)


    def __repr__(self):
        return f"<User(id={self.id}, display_name='{self.display_name}', email='{self.email}')>"

