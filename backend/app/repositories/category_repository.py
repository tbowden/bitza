from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bitza import Bitza
from app.models.category import Category


class CategoryRepository:
    """
    Data-access layer for the categories table.

    Unchanged in shape from Phase 2 — the only change is count_bitzas
    (renamed from count_assets) now counting against the unified Bitza
    table instead of the old Asset table.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, category_id: str) -> Optional[Category]:
        return self._db.get(Category, category_id)

    def get_by_name(self, name: str) -> Optional[Category]:
        stmt = select(Category).where(Category.name == name)
        return self._db.scalar(stmt)

    def list_all(self) -> list[Category]:
        stmt = select(Category).order_by(Category.name)
        return list(self._db.scalars(stmt).all())

    def count_bitzas(self, category_id: str) -> int:
        stmt = select(func.count()).select_from(Bitza).where(
            Bitza.category_id == category_id
        )
        return self._db.scalar(stmt) or 0

    def create(self, category: Category) -> Category:
        self._db.add(category)
        self._db.flush()
        self._db.refresh(category)
        return category

    def update(self, category: Category) -> Category:
        self._db.flush()
        self._db.refresh(category)
        return category

    def delete(self, category: Category) -> None:
        self._db.delete(category)
        self._db.flush()
