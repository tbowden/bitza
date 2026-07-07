from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bitza import BitzaImage


class BitzaImageRepository:
    """Data-access layer for the bitza_images table."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, image_id: str) -> Optional[BitzaImage]:
        return self._db.get(BitzaImage, image_id)

    def list_for_bitza(self, bitza_id: str) -> list[BitzaImage]:
        stmt = (
            select(BitzaImage)
            .where(BitzaImage.bitza_id == bitza_id)
            .order_by(BitzaImage.uploaded_at)
        )
        return list(self._db.scalars(stmt).all())

    def get_primary(self, bitza_id: str) -> Optional[BitzaImage]:
        stmt = select(BitzaImage).where(
            BitzaImage.bitza_id == bitza_id, BitzaImage.is_primary.is_(True)
        )
        return self._db.scalar(stmt)

    def create(self, image: BitzaImage) -> BitzaImage:
        self._db.add(image)
        self._db.flush()
        self._db.refresh(image)
        return image

    def update(self, image: BitzaImage) -> BitzaImage:
        self._db.flush()
        self._db.refresh(image)
        return image

    def delete(self, image: BitzaImage) -> None:
        self._db.delete(image)
        self._db.flush()

    def unset_primary_for_bitza(self, bitza_id: str) -> None:
        """Same rotation pattern used for refresh tokens and primary team
        membership — unset the old primary before the caller sets a new
        one, inside the same transaction."""
        existing = self.get_primary(bitza_id)
        if existing:
            existing.is_primary = False
            self._db.flush()
