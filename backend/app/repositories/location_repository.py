from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.location import LocationDetail, StorageLocation


class LocationRepository:
    """
    Data-access layer for storage_locations and location_details tables.
    No business logic. Returns ORM instances. Flushes only — service commits.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # StorageLocation reads
    # ------------------------------------------------------------------

    def get_location(self, location_id: str) -> Optional[StorageLocation]:
        return self._db.get(StorageLocation, location_id)

    def list_locations(self) -> list[StorageLocation]:
        stmt = select(StorageLocation).order_by(StorageLocation.name)
        return list(self._db.scalars(stmt).all())

    def count_details(self, location_id: str) -> int:
        stmt = select(func.count()).select_from(LocationDetail).where(
            LocationDetail.storage_location_id == location_id
        )
        return self._db.scalar(stmt) or 0

    # ------------------------------------------------------------------
    # StorageLocation writes
    # ------------------------------------------------------------------

    def create_location(self, location: StorageLocation) -> StorageLocation:
        self._db.add(location)
        self._db.flush()
        self._db.refresh(location)
        return location

    def update_location(self, location: StorageLocation) -> StorageLocation:
        self._db.flush()
        self._db.refresh(location)
        return location

    def delete_location(self, location: StorageLocation) -> None:
        self._db.delete(location)
        self._db.flush()

    # ------------------------------------------------------------------
    # LocationDetail reads
    # ------------------------------------------------------------------

    def get_detail(self, detail_id: str) -> Optional[LocationDetail]:
        return self._db.get(LocationDetail, detail_id)

    def list_details_for_location(self, location_id: str) -> list[LocationDetail]:
        stmt = (
            select(LocationDetail)
            .where(LocationDetail.storage_location_id == location_id)
            .order_by(LocationDetail.name)
        )
        return list(self._db.scalars(stmt).all())

    def count_assets_for_detail(self, detail_id: str) -> int:
        """Avoid circular import by using raw SQL count via text."""
        from sqlalchemy import text
        result = self._db.execute(
            text("SELECT COUNT(*) FROM assets WHERE location_detail_id = :did"),
            {"did": detail_id},
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # LocationDetail writes
    # ------------------------------------------------------------------

    def create_detail(self, detail: LocationDetail) -> LocationDetail:
        self._db.add(detail)
        self._db.flush()
        self._db.refresh(detail)
        return detail

    def update_detail(self, detail: LocationDetail) -> LocationDetail:
        self._db.flush()
        self._db.refresh(detail)
        return detail

    def delete_detail(self, detail: LocationDetail) -> None:
        self._db.delete(detail)
        self._db.flush()
