from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# StorageLocation
# ---------------------------------------------------------------------------

class StorageLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    is_private: bool = False


class StorageLocationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    is_private: Optional[bool] = None
    # Only the superuser may reassign ownership via API.
    owner_id: Optional[str] = None


class StorageLocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    owner_id: str
    owner_display_name: str = ""   # populated by service
    is_private: bool
    detail_count: int = 0          # populated by service
    created_at: datetime
    updated_at: datetime


class StorageLocationListRead(BaseModel):
    """Compact form for dropdown lists in the Angular UI."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    owner_display_name: str = ""
    is_private: bool
    detail_count: int = 0


# ---------------------------------------------------------------------------
# LocationDetail
# ---------------------------------------------------------------------------

class LocationDetailCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    is_private: bool = False
    rfid_tag: Optional[str] = Field(None, max_length=100)


class LocationDetailUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    is_private: Optional[bool] = None
    rfid_tag: Optional[str] = Field(None, max_length=100)
    # Superuser only: reassign owner.
    owner_id: Optional[str] = None


class LocationDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    storage_location_id: str
    storage_location_name: str = ""   # populated by service
    name: str
    owner_id: str
    owner_display_name: str = ""      # populated by service
    is_private: bool
    # Effective privacy: True if this detail or its parent is private.
    effective_private: bool = False   # populated by service
    rfid_tag: Optional[str]
    asset_count: int = 0              # populated by service
    created_at: datetime
    updated_at: datetime


class LocationDetailListRead(BaseModel):
    """Compact form for dropdown lists."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    storage_location_id: str
    storage_location_name: str = ""
    is_private: bool
    effective_private: bool = False
    rfid_tag: Optional[str]
    asset_count: int = 0
