"""User Pydantic schemas"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Shared user properties"""
    id: int
    display_name: str = Field(min_length=3, max_length=50)
    email: EmailStr
    

class AdminUserCreate(BaseModel):
    """Properties to receive on user creation"""
    display_name: str = Field(min_lenght=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length = 8, max_length=255)

class AdminUserUpdate(UserBase):
    """Update user profle/settings"""
    display_name: str | None = None
    email: EmailStr | None = None

class AdminUserResponse(UserBase):
    """SuperUser get individual user details"""
    is_active: bool
    is_superuser: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes = True)

#class UserResponse(UserBase):
#    """User get individual user details"""
#    id: int

#    model_config = ConfigDict(from_attributes = True)

class UserListResponse(BaseModel):
    """List of Users"""
    items: list[UserBase]
    total: int

    model_config = ConfigDict(from_attributes=True)

class MeRequest(BaseModel):
    """Users request their own profile"""
    id: int
    display_name: Optional[str]

class MeResponse(UserBase):
    """Show users their own profile"""
    created_at: datetime
    last_modified: datetime

class MeUpdateRequest(BaseModel):
    """User update their own profile"""
    current_password: str 
