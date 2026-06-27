from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Write schemas (input)
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """
    Used by admins/superusers to create a new user.
    No self-registration — this schema is only reachable by privileged roles.
    """

    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    display_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=12, max_length=128)
    role: UserRole = UserRole.user

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        cleaned = v.strip()
        # Allow letters, digits, underscores, hyphens only.
        if not all(c.isalnum() or c in ("_", "-") for c in cleaned):
            raise ValueError(
                "Username may only contain letters, numbers, underscores, and hyphens"
            )
        return cleaned.lower()

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower()


class UserUpdate(BaseModel):
    """
    Used by admins/superusers to update a user's details.
    All fields are optional — only supplied fields are changed.
    Role changes are superuser-only (enforced in UserService).
    """

    display_name: Optional[str] = Field(None, min_length=1, max_length=150)
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None  # Superuser-only; service enforces this

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.strip()
        if not all(c.isalnum() or c in ("_", "-") for c in cleaned):
            raise ValueError(
                "Username may only contain letters, numbers, underscores, and hyphens"
            )
        return cleaned.lower()

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: Optional[str]) -> Optional[str]:
        return v.lower() if v else v


class UserSelfUpdate(BaseModel):
    """
    Used by a normal user updating their own profile.
    Can change display_name or password only.
    Password change requires current_password for verification.
    """

    display_name: Optional[str] = Field(None, min_length=1, max_length=150)
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=12, max_length=128)

    @model_validator(mode="after")
    def password_change_requires_current(self) -> "UserSelfUpdate":
        if self.new_password and not self.current_password:
            raise ValueError("current_password is required when setting a new_password")
        return self


# ---------------------------------------------------------------------------
# Read schemas (output)
# ---------------------------------------------------------------------------

class UserRead(BaseModel):
    """Full user detail — returned on get/create/update."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserListRead(BaseModel):
    """Compact representation for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
