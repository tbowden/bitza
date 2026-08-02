from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    member_count: int = 0   # populated by service
    created_at: datetime


class ProjectListRead(BaseModel):
    """Compact form for pickers/dropdowns."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    member_count: int = 0


# ---------------------------------------------------------------------------
# ProjectMember
# ---------------------------------------------------------------------------

class ProjectMemberCreate(BaseModel):
    user_id: str
    is_primary: bool = False


class ProjectMemberSetPrimary(BaseModel):
    is_primary: bool


class ProjectMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    user_id: str
    user_display_name: str = ""   # populated by service
    is_primary: bool
    created_at: datetime


class MyProjectMembershipRead(BaseModel):
    """One row of the current user's own project memberships, for the '/me'
    landing page — project name plus the is_primary flag so the frontend
    can highlight it, without a client-side join against GET /projects/."""

    project_id: str
    project_name: str
    is_primary: bool
