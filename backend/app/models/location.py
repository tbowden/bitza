import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StorageLocation(Base):
    """
    A top-level named location — room, shed, garage, carport, etc.

    Privacy:
      is_private=False (default) → visible to all authenticated users.
      is_private=True            → visible only to the owner and superuser.
    """

    __tablename__ = "storage_locations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    details: Mapped[list["LocationDetail"]] = relationship(
        "LocationDetail", back_populates="storage_location", passive_deletes=True
    )


class LocationDetail(Base):
    """
    A sub-location within a StorageLocation — shelf, box, drawer, etc.

    Privacy cascade: if the parent StorageLocation is private, this detail is
    effectively private regardless of its own is_private flag.
    """

    __tablename__ = "location_details"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    storage_location_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("storage_locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rfid_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    storage_location: Mapped["StorageLocation"] = relationship(
        "StorageLocation", back_populates="details"
    )
