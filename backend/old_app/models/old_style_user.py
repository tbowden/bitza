"""SQLAlchemy User model"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.base import Base

class User(Base):
    """User database model"""
    __tablename__ = "users"
    id = Column(Integer, primary_key = True, index = True)
    email = Column(String(100), unique = True, nullable = False, index = True)
    display_name = Column(String(50), unique = True, nullable = False, index = True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default = True, nullable = False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


    def __repr__(self):
        return f"<User(id={self.id}, display_name='{self.display_name}', email='{self.email}')>"
