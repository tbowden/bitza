from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_by: Optional[str]
    asset_count: int = 0    # populated by service
    created_at: datetime


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------

class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    initial_quantity: int = Field(0, ge=0)
    unit: Optional[str] = Field(None, max_length=50)
    source_supplier: Optional[str] = Field(None, max_length=200)
    part_number: Optional[str] = Field(None, max_length=150)
    datasheet_url: Optional[str] = None
    order_url: Optional[str] = None
    category_id: Optional[str] = None
    tags: Optional[list[str]] = None
    project_name: Optional[str] = Field(None, max_length=200)
    trello_link: Optional[str] = None
    location_detail_id: str   # required


class AssetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=50)
    source_supplier: Optional[str] = Field(None, max_length=200)
    part_number: Optional[str] = Field(None, max_length=150)
    datasheet_url: Optional[str] = None
    order_url: Optional[str] = None
    category_id: Optional[str] = None
    tags: Optional[list[str]] = None
    project_name: Optional[str] = Field(None, max_length=200)
    trello_link: Optional[str] = None
    # Location can be reassigned (to any accessible detail).
    location_detail_id: Optional[str] = None


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    quantity: int
    unit: Optional[str]
    source_supplier: Optional[str]
    part_number: Optional[str]
    datasheet_url: Optional[str]
    order_url: Optional[str]
    category_id: Optional[str]
    category_name: Optional[str] = None      # populated by service
    tags: Optional[list[str]]
    image_path: Optional[str]
    project_name: Optional[str]
    trello_link: Optional[str]
    location_detail_id: str
    location_detail_name: str = ""           # populated by service
    storage_location_id: str = ""            # populated by service
    storage_location_name: str = ""          # populated by service
    created_by: Optional[str]
    created_by_display_name: str = ""        # populated by service
    created_at: datetime
    updated_at: datetime


class AssetListRead(BaseModel):
    """Compact form for list endpoint."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    quantity: int
    unit: Optional[str]
    part_number: Optional[str]
    category_name: Optional[str] = None
    location_detail_name: str = ""
    storage_location_name: str = ""
    created_at: datetime


# ---------------------------------------------------------------------------
# AssetTransaction
# ---------------------------------------------------------------------------

class TransactionCreate(BaseModel):
    delta: int = Field(..., description="Positive = stock in, negative = stock out")
    note: Optional[str] = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    delta: int
    quantity_after: int
    user_id: Optional[str]
    user_display_name: str = ""   # populated by service
    note: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    action: str
    user_id: Optional[str]
    user_display_name: str = ""   # populated by service
    description: Optional[str]
    created_at: datetime
