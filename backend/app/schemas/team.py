from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    member_count: int = 0   # populated by service
    created_at: datetime


class TeamListRead(BaseModel):
    """Compact form for pickers/dropdowns."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    member_count: int = 0


# ---------------------------------------------------------------------------
# TeamMember
# ---------------------------------------------------------------------------

class TeamMemberCreate(BaseModel):
    user_id: str
    is_primary: bool = False


class TeamMemberSetPrimary(BaseModel):
    is_primary: bool


class TeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    user_id: str
    user_display_name: str = ""   # populated by service
    is_primary: bool
    created_at: datetime
