"""User Pydantic schemas"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime


class UserBase(BaseModel):
    """Shared user properties"""
    display_name: str = Field(min_length=3, max_length=50)
    email: EmailStr
    

class UserCreate(UserBase):
    """Properties to receive on user creation"""
    password: str = Field(min_length = 8)

class UserUpdate(UserBase):
    """Update user profle/settings"""
    display_name: str | None = None
    email: EmailStr | None = None

class OldUserResponse(UserBase):
    """User get individual user details"""
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes = True)

class UserResponse(UserBase):
    """User get individual user details"""
    id: int

    model_config = ConfigDict(from_attributes = True)

class UserListResponse(BaseModel):
    """List of Users"""
    items: list[UserResponse]
    total: int

    model_config = ConfigDict(from_attributes=True)

class Me(UserBase):
    """Show users their own profile"""
    created_at: datetime
    last_modified: datetime
